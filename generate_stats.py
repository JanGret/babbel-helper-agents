"""
Babbel Stats: Monatliche Statistiken generieren.

Exportiert fuer jeden Monat den Learners-Report und berechnet:
- Activity % (Nutzer mit >= 1 Activity)
- Learning Time in Minutes (Summe)
- Professional Active Users
- Intensive Active Users

Nutzung:
    py generate_stats.py                     # Fehlende Monate exportieren + Tabelle
    py generate_stats.py --months 6          # Letzte 6 abgeschlossene Monate
    py generate_stats.py --from 2025-07      # Ab Juli 2025
    py generate_stats.py --force             # Vorhandene Monate ueberschreiben
    py generate_stats.py --no-export         # Nur vorhandene Daten anzeigen

Voraussetzungen:
    - daten/memberships.csv (fuer Professional/Intensive Split)
    - Fuer Export: .env mit BABBEL_EMAIL und BABBEL_PASSWORD
"""

import argparse
import calendar
import csv
import io
import json
import os
import sys
import time
from datetime import datetime, date
from pathlib import Path

from dotenv import load_dotenv
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

from babbel_utils import read_pool_info, print_pool_info

load_dotenv()
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

DATA_DIR = Path(__file__).parent / "daten"
STATS_DIR = DATA_DIR / "stats"


# ---------------------------------------------------------------------------
# Month Logic
# ---------------------------------------------------------------------------

def last_completed_month():
    """Return the last fully completed month as (year, month)."""
    today = date.today()
    if today.month == 1:
        return (today.year - 1, 12)
    return (today.year, today.month - 1)


def month_range(start_ym, end_ym):
    """Generate list of (year, month) tuples from start to end (inclusive)."""
    months = []
    y, m = start_ym
    while (y, m) <= end_ym:
        months.append((y, m))
        if m == 12:
            y += 1
            m = 1
        else:
            m += 1
    return months


def last_n_months(n):
    """Return the last N completed months as list of (year, month)."""
    end = last_completed_month()
    # Go back n-1 months from end
    y, m = end
    start_months = []
    for _ in range(n):
        start_months.append((y, m))
        if m == 1:
            y -= 1
            m = 12
        else:
            m -= 1
    start_months.reverse()
    return start_months


def month_label(ym):
    """Format (year, month) as 'YYYY-MM'."""
    return f"{ym[0]:04d}-{ym[1]:02d}"


def month_csv_path(ym):
    """Return the path for a month's CSV file."""
    return STATS_DIR / f"{month_label(ym)}.csv"


def determine_months_to_export(args):
    """Determine which months need to be exported based on arguments."""
    end_ym = last_completed_month()

    if args.from_month:
        # Parse --from YYYY-MM
        parts = args.from_month.split("-")
        start_ym = (int(parts[0]), int(parts[1]))
        months = month_range(start_ym, end_ym)
    elif args.months:
        months = last_n_months(args.months)
    else:
        months = last_n_months(12)

    # Filter: nur abgeschlossene Monate
    months = [m for m in months if m <= end_ym]

    # Inkrementell: ueberspringe bereits vorhandene (ausser --force)
    if not args.force:
        months = [m for m in months if not month_csv_path(m).exists()]

    return months


# ---------------------------------------------------------------------------
# Memberships Loader
# ---------------------------------------------------------------------------

def load_memberships():
    """Load memberships for Professional/Intensive classification."""
    candidates = [
        DATA_DIR / "memberships.csv",
    ]
    # Fallback auf Glob
    import glob
    candidates.extend(glob.glob(str(DATA_DIR / "memberships*")))

    filepath = next((f for f in candidates if Path(f).exists()), None)
    if not filepath:
        print("  WARNUNG: memberships.csv nicht gefunden. Plan-Split nicht moeglich.")
        return {}

    data = {}
    with open(filepath, "r", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            email = (row.get("Email") or "").strip().lower()
            if not email:
                continue
            plan_raw = (row.get("Plan") or "").strip()
            if "private-classes" in plan_raw:
                data[email] = "intensive"
            else:
                data[email] = "professional"
    return data


# ---------------------------------------------------------------------------
# Stats Calculation
# ---------------------------------------------------------------------------

def calculate_month_stats(csv_path, memberships):
    """Calculate statistics for a single month's CSV export."""
    total_users = 0
    active_users = 0
    learning_minutes_total = 0.0
    professional_active = 0
    intensive_active = 0

    with open(csv_path, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            total_users += 1
            email = (row.get("E-mail") or row.get("E-Mail") or row.get("Email") or "").strip().lower()

            try:
                activities = int(row.get("Activities", 0) or 0)
            except (ValueError, TypeError):
                activities = 0

            try:
                learning_min = float(row.get("Learning minutes", 0) or 0)
            except (ValueError, TypeError):
                learning_min = 0.0

            learning_minutes_total += learning_min

            if activities > 0:
                active_users += 1
                plan = memberships.get(email, "professional")
                if plan == "intensive":
                    intensive_active += 1
                else:
                    professional_active += 1

    activity_pct = (active_users / total_users * 100) if total_users > 0 else 0.0

    return {
        "total_users": total_users,
        "active_users": active_users,
        "activity_pct": round(activity_pct, 1),
        "learning_minutes": round(learning_minutes_total),
        "professional_active": professional_active,
        "intensive_active": intensive_active,
    }


def calculate_all_stats(months_available, memberships):
    """Calculate stats for all available month CSVs."""
    stats = []
    for ym in sorted(months_available):
        csv_path = month_csv_path(ym)
        if csv_path.exists():
            month_stats = calculate_month_stats(csv_path, memberships)
            month_stats["month"] = month_label(ym)
            stats.append(month_stats)
    return stats


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------

def print_stats_table(stats):
    """Print formatted statistics table."""
    if not stats:
        print("\nKeine Statistiken vorhanden.")
        return

    first = stats[0]["month"]
    last = stats[-1]["month"]

    print(f"\n{'=' * 78}")
    print(f"BABBEL MONTHLY STATISTICS ({first} bis {last})")
    print(f"{'=' * 78}")
    print(f"{'Monat':<10} {'Total':<7} {'Active':<8} {'Activity%':<11} {'Lernmin.':<10} {'Prof.Act.':<11} {'Intens.Act.'}")
    print(f"{'-' * 78}")

    total_activity_pct = 0
    total_learning_min = 0
    total_prof = 0
    total_intens = 0

    for s in stats:
        print(f"{s['month']:<10} {s['total_users']:<7} {s['active_users']:<8} "
              f"{s['activity_pct']:>5.1f}%     {s['learning_minutes']:<10} "
              f"{s['professional_active']:<11} {s['intensive_active']}")
        total_activity_pct += s["activity_pct"]
        total_learning_min += s["learning_minutes"]
        total_prof += s["professional_active"]
        total_intens += s["intensive_active"]

    n = len(stats)
    print(f"{'-' * 78}")
    print(f"{'Durchschn.':<10} {'':7} {'':8} "
          f"{total_activity_pct / n:>5.1f}%     {total_learning_min // n:<10} "
          f"{total_prof // n:<11} {total_intens // n}")
    print(f"{'=' * 78}")
    print()
    print("  Hinweis: Geloeschte Nutzer fehlen auch in historischen Monaten. Dadurch ist")
    print("  Total Users fuer aeltere Monate etwas zu niedrig und Activity% etwas zu hoch.")


def save_stats_json(stats):
    """Save stats to JSON file."""
    STATS_DIR.mkdir(parents=True, exist_ok=True)
    output_path = STATS_DIR / "monthly_stats.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)
    print(f"\nJSON gespeichert: {output_path}")


# ---------------------------------------------------------------------------
# Browser Automation
# ---------------------------------------------------------------------------

BABBEL_BASE_URL = "https://my.babbel.com"
REPORTS_URL = f"{BABBEL_BASE_URL}/de/organizations/jobcloud/reports/active"
SESSION_DIR = Path(__file__).parent / ".session"


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

    try:
        page.wait_for_url("**/organizations/**", timeout=15000)
        print("  Bereits eingeloggt (gespeicherte Session).")
        return
    except PlaywrightTimeout:
        pass

    email_input = page.locator('input[type="email"], input[name="email"], input[id*="email"]')
    email_input.first.wait_for(state="visible", timeout=15000)
    email_input.first.fill(email)
    page.locator('button:has-text("Weiter"), button:has-text("Continue"), [type="submit"]').first.click()

    pw_input = page.locator('input[type="password"]')
    pw_input.first.wait_for(state="visible", timeout=15000)
    pw_input.first.fill(password)
    page.locator('button:has-text("Einloggen"), button:has-text("Log in"), button:has-text("Weiter"), [type="submit"]').first.click()

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


def _get_qs_frame(page):
    """Find the QuickSight iframe."""
    for frame in page.frames:
        if "quicksight" in frame.url:
            return frame
    return None


def navigate_to_learners(page):
    """Navigate to Reports > Learners tab."""
    print("Navigiere zu Reports > Learners...")
    page.goto(REPORTS_URL)
    try:
        page.wait_for_load_state("networkidle", timeout=30000)
    except PlaywrightTimeout:
        pass
    time.sleep(5)

    for frame in page.frames:
        try:
            frame.locator('text="Learners"').first.click(timeout=5000)
            print("  Learners-Tab geklickt.")
            time.sleep(5)
            return
        except (PlaywrightTimeout, Exception):
            continue
    print("  WARNUNG: Learners-Tab nicht gefunden!")


def select_custom_dates(page):
    """Select 'Custom dates' in the Timeframe dropdown (only needed once)."""
    qs_frame = _get_qs_frame(page)
    if not qs_frame:
        return False

    try:
        dropdown = qs_frame.locator('[data-automation-context="Timeframe"][data-automation-id="sheet_control_value"]')
        dropdown.first.dispatch_event("mousedown")
    except PlaywrightTimeout:
        print("  WARNUNG: Timeframe-Dropdown nicht gefunden.")
        return False
    time.sleep(3)

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
    time.sleep(2)
    return result


def set_month_timeframe(page, year, month):
    """Set timeframe to a specific month (both from and to fields)."""
    qs_frame = _get_qs_frame(page)
    if not qs_frame:
        return False

    last_day = calendar.monthrange(year, month)[1]
    from_date = f"{month:02d}/01/{year}"
    to_date = f"{month:02d}/{last_day:02d}/{year}"

    # Setze erst "to" (inputs[0]), dann "from" (inputs[1])
    # Jedes Feld einzeln setzen mit separatem blur dazwischen
    # Das ist der Ansatz der beim export_babbel.py funktioniert hat

    # Schritt 1: "to"-Feld setzen
    qs_frame.evaluate('''
        (dateValue) => {
            const inputs = document.querySelectorAll('[data-automation-id="date_picker_0"]');
            if (inputs.length < 2) return;
            const input = inputs[0];  // "to" field
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
    ''', to_date)
    time.sleep(2)

    # Schliesse Popovers
    qs_frame.evaluate('''
        () => {
            document.querySelectorAll('[role="presentation"][class*="MuiPopover"]').forEach(p => {
                const backdrop = p.querySelector('[aria-hidden="true"]');
                if (backdrop) backdrop.click();
            });
        }
    ''')
    time.sleep(1)

    # Schritt 2: "from"-Feld setzen
    qs_frame.evaluate('''
        (dateValue) => {
            const inputs = document.querySelectorAll('[data-automation-id="date_picker_0"]');
            if (inputs.length < 2) return;
            const input = inputs[1];  // "from" field
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
    ''', from_date)
    time.sleep(2)

    # Schliesse Popovers
    qs_frame.evaluate('''
        () => {
            document.querySelectorAll('[role="presentation"][class*="MuiPopover"]').forEach(p => {
                const backdrop = p.querySelector('[aria-hidden="true"]');
                if (backdrop) backdrop.click();
            });
        }
    ''')

    return True


def export_table_csv(page, output_path):
    """Export the current table as CSV via hover menu (with retry)."""
    qs_frame = _get_qs_frame(page)
    if not qs_frame:
        raise Exception("QuickSight-Frame nicht gefunden")

    # Find menu button via hover with retry
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
            time.sleep(3)

    if not menu_btn:
        raise Exception("Menue-Button nicht gefunden")

    # Click menu button
    menu_btn.scroll_into_view_if_needed(timeout=10000)
    time.sleep(1)
    menu_btn = qs_frame.locator('[data-automation-id="analysis_visual_dropdown_menu_button"]').first
    menu_btn.hover(timeout=10000, force=True)
    time.sleep(1)
    menu_btn.click(timeout=10000, force=True)
    time.sleep(2)

    # Click "Export to CSV"
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

    STATS_DIR.mkdir(parents=True, exist_ok=True)
    download_info.value.save_as(output_path)
    return output_path


def export_months(months_to_export):
    """Export Learners CSV for each month via browser automation."""
    print(f"\nExportiere {len(months_to_export)} Monat(e)...")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
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

            # Memberships aktualisieren wenn noetig (< 7 Tage alt)
            memberships_path = DATA_DIR / "memberships.csv"
            memberships_stale = True
            if memberships_path.exists():
                age_days = (datetime.now() - datetime.fromtimestamp(memberships_path.stat().st_mtime)).days
                memberships_stale = age_days >= 7

            if memberships_stale:
                print("\n  Memberships aktualisieren (fuer Professional/Intensive Split)...")
                page.goto(f"{BABBEL_BASE_URL}/de/organizations/jobcloud/users")
                try:
                    page.wait_for_load_state("networkidle", timeout=30000)
                except PlaywrightTimeout:
                    pass
                time.sleep(3)
                try:
                    with page.expect_download(timeout=30000) as download_info:
                        btn = page.locator('[data-class="download-members"], [aria-label="Daten herunterladen"]')
                        btn.first.click(timeout=10000)
                    DATA_DIR.mkdir(exist_ok=True)
                    download_info.value.save_as(memberships_path)
                    print(f"  Memberships gespeichert: {memberships_path.name}")
                except Exception as e:
                    print(f"  WARNUNG: Memberships-Download fehlgeschlagen: {e}")

            exported = []
            for i, ym in enumerate(months_to_export):
                year, month = ym
                label = month_label(ym)
                print(f"\n  [{i+1}/{len(months_to_export)}] {label}...")

                # Jedes Mal neu laden — QuickSight akzeptiert Timeframe-Aenderungen
                # nur beim ersten Mal pro Seitenaufruf zuverlaessig
                navigate_to_learners(page)
                if not select_custom_dates(page):
                    print(f"    WARNUNG: 'Custom dates' nicht ausgewaehlt.")
                    continue
                time.sleep(2)

                # Set timeframe to this month
                if not set_month_timeframe(page, year, month):
                    print(f"    WARNUNG: Timeframe fuer {label} konnte nicht gesetzt werden.")
                    continue

                # Wait for data to reload
                time.sleep(5)

                # Export
                output_path = month_csv_path(ym)
                try:
                    export_table_csv(page, output_path)
                    print(f"    CSV gespeichert: {output_path.name}")
                    exported.append(ym)
                except Exception as e:
                    print(f"    FEHLER beim Export: {e}")
                    continue

            print(f"\n  {len(exported)}/{len(months_to_export)} Monate erfolgreich exportiert.")

            # Pool-Info auslesen (Browser ist noch offen)
            print("\n  Lese Intensive Credits Pool-Info...")
            pool_info = read_pool_info(page)
            print_pool_info(pool_info)

            return exported

        except Exception as e:
            STATS_DIR.mkdir(parents=True, exist_ok=True)
            page.screenshot(path=str(STATS_DIR / "error_screenshot.png"))
            print(f"\nFEHLER: {e}")
            print(f"Screenshot: {STATS_DIR / 'error_screenshot.png'}")
            return []
        finally:
            browser.close()


def fetch_pool_info_standalone():
    """Oeffnet einen kurzen Browser nur um die Pool-Info auszulesen."""
    print("\nLese Intensive Credits Pool-Info...")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        SESSION_DIR.mkdir(exist_ok=True)
        context = browser.new_context(
            storage_state=str(SESSION_DIR / "state.json") if (SESSION_DIR / "state.json").exists() else None,
            viewport={"width": 1440, "height": 900},
        )
        page = context.new_page()
        try:
            login(page)
            context.storage_state(path=str(SESSION_DIR / "state.json"))
            pool_info = read_pool_info(page)
            print_pool_info(pool_info)
        except Exception as e:
            print(f"  Pool-Info konnte nicht gelesen werden: {e}")
        finally:
            browser.close()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Babbel: Monatliche Statistiken")
    parser.add_argument("--months", type=int, default=12,
                        help="Anzahl abgeschlossener Monate (Standard: 12)")
    parser.add_argument("--from", dest="from_month", type=str,
                        help="Start-Monat im Format YYYY-MM")
    parser.add_argument("--force", action="store_true",
                        help="Vorhandene Monate neu exportieren")
    parser.add_argument("--no-export", action="store_true",
                        help="Nur vorhandene Daten anzeigen, kein Browser")
    args = parser.parse_args()

    STATS_DIR.mkdir(parents=True, exist_ok=True)

    # Welche Monate brauchen wir?
    end_ym = last_completed_month()
    if args.from_month:
        parts = args.from_month.split("-")
        start_ym = (int(parts[0]), int(parts[1]))
        all_months = month_range(start_ym, end_ym)
    else:
        all_months = last_n_months(args.months)

    print(f"Zeitraum: {month_label(all_months[0])} bis {month_label(all_months[-1])}")
    print(f"  Letzter abgeschlossener Monat: {month_label(end_ym)}")

    # Welche sind bereits vorhanden?
    available = [m for m in all_months if month_csv_path(m).exists()]
    missing = [m for m in all_months if not month_csv_path(m).exists()]

    if args.force:
        missing = all_months
        available = []

    print(f"  Vorhanden: {len(available)} Monat(e)")
    print(f"  Fehlend: {len(missing)} Monat(e)")

    # Export falls noetig
    if missing and not args.no_export:
        exported = export_months(missing)
        # Nach Export: available aktualisieren
        available = [m for m in all_months if month_csv_path(m).exists()]

    if not available:
        print("\nKeine Monats-Daten vorhanden. Fuehre zuerst einen Export aus.")
        return

    # Statistiken berechnen
    print(f"\nBerechne Statistiken fuer {len(available)} Monat(e)...")
    memberships = load_memberships()
    if memberships:
        print(f"  Memberships geladen: {len(memberships)} Nutzer")

    stats = calculate_all_stats(available, memberships)
    print_stats_table(stats)
    save_stats_json(stats)

    # Pool-Info: Nur im --no-export Fall separat holen
    # (Im Export-Fall wird die Pool-Info bereits in export_months() ausgegeben)
    if args.no_export or not missing:
        fetch_pool_info_standalone()


if __name__ == "__main__":
    main()
