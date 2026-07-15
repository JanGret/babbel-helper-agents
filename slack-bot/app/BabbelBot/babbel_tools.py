"""
BabbelBot Tools: Implementierung der Babbel-Portal-Interaktionen.

Diese Funktionen werden von den @tool-dekorierten Funktionen in main.py aufgerufen.
Sie kapseln die Playwright-Browser-Automation und Daten-Lookups.

HINWEIS: Dies ist ein Entwurf. Die Funktionen muessen noch mit der tatsaechlichen
Playwright-Logik aus den bestehenden Scripts (refill_credits.py, invite_user.py)
befuellt werden. Die Signaturen und Return-Werte sind bereits definiert.
"""

import csv
import os
import time
from pathlib import Path

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

BABBEL_BASE_URL = "https://my.babbel.com"
USERS_URL = f"{BABBEL_BASE_URL}/en/organizations/jobcloud/users"
INTENSIVE_URL = f"{BABBEL_BASE_URL}/en/organizations/jobcloud/intensivecredits"

# In Cloud: Session-State in S3 oder als Secret speichern
# Lokal: .session/state.json
SESSION_STATE_PATH = os.getenv("BABBEL_SESSION_PATH", "/tmp/babbel_session/state.json")

# CSV-Daten (in Cloud: aus S3 laden)
DATA_DIR = Path(os.getenv("BABBEL_DATA_DIR", "/tmp/babbel_data"))

# Admin Slack User ID fuer Benachrichtigungen
ADMIN_SLACK_USER_ID = os.getenv("ADMIN_SLACK_USER_ID", "")

# Limits
MAX_SLOTS = 100
ADMIN_COUNT = 3  # Admin-Accounts die keine Nutzer-Slots belegen
MAX_INTENSIVE = 30
CREDITS_REFILL_THRESHOLD = 5  # Nur nachfuellen wenn remaining < 5
CREDITS_TARGET = 10  # Auffuellen auf diesen Wert
CREDITS_HARD_CAP = 20


# ---------------------------------------------------------------------------
# Helper: Browser Session
# ---------------------------------------------------------------------------

def _get_browser_context(playwright):
    """Erstellt einen Browser-Context mit gespeicherter Session.

    Verwendet headless Chromium. Session-State wird persistent gespeichert
    um wiederholtes Einloggen (und Captcha) zu vermeiden.
    """
    browser = playwright.chromium.launch(headless=True)
    session_path = Path(SESSION_STATE_PATH)

    context_kwargs = {
        "viewport": {"width": 1440, "height": 900},
    }
    if session_path.exists():
        context_kwargs["storage_state"] = str(session_path)

    context = browser.new_context(**context_kwargs)
    return browser, context


def _login(page):
    """Login to Babbel portal. Skips if session is still valid.

    HINWEIS: In der Cloud muss die Session persistent gehalten werden.
    Das erste Login braucht evtl. ein manuelles Captcha -- das muss einmalig
    manuell erledigt und der Session-State gespeichert werden.
    """
    email = os.getenv("BABBEL_EMAIL")
    password = os.getenv("BABBEL_PASSWORD")
    if not email or not password:
        return False

    login_url = (
        f"{BABBEL_BASE_URL}/de/authentication/login/email"
        "?return_to=https%3A%2F%2Fmy.babbel.com%2Fde%2Forganizations%2Fjobcloud%2Fusers"
    )
    page.goto(login_url, wait_until="domcontentloaded")

    # Bereits eingeloggt?
    try:
        page.wait_for_url("**/organizations/**", timeout=15000)
        return True
    except PlaywrightTimeout:
        pass

    # Login-Flow
    email_input = page.locator('input[type="email"], input[name="email"], input[id*="email"]')
    email_input.first.wait_for(state="visible", timeout=15000)
    email_input.first.fill(email)
    page.locator('button:has-text("Weiter"), button:has-text("Continue"), [type="submit"]').first.click()

    pw_input = page.locator('input[type="password"]')
    pw_input.first.wait_for(state="visible", timeout=15000)
    pw_input.first.fill(password)
    page.locator('button:has-text("Einloggen"), button:has-text("Log in"), button:has-text("Weiter"), [type="submit"]').first.click()

    try:
        page.wait_for_url("**/organizations/**", timeout=30000)
        return True
    except PlaywrightTimeout:
        return False


# ---------------------------------------------------------------------------
# Tool Implementations
# ---------------------------------------------------------------------------

def check_user_status(email: str) -> dict:
    """Prueft den Status eines Nutzers anhand der lokalen/S3 CSV-Daten.

    Returns:
        dict mit: exists, plan, credits_remaining, slots_used, slots_max
    """
    result = {
        "exists": False,
        "plan": None,
        "credits_remaining": None,
        "slots_used": None,
        "slots_max": MAX_SLOTS,
    }

    # Memberships CSV pruefen (existiert der User?)
    memberships_path = DATA_DIR / "memberships.csv"
    if memberships_path.exists():
        with open(memberships_path, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            # Slot-Belegung berechnen (minus Admins)
            result["slots_used"] = len(rows) - ADMIN_COUNT

            for row in rows:
                row_email = (row.get("Email") or row.get("email") or "").strip().lower()
                if row_email == email.strip().lower():
                    result["exists"] = True
                    break

    # Intensive Credits CSV pruefen (Plan + remaining)
    credits_path = DATA_DIR / "intensive_credits.csv"
    if credits_path.exists() and result["exists"]:
        with open(credits_path, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                row_email = (row.get("Email") or row.get("email") or "").strip().lower()
                if row_email == email.strip().lower():
                    result["plan"] = "intensive"
                    try:
                        result["credits_remaining"] = int(row.get("Remaining", 0))
                    except (ValueError, TypeError):
                        result["credits_remaining"] = 0
                    break

    # Falls User existiert aber nicht in Intensive-Credits → Professional
    if result["exists"] and result["plan"] is None:
        result["plan"] = "professional"

    return result


def invite_user(email: str, plan: str, lang: str) -> dict:
    """Laedt einen neuen Nutzer ein via Browser-Automation.

    Portiert die Logik aus invite_user.py.

    Returns:
        dict mit: success, message
    """
    # Duplikat-Check
    status = check_user_status(email)
    if status["exists"]:
        return {"success": False, "message": f"Nutzer {email} existiert bereits."}

    # Slot-Check
    slots_warning = False
    if status["slots_used"] is not None and status["slots_used"] >= MAX_SLOTS:
        slots_warning = True

    try:
        with sync_playwright() as p:
            browser, context = _get_browser_context(p)
            page = context.new_page()

            if not _login(page):
                browser.close()
                return {"success": False, "message": "Login fehlgeschlagen."}

            # Session speichern
            session_path = Path(SESSION_STATE_PATH)
            session_path.parent.mkdir(parents=True, exist_ok=True)
            context.storage_state(path=str(session_path))

            # Zur Users-Seite navigieren
            page.goto(USERS_URL)
            page.wait_for_load_state("networkidle", timeout=30000)
            time.sleep(3)

            # "Invite New Member" klicken
            invite_btn = page.locator(
                'button:has-text("Invite New Member"), '
                '[data-class*="invite"]'
            )
            invite_btn.first.click(timeout=10000)
            time.sleep(2)

            # E-Mail eingeben
            email_input = page.locator('[role="dialog"] input[type="email"], [role="dialog"] input[type="text"]')
            email_input.first.wait_for(state="visible", timeout=10000)
            email_input.first.fill(email)
            time.sleep(1)

            # Sprache auswaehlen (Radix UI Dropdown)
            lang_trigger = page.locator('button:has-text("Email invitation language")')
            if lang_trigger.count() > 0:
                lang_trigger.first.click(timeout=5000)
                time.sleep(1)
                lang_option = page.locator(f'[data-class="selectlanguage-invitation-{lang}"]')
                if lang_option.count() > 0:
                    lang_option.first.click(timeout=5000)
                time.sleep(1)

            # Plan auswaehlen (natives <select>)
            plan_label = "Professional" if plan == "professional" else "Intensive"
            plan_dropdown = page.locator('[data-class="selectplan-invitation-standard"], select[aria-label="Plan"]')
            if plan_dropdown.count() > 0:
                plan_dropdown.first.select_option(label=plan_label)
            time.sleep(2)

            # Bei Intensive: Start-Credits eingeben
            if plan == "intensive":
                credits_input = page.locator('[role="dialog"] input[type="number"]')
                try:
                    credits_input.first.wait_for(state="visible", timeout=5000)
                    credits_input.first.clear()
                    credits_input.first.fill("10")
                    time.sleep(1)
                except PlaywrightTimeout:
                    pass

            # "Invite New Members" klicken
            confirm_btn = page.locator('[data-class="add-invitations-modal"]')
            confirm_btn.first.click(timeout=10000)
            time.sleep(3)

            # Erfolg pruefen
            alert = page.locator('[role="alert"]:visible')
            if alert.count() > 0:
                alert_text = alert.first.text_content() or ""
                if "success" in alert_text.lower() or "invited" in alert_text.lower():
                    browser.close()
                    msg = f"Einladung an {email} gesendet (Plan: {plan_label})."
                    if slots_warning:
                        msg += " WARNUNG: Account hat >= 100 Slots belegt!"
                    return {"success": True, "message": msg, "slots_warning": slots_warning}

            browser.close()
            return {"success": False, "message": "Einladung konnte nicht bestaetigt werden."}

    except Exception as e:
        return {"success": False, "message": f"Fehler: {str(e)}"}


def refill_credits(email: str) -> dict:
    """Fuellt Intensive Credits nach via Browser-Automation.

    Portiert die Logik aus refill_credits.py.

    Returns:
        dict mit: success, credits_added, new_remaining, pool_remaining, pool_total, message
    """
    # Vorab-Check: Ist der User Intensive?
    status = check_user_status(email)
    if not status["exists"]:
        return {"success": False, "message": f"Nutzer {email} existiert nicht im Babbel-Account."}
    if status["plan"] != "intensive":
        return {"success": False, "message": f"Nutzer {email} hat keinen Intensive-Plan."}
    if status["credits_remaining"] is not None and status["credits_remaining"] >= CREDITS_REFILL_THRESHOLD:
        return {
            "success": False,
            "message": f"Nutzer hat noch {status['credits_remaining']} Credits. Kein Nachfuellen noetig (Schwelle: < {CREDITS_REFILL_THRESHOLD}).",
        }

    try:
        with sync_playwright() as p:
            browser, context = _get_browser_context(p)
            page = context.new_page()

            if not _login(page):
                browser.close()
                return {"success": False, "message": "Login fehlgeschlagen."}

            # Session speichern
            session_path = Path(SESSION_STATE_PATH)
            session_path.parent.mkdir(parents=True, exist_ok=True)
            context.storage_state(path=str(session_path))

            # Zur Intensive Credits Seite
            page.goto(INTENSIVE_URL)
            page.wait_for_load_state("networkidle", timeout=30000)
            time.sleep(3)

            # Nutzer suchen
            search_input = page.locator('input[type="search"], input[placeholder*="Search"]')
            search_input.first.wait_for(state="visible", timeout=15000)
            search_input.first.fill(email)
            time.sleep(2)

            # Nutzer in Tabelle finden
            user_row = page.locator(f'tr:has-text("{email}")')
            user_row.first.wait_for(state="visible", timeout=15000)

            # Remaining auslesen (fuer korrekte Credits-Berechnung)
            # TODO: _read_remaining_from_row Logik portieren
            credits_to_add = CREDITS_TARGET  # Vereinfacht: immer 10 hinzufuegen

            # Nutzer auswaehlen
            checkbox = user_row.first.locator('input[type="checkbox"]')
            if checkbox.count() > 0:
                checkbox.first.click(timeout=5000)
            time.sleep(2)

            # "Add Credits" klicken
            add_btn = page.locator('[data-class="add-intensivecredits-cta"]')
            add_btn.first.click(timeout=10000)
            time.sleep(2)

            # Credits eingeben
            credits_input = page.locator('[role="dialog"] input[type="number"], [role="dialog"] input[type="text"]')
            credits_input.first.wait_for(state="visible", timeout=10000)
            credits_input.first.clear()
            credits_input.first.fill(str(credits_to_add))
            time.sleep(1)

            # Confirm
            confirm_btn = page.locator('button:has-text("Confirm")')
            confirm_btn.first.click(timeout=10000)
            time.sleep(3)

            # Erfolg pruefen
            alert = page.locator('[role="alert"]:visible')
            if alert.count() > 0:
                alert_text = alert.first.text_content() or ""
                if "success" in alert_text.lower() or "changed" in alert_text.lower():
                    # Pool-Info auslesen
                    import re
                    page_text = page.text_content("body") or ""
                    pool_remaining = None
                    pool_total = None
                    match_total = re.search(r"(\d+)\s*total\s*credits", page_text, re.IGNORECASE)
                    match_remaining = re.search(r"(\d+)\s*remaining\s*credits?", page_text, re.IGNORECASE)
                    if match_total:
                        pool_total = int(match_total.group(1))
                    if match_remaining:
                        pool_remaining = int(match_remaining.group(1))

                    browser.close()
                    return {
                        "success": True,
                        "credits_added": credits_to_add,
                        "new_remaining": credits_to_add,  # Vereinfacht
                        "pool_remaining": pool_remaining,
                        "pool_total": pool_total,
                        "message": f"{credits_to_add} Credits fuer {email} hinzugefuegt.",
                    }

            browser.close()
            return {"success": False, "message": "Credits konnten nicht bestaetigt werden."}

    except Exception as e:
        return {"success": False, "message": f"Fehler: {str(e)}"}


def send_admin_notification(message: str) -> dict:
    """Sendet eine Slack DM an den Admin.

    HINWEIS: Die tatsaechliche Implementierung haengt davon ab,
    wie die Slack-App-Schicht aufgebaut ist. Optionen:
    - Direkt via Slack API (braucht Bot Token)
    - Ueber einen Callback an die Slack-App-Schicht
    - Ueber einen SNS Topic der die Slack-App triggert

    Returns:
        dict mit: success, message
    """
    # TODO: Implementierung abhaengig von Slack-App-Architektur
    # Placeholder: Logge die Nachricht
    import logging
    logging.warning(f"ADMIN NOTIFICATION: {message}")
    return {"success": True, "message": f"Admin benachrichtigt: {message}"}
