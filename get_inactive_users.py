"""
Babbel Helper: Inaktive Nutzer identifizieren

Loggt sich im Babbel-Portal ein, navigiert zu Reports > Learners,
stellt den Timeframe auf die letzten 2 Jahre, exportiert die CSV
und gibt inaktive Nutzer sortiert nach Aktivitaet aus.

Nutzung:
    py get_inactive_users.py [--threshold N] [--headless] [--skip-export]

Voraussetzungen:
    - .env Datei mit BABBEL_EMAIL und BABBEL_PASSWORD
    - py -m pip install playwright python-dotenv
    - py -m playwright install chromium
"""

import argparse
import csv
import io
import json
import os
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

from dotenv import load_dotenv
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

load_dotenv()
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

BABBEL_BASE_URL = "https://my.babbel.com"
REPORTS_URL = f"{BABBEL_BASE_URL}/de/organizations/jobcloud/reports/active"
EXPORT_DIR = Path(__file__).parent / "exports"
SESSION_DIR = Path(__file__).parent / ".session"


# ---------------------------------------------------------------------------
# Browser Automation
# ---------------------------------------------------------------------------

def login(page):
    """Login to Babbel. Skips if session is still valid."""
    email = os.getenv("BABBEL_EMAIL")
    password = os.getenv("BABBEL_PASSWORD")
    if not email or not password:
        print("FEHLER: BABBEL_EMAIL und BABBEL_PASSWORD muessen in .env gesetzt sein.")
        sys.exit(1)

    print(f"Login als {email}...")
    login_url = (
        f"{BABBEL_BASE_URL}/de/authentication/login/email"
        "?return_to=https%3A%2F%2Fmy.babbel.com%2Fde%2Forganizations%2Fjobcloud%2Fusers"
    )
    page.goto(login_url, wait_until="domcontentloaded")

    # Bereits eingeloggt?
    try:
        page.wait_for_url("**/organizations/**", timeout=15000)
        print("  Bereits eingeloggt (gespeicherte Session).")
        return
    except PlaywrightTimeout:
        pass

    # E-Mail eingeben
    email_input = page.locator('input[type="email"], input[name="email"], input[id*="email"]')
    email_input.first.wait_for(state="visible", timeout=15000)
    email_input.first.fill(email)
    page.locator('button:has-text("Weiter"), button:has-text("Continue"), [type="submit"]').first.click()
    print("  E-Mail eingegeben...")

    # Passwort eingeben
    pw_input = page.locator('input[type="password"]')
    pw_input.first.wait_for(state="visible", timeout=15000)
    pw_input.first.fill(password)
    page.locator('button:has-text("Einloggen"), button:has-text("Log in"), button:has-text("Weiter"), [type="submit"]').first.click()
    print("  Passwort eingegeben...")

    # Captcha-Check
    try:
        page.wait_for_url("**/organizations/**", timeout=10000)
    except PlaywrightTimeout:
        print("\n  *** CAPTCHA — bitte im Browser loesen (max 5 Min) ***")
        try:
            page.wait_for_url("**/organizations/**", timeout=300000)
        except PlaywrightTimeout:
            if "authentication" in page.url:
                print("FEHLER: Login fehlgeschlagen.")
                sys.exit(1)

    print("  Login erfolgreich.")


def navigate_to_learners(page):
    """Navigate to Reports > Learners tab."""
    print("Navigiere zu Reports > Learners...")
    page.goto(REPORTS_URL)
    try:
        page.wait_for_load_state("networkidle", timeout=30000)
    except PlaywrightTimeout:
        pass
    time.sleep(5)

    # Klicke Learners-Tab im QuickSight-iframe
    for frame in page.frames:
        try:
            frame.locator('text="Learners"').first.click(timeout=5000)
            print("  Learners-Tab geklickt.")
            time.sleep(5)
            return
        except (PlaywrightTimeout, Exception):
            continue

    print("  WARNUNG: Learners-Tab nicht gefunden.")


def _get_qs_frame(page):
    """Find the QuickSight iframe."""
    for frame in page.frames:
        if "quicksight" in frame.url:
            return frame
    return None


def set_timeframe(page, days_back=730):
    """Set timeframe to 'Custom dates' with start date N days ago."""
    print("Setze Timeframe...")
    qs_frame = _get_qs_frame(page)
    if not qs_frame:
        print("  WARNUNG: QuickSight-Frame nicht gefunden.")
        return

    start_date = (datetime.now() - timedelta(days=days_back)).strftime("%m/%d/%Y")

    # Oeffne Timeframe-Dropdown via mousedown (MUI Select)
    try:
        dropdown = qs_frame.locator('[data-automation-context="Timeframe"][data-automation-id="sheet_control_value"]')
        dropdown.first.dispatch_event("mousedown")
    except PlaywrightTimeout:
        print("  WARNUNG: Timeframe-Dropdown nicht gefunden.")
        return
    time.sleep(3)

    # Waehle "Custom dates" per JS
    result = qs_frame.evaluate('''
        () => {
            const items = document.querySelectorAll('li');
            for (const item of items) {
                if ((item.textContent || '').includes('Custom')) {
                    item.click();
                    return true;
                }
            }
            return false;
        }
    ''')
    if not result:
        print("  WARNUNG: 'Custom dates' nicht gefunden.")
        return
    time.sleep(3)

    # Setze "from"-Datum per React nativeInputValueSetter
    # Im DOM: nth(0) = "to", nth(1) = "from"
    qs_frame.evaluate('''
        (dateValue) => {
            const inputs = document.querySelectorAll('[data-automation-id="date_picker_0"]');
            const input = inputs[1];  // "from" field
            if (!input) return;
            const setter = Object.getOwnPropertyDescriptor(
                window.HTMLInputElement.prototype, 'value'
            ).set;
            setter.call(input, dateValue);
            const reactKey = Object.keys(input).find(k => k.startsWith('__reactProps$'));
            if (reactKey && input[reactKey].onChange) {
                input[reactKey].onChange({target: input, currentTarget: input});
            }
            input.dispatchEvent(new Event('input', { bubbles: true }));
            input.dispatchEvent(new Event('change', { bubbles: true }));
            input.focus();
            input.dispatchEvent(new FocusEvent('blur', { bubbles: true }));
            input.blur();
        }
    ''', start_date)
    time.sleep(2)

    # Schliesse eventuelle Date-Picker Popovers
    qs_frame.evaluate('''
        () => {
            document.querySelectorAll('[role="presentation"][class*="MuiPopover"]').forEach(p => {
                const backdrop = p.querySelector('[aria-hidden="true"]');
                if (backdrop) backdrop.click();
            });
        }
    ''')

    print(f"  Timeframe gesetzt: {start_date} - heute")
    time.sleep(15)


def export_csv(page):
    """Export learners table as CSV via hover menu."""
    print("Exportiere CSV...")
    EXPORT_DIR.mkdir(exist_ok=True)
    time.sleep(5)

    qs_frame = _get_qs_frame(page)
    if not qs_frame:
        raise Exception("QuickSight-Frame nicht gefunden")

    try:
        qs_frame.wait_for_load_state("networkidle", timeout=30000)
    except PlaywrightTimeout:
        pass
    time.sleep(5)

    # Finde den Menue-Button durch Hover ueber grid-blocks
    menu_btn = None
    table_visual = qs_frame.locator('[data-automation-id="grid-block"]')
    count = table_visual.count()
    for idx in range(count):
        try:
            table_visual.nth(idx).hover(timeout=5000)
            time.sleep(2)
            btn = qs_frame.locator('[data-automation-id="analysis_visual_dropdown_menu_button"]')
            if btn.count() > 0:
                menu_btn = btn.first
                break
        except (PlaywrightTimeout, Exception):
            continue

    if not menu_btn:
        raise Exception("Menue-Button nicht gefunden")

    # Klicke Menue-Button
    menu_btn.scroll_into_view_if_needed(timeout=10000)
    time.sleep(1)
    menu_btn = qs_frame.locator('[data-automation-id="analysis_visual_dropdown_menu_button"]').first
    menu_btn.hover(timeout=10000, force=True)
    time.sleep(1)
    menu_btn.click(timeout=10000, force=True)
    time.sleep(2)

    # Klicke "Export to CSV"
    with page.expect_download(timeout=60000) as download_info:
        clicked = False
        for frame in page.frames:
            if clicked:
                break
            try:
                export_btn = frame.locator('[data-automation-id="dashboard_visual_dropdown_export"]')
                if export_btn.count() > 0:
                    export_btn.first.click(timeout=5000)
                    clicked = True
            except (PlaywrightTimeout, Exception):
                continue
        if not clicked:
            raise Exception("Export to CSV nicht gefunden")

    export_path = EXPORT_DIR / "learners_report.csv"
    download_info.value.save_as(export_path)
    print(f"  CSV exportiert: {export_path}")
    return export_path


# ---------------------------------------------------------------------------
# CSV Parsing
# ---------------------------------------------------------------------------

def parse_csv(csv_path, threshold=0):
    """Parse CSV and return all users sorted by activity (least active first)."""
    users = []
    with open(csv_path, "r", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            name = row.get("Name", "")
            email = row.get("E-mail", row.get("E-Mail", row.get("Email", "")))
            try:
                active_days = int(row.get("Active days", 0) or 0)
            except (ValueError, TypeError):
                active_days = 0
            try:
                learning_min = int(float(row.get("Learning minutes", 0) or 0))
            except (ValueError, TypeError):
                learning_min = 0
            try:
                activities = int(row.get("Activities", 0) or 0)
            except (ValueError, TypeError):
                activities = 0

            if name or email:
                users.append({
                    "name": name,
                    "email": email,
                    "active_days": active_days,
                    "learning_minutes": learning_min,
                    "activities": activities,
                })

    users.sort(key=lambda u: (u["active_days"], u["learning_minutes"]))
    inactive = [u for u in users if u["active_days"] <= threshold]
    return users, inactive


def print_results(all_users, inactive_users, threshold):
    """Print formatted results and save JSON."""
    print("\n" + "=" * 70)
    print(f"BABBEL NUTZER-AKTIVITAET (letzte 2 Jahre)")
    print(f"Gesamt: {len(all_users)} Nutzer | Inaktiv (<={threshold} aktive Tage): {len(inactive_users)}")
    print("=" * 70)

    print(f"\n{'#':<4} {'Name':<25} {'E-Mail':<35} {'Tage':<6} {'Min':<8} {'Akt.':<5}")
    print("-" * 83)

    for i, user in enumerate(all_users[:30], 1):
        marker = " **" if user["active_days"] <= threshold else ""
        print(f"{i:<4} {user['name'][:24]:<25} {user['email'][:34]:<35} "
              f"{user['active_days']:<6} {user['learning_minutes']:<8} "
              f"{user['activities']:<5}{marker}")

    if len(all_users) > 30:
        print(f"\n  ... und {len(all_users) - 30} weitere Nutzer")

    output = {
        "total_users": len(all_users),
        "inactive_count": len(inactive_users),
        "threshold_active_days": threshold,
        "inactive_users": inactive_users,
        "all_users_sorted": all_users,
    }
    output_path = EXPORT_DIR / "inactive_users.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f"\nJSON gespeichert: {output_path}")
    return output


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Babbel: Inaktive Nutzer identifizieren")
    parser.add_argument("--threshold", type=int, default=0,
                        help="Schwellenwert aktive Tage (Standard: 0)")
    parser.add_argument("--headless", action="store_true",
                        help="Browser ohne Fenster ausfuehren")
    parser.add_argument("--skip-export", action="store_true",
                        help="Vorhandene CSV nutzen, kein neuer Export")
    args = parser.parse_args()

    if args.skip_export:
        csv_path = EXPORT_DIR / "learners_report.csv"
        if not csv_path.exists():
            print(f"FEHLER: {csv_path} nicht gefunden.")
            sys.exit(1)
    else:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=args.headless)
            SESSION_DIR.mkdir(exist_ok=True)
            context = browser.new_context(
                storage_state=str(SESSION_DIR / "state.json") if (SESSION_DIR / "state.json").exists() else None,
                viewport={"width": 1440, "height": 900},
                accept_downloads=True,
            )
            page = context.new_page()

            try:
                login(page)
                context.storage_state(path=str(SESSION_DIR / "state.json"))
                navigate_to_learners(page)
                set_timeframe(page, days_back=730)
                csv_path = export_csv(page)
            except Exception as e:
                EXPORT_DIR.mkdir(exist_ok=True)
                page.screenshot(path=str(EXPORT_DIR / "error_screenshot.png"))
                print(f"\nFEHLER: {e}")
                print(f"Screenshot: {EXPORT_DIR / 'error_screenshot.png'}")
                sys.exit(1)
            finally:
                browser.close()

    all_users, inactive = parse_csv(csv_path, args.threshold)
    print_results(all_users, inactive, args.threshold)


if __name__ == "__main__":
    main()
