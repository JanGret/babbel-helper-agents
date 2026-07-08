---
name: babbel-export
description: Exportiere Daten aus dem Babbel-Portal. Nutze diesen Skill wenn Daten aus Babbel heruntergeladen oder aktualisiert werden sollen.
---

# Babbel: Daten exportieren

## Script: `export_babbel.py`

Exportiert Daten automatisch aus dem Babbel-Portal via Browser-Automatisierung (Playwright).

```bash
py export_babbel.py --tab all              # Alle 4 Quellen (empfohlen)
py export_babbel.py --tab learners         # Nur Learners (mit 2J Timeframe)
py export_babbel.py --tab app-lessons      # Nur App Lessons
py export_babbel.py --tab memberships      # Nur Memberships (/users)
py export_babbel.py --tab intensive-credits # Nur Intensive Credits
py export_babbel.py --headless             # Browser ohne Fenster
```

## Output (in `daten/` Ordner)

| Datei | Inhalt | Quelle |
|-------|--------|--------|
| `daten/learners.csv` | Active Days, Learning Minutes, Activities (2J) | Reports > Learners (QuickSight) |
| `daten/app_lessons.csv` | First & Latest Lesson (Date, Level) | Reports > App lessons (QuickSight) |
| `daten/memberships.csv` | Plan-Typ, Join Date | /users Seite |
| `daten/intensive_credits.csv` | Credits: Total, Used, Remaining | /intensivecredits Seite |

## Fuer Orchestratoren / aufrufende Agenten

| Befehl | Timeout | Dauer |
|--------|---------|-------|
| `--tab memberships` | 300.000ms (5 Min) | ~2-3 Min |
| `--tab intensive-credits` | 300.000ms (5 Min) | ~2-3 Min |
| `--tab learners` | 600.000ms (10 Min) | ~3-5 Min |
| `--tab app-lessons` | 300.000ms (5 Min) | ~2-3 Min |
| `--tab all` | 900.000ms (15 Min) | ~8-12 Min |

## Hinweise

- **Session:** Login-Session in `.session/state.json` (Captcha nur beim ersten Mal)
- **Captcha:** Beim ersten Login muss ein Captcha manuell geloest werden (5 Min Timeout)
- **Headless:** Nicht verwenden wenn Captcha erwartet wird
- **QuickSight:** Learners und App-Lessons nutzen ein eingebettetes QuickSight-Dashboard (langsamer)
- **Direkt-Download:** Memberships und Intensive Credits nutzen einen einfachen Download-Button (schneller)
