"""
Babbel Export: Generischer Export fuer Babbel QuickSight Reports.

Loggt sich im Babbel-Portal ein, navigiert zum gewuenschten Tab
im Reports-Dashboard und exportiert die Daten als CSV.

Nutzung:
    py export_babbel.py --tab learners       # Learners + 2J Timeframe
    py export_babbel.py --tab app-lessons    # App Lessons (alle Daten)
    py export_babbel.py --tab all            # Beide nacheinander

Voraussetzungen:
    - .env Datei mit BABBEL_EMAIL und BABBEL_PASSWORD
    - py -m pip install playwright python-dotenv
    - py -m playwright install chromium
"""

import argparse
import io
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
USERS_URL = f"{BABBEL_BASE_URL}/de/organizations/jobcloud/users"
INTENSIVE_URL = f"{BABBEL_BASE_URL}/de/organizations/jobcloud/intensivecredits"
DATA_DIR = Path(__file__).parent / "daten"
SESSION_DIR = Path(__file__).parent / ".session"

# Tab-Konfiguration
TABS = {
    "learners": {
        "tab_name": "Learners",
        "output_file": "learners.csv",
        "needs_timeframe": True,
        "source": "quicksight",
    },
    "app-lessons": {
        "tab_name": "App lessons",
        "output_file": "app_lessons.csv",
        "needs_timeframe": False,
        "source": "quicksight",
    },
    "memberships": {
        "tab_name": "Memberships",
        "output_file": "memberships.csv",
        "needs_timeframe": False,
        "source": "users_page",
    },
    "intensive-credits": {
        "tab_name": "Intensive Credits",
        "output_file": "intensive_credits.csv",
        "needs_timeframe": False,
        "source": "intensive_page",
    },
}


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


def navigate_to_reports(page):
    """Navigate to the Reports page."""
    print("Navigiere zu Reports...")
    page.goto(REPORTS_URL)
    try:
        page.wait_for_load_state("networkidle", timeout=30000)
    except PlaywrightTimeout:
        pass
    time.sleep(5)


def click_tab(page, tab_name):
    """Click a specific tab in the QuickSight dashboard."""
    print(f"  Klicke Tab '{tab_name}'...")
    for frame in page.frames:
        try:
            tab = frame.locator(f'text="{tab_name}"').first
            tab.click(timeout=5000)
            print(f"  Tab '{tab_name}' geklickt.")
            time.sleep(5)
            return
        except (PlaywrightTimeout, Exception):
            continue
    print(f"  WARNUNG: Tab '{tab_name}' nicht gefunden!")


def _get_qs_frame(page):
    """Find the QuickSight iframe."""
    for frame in page.frames:
        if "quicksight" in frame.url:
            return frame
    return None


def set_timeframe(page, days_back=730):
    """Set timeframe to 'Custom dates' with start date N days ago."""
    print("  Setze Timeframe auf 2 Jahre...")
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
    date_fields = qs_frame.locator('[data-automation-id="date_picker_0"]')
    if date_fields.count() < 2:
        print("  WARNUNG: Datumsfelder nicht gefunden.")
        return

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
    time.sleep(5)


def export_csv(page, output_path):
    """Export the current tab's table as CSV via hover menu."""
    print("  Exportiere CSV...")

    qs_frame = _get_qs_frame(page)
    if not qs_frame:
        raise Exception("QuickSight-Frame nicht gefunden")

    try:
        qs_frame.wait_for_load_state("networkidle", timeout=15000)
    except PlaywrightTimeout:
        pass
    time.sleep(3)

    # Finde den Menue-Button durch Hover ueber grid-blocks (mit Retry)
    menu_btn = None
    for retry in range(3):
        table_visual = qs_frame.locator('[data-automation-id="grid-block"]')
        count = table_visual.count()
        for idx in range(count):
            try:
                table_visual.nth(idx).hover(timeout=3000)
                time.sleep(1)
                btn = qs_frame.locator('[data-automation-id="analysis_visual_dropdown_menu_button"]')
                if btn.count() > 0:
                    menu_btn = btn.first
                    break
            except (PlaywrightTimeout, Exception):
                continue
        if menu_btn:
            break
        if retry < 2:
            print(f"    Menue-Button nicht gefunden, Versuch {retry + 2}/3...")
            time.sleep(3)

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

    DATA_DIR.mkdir(exist_ok=True)
    download_info.value.save_as(output_path)
    print(f"  CSV gespeichert: {output_path}")
    return output_path


# ---------------------------------------------------------------------------
# Tab Export Workflows
# ---------------------------------------------------------------------------

def export_memberships(page, output_path):
    """Export memberships from the /users page via 'Daten herunterladen' button."""
    print("  Navigiere zu /users...")
    page.goto(USERS_URL)
    try:
        page.wait_for_load_state("networkidle", timeout=30000)
    except PlaywrightTimeout:
        pass
    time.sleep(3)

    # Finde und klicke den "Daten herunterladen" Button
    print("  Klicke 'Daten herunterladen'...")
    with page.expect_download(timeout=30000) as download_info:
        btn = page.locator('[data-class="download-members"], [aria-label="Daten herunterladen"]')
        btn.first.click(timeout=10000)

    DATA_DIR.mkdir(exist_ok=True)
    download_info.value.save_as(output_path)
    print(f"  CSV gespeichert: {output_path}")
    return output_path


def export_intensive_credits(page, output_path):
    """Export intensive credits from the /intensivecredits page."""
    print("  Navigiere zu /intensivecredits...")
    page.goto(INTENSIVE_URL)
    try:
        page.wait_for_load_state("networkidle", timeout=30000)
    except PlaywrightTimeout:
        pass
    time.sleep(3)

    # Finde und klicke den "Daten herunterladen" Button
    print("  Klicke 'Daten herunterladen'...")
    with page.expect_download(timeout=30000) as download_info:
        btn = page.locator('[data-class="download-intensivecredits"], [aria-label="Daten herunterladen"]')
        btn.first.click(timeout=10000)

    DATA_DIR.mkdir(exist_ok=True)
    download_info.value.save_as(output_path)
    print(f"  CSV gespeichert: {output_path}")
    return output_path


def export_tab(page, tab_key):
    """Export a single tab/source."""
    config = TABS[tab_key]
    output_path = DATA_DIR / config["output_file"]

    print(f"\n{'=' * 50}")
    print(f"Export: {config['tab_name']}")
    print(f"{'=' * 50}")

    if config["source"] == "users_page":
        export_memberships(page, output_path)
    elif config["source"] == "intensive_page":
        export_intensive_credits(page, output_path)
    else:
        # QuickSight Tab
        click_tab(page, config["tab_name"])
        if config["needs_timeframe"]:
            set_timeframe(page, days_back=730)
        export_csv(page, output_path)

    return output_path


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Babbel: Report-Export")
    parser.add_argument("--tab", choices=["learners", "app-lessons", "memberships", "intensive-credits", "all"], default="all",
                        help="Welcher Tab exportiert werden soll (Standard: all)")
    parser.add_argument("--headless", action="store_true",
                        help="Browser ohne Fenster ausfuehren")
    args = parser.parse_args()

    # Welche Tabs exportieren?
    if args.tab == "all":
        tabs_to_export = ["learners", "app-lessons", "memberships", "intensive-credits"]
    else:
        tabs_to_export = [args.tab]

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

            # Navigiere nur zu Reports wenn QuickSight-Tabs dabei sind
            qs_tabs = [t for t in tabs_to_export if TABS[t]["source"] == "quicksight"]
            if qs_tabs:
                navigate_to_reports(page)

            exported = []
            for tab_key in tabs_to_export:
                path = export_tab(page, tab_key)
                exported.append(path)

            print(f"\n{'=' * 50}")
            print(f"FERTIG: {len(exported)} Export(s) abgeschlossen")
            for p in exported:
                print(f"  - {p}")
            print(f"{'=' * 50}")

        except Exception as e:
            DATA_DIR.mkdir(exist_ok=True)
            page.screenshot(path=str(DATA_DIR / "error_screenshot.png"))
            print(f"\nFEHLER: {e}")
            print(f"Screenshot: {DATA_DIR / 'error_screenshot.png'}")
            sys.exit(1)
        finally:
            browser.close()


if __name__ == "__main__":
    main()
