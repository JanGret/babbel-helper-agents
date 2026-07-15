"""
Babbel Utilities: Gemeinsame Hilfsfunktionen fuer Babbel-Scripts.

Wird von refill_credits.py und generate_stats.py importiert.
"""

import re
import time

from playwright.sync_api import TimeoutError as PlaywrightTimeout

BABBEL_BASE_URL = "https://my.babbel.com"
INTENSIVE_URL = f"{BABBEL_BASE_URL}/en/organizations/jobcloud/intensivecredits"


def read_pool_info(page):
    """Liest die Credits-Pool-Info von der Intensive Credits Seite.

    Erwartet dass die Seite /intensivecredits bereits geladen ist
    oder navigiert selbst dorthin falls noetig.

    Returns:
        dict mit keys: total, assigned, remaining (jeweils int)
        oder None bei Fehler
    """
    # Sicherstellen dass wir auf der richtigen Seite sind
    if "intensivecredits" not in page.url:
        page.goto(INTENSIVE_URL)
        try:
            page.wait_for_load_state("networkidle", timeout=30000)
        except PlaywrightTimeout:
            pass
        time.sleep(3)

    try:
        # Alle sichtbaren Text-Inhalte auf der Seite nach den Pool-Werten durchsuchen
        # Die Seite zeigt: "500 total credits", "340 ... assigned", "160 remaining credits"
        page_text = page.text_content("body") or ""

        total = _extract_number(page_text, r"(\d+)\s*total\s*credits")
        assigned = _extract_number(page_text, r"(\d+)\s*(?:Live\s*credits?\s*\(Intensive\)\s*)?assigned")
        remaining = _extract_number(page_text, r"(\d+)\s*remaining\s*credits?")

        if total is not None and remaining is not None:
            # Falls assigned nicht direkt gefunden, berechnen
            if assigned is None:
                assigned = total - remaining

            return {
                "total": total,
                "assigned": assigned,
                "remaining": remaining,
            }

        return None

    except Exception:
        return None


def print_pool_info(pool_info):
    """Gibt die Pool-Info formatiert aus.

    Args:
        pool_info: dict von read_pool_info() oder None
    """
    if pool_info is None:
        print("  Pool-Info: Konnte nicht ausgelesen werden.")
        return

    print(
        f"  Intensive Credits Pool: "
        f"{pool_info['remaining']} remaining / "
        f"{pool_info['total']} total "
        f"({pool_info['assigned']} assigned)"
    )


def _extract_number(text, pattern):
    """Extrahiert eine Zahl aus Text mittels Regex-Pattern.

    Args:
        text: Der zu durchsuchende Text
        pattern: Regex mit einer Capture-Group fuer die Zahl

    Returns:
        int oder None
    """
    match = re.search(pattern, text, re.IGNORECASE)
    if match:
        try:
            return int(match.group(1))
        except (ValueError, IndexError):
            return None
    return None
