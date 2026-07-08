---
name: babbel-stats
description: Generiere monatliche Babbel-Statistiken. Nutze diesen Skill wenn der User nach Aktivitaets-Statistiken, Nutzungstrends oder monatlichen Reports fragt.
---

# Babbel: Monatliche Statistiken

## Script: `generate_stats.py`

```bash
py generate_stats.py                     # Fehlende Monate exportieren + Tabelle
py generate_stats.py --months 1          # Nur letzter abgeschlossener Monat
py generate_stats.py --months 6          # Letzte 6 Monate
py generate_stats.py --from 2025-07      # Ab Juli 2025
py generate_stats.py --force             # Bereits vorhandene neu exportieren
py generate_stats.py --no-export         # Nur vorhandene Daten anzeigen (kein Browser)
```

## Was es berechnet (pro Monat)

- **Activity %** — Anteil Nutzer mit >= 1 Activity
- **Learning Minutes** — Gesamte Lernzeit aller Nutzer
- **Professional Active** — Aktive App-only Nutzer
- **Intensive Active** — Aktive Intensive-Nutzer (1:1 Lektionen)

## Automatische Abhaengigkeiten

Das Script prueft und aktualisiert automatisch:
- `memberships.csv` wird automatisch heruntergeladen wenn sie fehlt oder aelter als 7 Tage ist (fuer den Professional/Intensive Split)
- Kein separater Aufruf von `export_babbel.py --tab memberships` noetig

## Inkrementelles Reporting

- Bereits exportierte Monate werden uebersprungen (ausser `--force`)
- Der aktuelle (laufende) Monat wird NIE exportiert
- Daten liegen in `daten/stats/YYYY-MM.csv`

## Fuer Orchestratoren / aufrufende Agenten

| Szenario | Befehl | Timeout |
|----------|--------|---------|
| Monatliches Update (1 Monat) | `py generate_stats.py --months 1` | 600.000ms (10 Min) |
| Erstlauf (12 Monate, Ordner leer) | `py generate_stats.py --from 2025-07` | 1.800.000ms (30 Min) |
| Nur anzeigen (kein Browser) | `py generate_stats.py --no-export` | 120.000ms (Standard) |

## Output

Konsolen-Tabelle + `daten/stats/monthly_stats.json`
