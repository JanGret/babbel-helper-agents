---
name: babbel-stats
description: Generiere monatliche Babbel-Statistiken. Nutze diesen Skill wenn der User nach Aktivitaets-Statistiken, Nutzungstrends oder monatlichen Reports fragt.
---

# Babbel: Monatliche Statistiken

## Uebersicht

Generiert monatliche Nutzungsstatistiken fuer den Babbel-Account von Jobcloud:
- Activity % (Anteil aktiver Nutzer pro Monat)
- Learning Time in Minutes (Gesamte Lernzeit)
- Professional Active Users (Aktive App-only Nutzer)
- Intensive Active Users (Aktive Intensive-Nutzer)

## Script: `generate_stats.py`

```bash
py generate_stats.py                     # Fehlende Monate exportieren + Tabelle anzeigen
py generate_stats.py --months 6          # Letzte 6 abgeschlossene Monate
py generate_stats.py --from 2025-01      # Ab Januar 2025
py generate_stats.py --force             # Bereits vorhandene Monate neu exportieren
py generate_stats.py --no-export         # Nur vorhandene Daten anzeigen (kein Browser)
```

## Wie es funktioniert

1. Bestimmt welche abgeschlossenen Monate noch nicht exportiert wurden
2. Oeffnet den Browser und navigiert zum Learners-Tab
3. Fuer jeden fehlenden Monat: Setzt Timeframe auf genau diesen Monat (1. bis letzter Tag) und exportiert die CSV
4. Berechnet Statistiken aus allen vorhandenen Monats-CSVs
5. Gibt eine formatierte Tabelle aus

## Inkrementelles Reporting

- Bereits exportierte Monate werden **uebersprungen** (ausser `--force`)
- Der aktuelle (laufende) Monat wird **nie exportiert** (nur abgeschlossene Monate)
- Fuer monatliches Update reicht: `py generate_stats.py --months 1` (exportiert nur den letzten abgeschlossenen Monat)

## Output

```
BABBEL MONTHLY STATISTICS (Jul 2025 - Jun 2026)
==============================================================================
Monat      Total   Active   Activity%   Lernmin.   Prof.Act.   Intens.Act.
------------------------------------------------------------------------------
2025-07    69      20        29.0%     3416       12          8
2025-08    70      16        22.9%     2747       7           9
...
2026-06    96      16        16.7%     1442       7           9
------------------------------------------------------------------------------
Durchschn.                   21.7%     2456       6           11
==============================================================================
```

Zusaetzlich wird `daten/stats/monthly_stats.json` gespeichert.

## Datenstruktur

```
daten/stats/
├── 2025-07.csv          (Learners-Export fuer Juli 2025)
├── 2025-08.csv
├── ...
├── 2026-06.csv
└── monthly_stats.json   (aggregierte Statistiken)
```

## Laufzeit

- **Pro Monat:** ~2 Minuten (Page-Reload + Timeframe + Export)
- **12 Monate (Erstlauf):** ~20-25 Minuten
- **Folgelaeufe (1 Monat):** ~2 Minuten
- Inkrementell: Nur fehlende Monate werden exportiert

## Typische Szenarien

**"Wie hat sich die Aktivitaet entwickelt?"**
```bash
py generate_stats.py --no-export
```
(Zeigt vorhandene Daten an, kein neuer Export)

**"Aktualisiere die Statistiken"**
```bash
py generate_stats.py --months 1
```
(Exportiert nur den letzten abgeschlossenen Monat und haengt ihn an)

**"Ich brauche die Daten seit Anfang 2025"**
```bash
py generate_stats.py --from 2025-01
```

## Hinweise

- Der aktuelle Monat wird nie exportiert (Daten waeren unvollstaendig)
- Total Users = Anzahl der Zeilen im Export (alle Nutzer die in dem Monat einen Account hatten)
- Professional/Intensive Split basiert auf der aktuellen `memberships.csv`
- Bei Captcha-Problemen: `.session/state.json` loeschen und neu ausfuehren
