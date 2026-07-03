---
name: babbel-nutzer-verwaltung
description: Verwalte Babbel-Nutzer bei Jobcloud. Nutze diesen Skill wenn der User nach inaktiven Nutzern, Empfehlungen zum Loeschen, Diskrepanzen, Datenexport oder Babbel-Lizenzverwaltung fragt.
---

# Babbel: Nutzerverwaltung fuer Jobcloud L&D

## Uebersicht

Jobcloud hat 100 Babbel-Lizenzslots. Dieses Skill hilft dabei:
- Alle relevanten Daten automatisch aus dem Babbel-Portal zu exportieren
- Inaktive Nutzer zu identifizieren
- Empfehlungen zum Loeschen zu generieren (basierend auf 5 Datenquellen)
- Diskrepanzen zwischen Babbel und der manuellen SharePoint-Excel aufzudecken

## Verfuegbare Scripts

### `export_babbel.py` (Daten-Export)

Exportiert Daten automatisch aus dem Babbel-Portal. Nutzt Playwright (Browser-Automatisierung).

```bash
py export_babbel.py --tab all              # Alle 4 Quellen (empfohlen)
py export_babbel.py --tab learners         # Nur Learners (mit 2J Timeframe)
py export_babbel.py --tab app-lessons      # Nur App Lessons
py export_babbel.py --tab memberships      # Nur Memberships (/users)
py export_babbel.py --tab intensive-credits # Nur Intensive Credits
py export_babbel.py --headless             # Browser ohne Fenster
```

**Output (in `daten/` Ordner):**
- `daten/learners.csv` — Active Days, Learning Minutes, Activities (Zeitraum: 2 Jahre)
- `daten/app_lessons.csv` — First & Latest Lesson (Date, Level, Language)
- `daten/memberships.csv` — Plan-Typ (professional/intensive), Join Date
- `daten/intensive_credits.csv` — Credits: Total, Used, Remaining

**Quellen:**
| Tab | URL / Quelle | Methode |
|-----|-------------|---------|
| learners | Reports > Learners (QuickSight) | Hover-Menue > Export to CSV |
| app-lessons | Reports > App lessons (QuickSight) | Hover-Menue > Export to CSV |
| memberships | /organizations/jobcloud/users | "Daten herunterladen" Button |
| intensive-credits | /organizations/jobcloud/intensivecredits | "Daten herunterladen" Button |

### `consolidate.py` (Analyse & Empfehlungen)

Fuehrt alle Datenquellen zusammen, berechnet einen Inactivity-Score und gibt Empfehlungen.

```bash
py consolidate.py                        # Alle Empfehlungen
py consolidate.py --context professional  # Nur Professional-Nutzer
py consolidate.py --context intensive     # Nur Intensive-Nutzer
```

**Output:**
- Diskrepanzen zwischen SharePoint und Babbel (stdout)
- Empfehlungsliste mit Scoring und Begruendungen (stdout)
- `exports/consolidated_profiles.json` — Alle Profile als JSON

### `get_inactive_users.py` (Legacy)

Aelteres Script, nur Learners-Tab. Nutze stattdessen `export_babbel.py --tab learners`.

## Typischer Workflow

```bash
# 1. Frische Daten aus Babbel holen (alle 4 automatisierbaren Quellen)
py export_babbel.py --tab all

# 2. Analyse mit Empfehlungen
py consolidate.py

# 3. Kontext-spezifisch (wenn ein Slot gebraucht wird)
py consolidate.py --context professional
py consolidate.py --context intensive
```

## Datenquellen

| Datei | Quelle | Automatisiert? |
|-------|--------|:--------------:|
| `daten/learners.csv` | Babbel Reports > Learners | Ja |
| `daten/app_lessons.csv` | Babbel Reports > App lessons | Ja |
| `daten/memberships.csv` | Babbel /users | Ja |
| `daten/intensive_credits.csv` | Babbel /intensivecredits | Ja |
| SharePoint-Excel (OneDrive Sync) | SharePoint > HR > Babbel User List.xlsx | Ja (via Sync) |

**SharePoint-Excel:** Wird direkt vom lokalen OneDrive-Sync-Pfad gelesen. Der Pfad ist konfigurierbar via `SHAREPOINT_EXCEL_PATH` in `.env`. Fallback auf `daten/Babbel User List*.xlsx` falls der Sync-Pfad nicht existiert.

## Scoring-Logik

| Bedingung | Punkte |
|-----------|--------|
| Letzte Lektion > 12 Monate (oder nie) | +35 |
| 0 Active Days in 2 Jahren | +25 |
| Letzte Lektion > 6 Monate | +15 |
| Keine Intensive Credits remaining | +10 |
| Nur Professional (kein Intensive-Plan) | +10 |
| 0 Learning Minutes | +5 |

**Overrides:**
- Admin-Accounts (Kyra, Alla, Jan) → Score = 0, immer "BEHALTEN"
- Hat remaining Credits > 0 → Score max 50
- SharePoint Status "Deleted" → wird uebersprungen
- SharePoint Status "Invited" → Score = 0

**Empfehlungskategorien:**
- Score >= 80 → "LOESCHEN empfohlen"
- Score 50-79 → "PRUEFEN"
- Score < 50 → "BEHALTEN"

## Typische Szenarien

**"Wer ist am inaktivsten?"**
```bash
py consolidate.py
```

**"Ich muss einen Slot frei machen fuer einen neuen Professional-Nutzer":**
```bash
py consolidate.py --context professional
```

**"Jemand moechte Intensive — wer ist am inaktivsten?":**
```bash
py consolidate.py --context intensive
```

**"Gibt es Unterschiede zwischen unserer Excel und Babbel?":**
```bash
py consolidate.py
```
→ Zeigt die Diskrepanzen-Sektion (fehlende Nutzer, Status-Widersprueche).

**"Hol frische Daten und zeig mir die Empfehlungen":**
```bash
py export_babbel.py --tab all
py consolidate.py
```

## Technische Hinweise

- **Session:** Login-Session wird in `.session/state.json` gespeichert (Captcha nur beim ersten Mal)
- **Captcha:** Beim ersten Login muss ein Captcha manuell im Browser geloest werden (5 Min Timeout)
- **Viewport:** 1440x900 (QuickSight braucht feste Groesse fuer korrekte Darstellung)
- **QuickSight:** Reports werden in einem iframe gerendert (Amazon QuickSight embedded)
- **Timeframe:** Nur der Learners-Tab braucht einen Custom-Date-Range (wird per React-Hack gesetzt)
- **DOM-Reihenfolge:** Im Timeframe-Widget ist nth(0) das "to"-Feld und nth(1) das "from"-Feld
- **Plan-Typen:** `professional` = App-only, `private-classes-9d148a1c` = Intensive (1:1 Lektionen)
- **SharePoint-Excel:** Wird direkt vom lokalen OneDrive-Sync-Pfad gelesen (kein manuelles Kopieren noetig)
- **Sync-Pfad:** Konfigurierbar via `SHAREPOINT_EXCEL_PATH` in `.env`
