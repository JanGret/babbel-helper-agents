---
name: babbel-recommendations
description: Analysiere Babbel-Nutzer und gib Empfehlungen zum Loeschen. Nutze diesen Skill wenn der User nach inaktiven Nutzern, Loeschkandidaten oder Diskrepanzen fragt.
---

# Babbel: Nutzer-Analyse & Empfehlungen

## Script: `consolidate.py`

```bash
py consolidate.py                        # Alle Empfehlungen
py consolidate.py --context professional  # Nur Professional-Nutzer
py consolidate.py --context intensive     # Nur Intensive-Nutzer
```

## Was es tut

1. Liest 5 Datenquellen (Learners, App-Lessons, Credits, Memberships, SharePoint-Excel)
2. Berechnet einen Inactivity-Score (0-100) pro Nutzer
3. Zeigt Diskrepanzen zwischen SharePoint und Babbel
4. Gibt Empfehlungen: LOESCHEN / PRUEFEN / BEHALTEN

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
- Admin-Accounts (Kyra, Alla, Jan) → Score = 0
- Hat remaining Credits > 0 → Score max 50
- Status "Deleted" → uebersprungen
- Status "Invited" → Score = 0

**Empfehlungen:** Score >= 80 → LOESCHEN | 50-79 → PRUEFEN | < 50 → BEHALTEN

## Fuer Orchestratoren / aufrufende Agenten

| Befehl | Timeout | Braucht Browser? |
|--------|---------|:----------------:|
| `py consolidate.py` | 120.000ms (Standard) | Nein |
| `py consolidate.py --context professional` | 120.000ms (Standard) | Nein |

**Voraussetzung:** Aktuelle Daten im `daten/`-Ordner. Falls veraltet, vorher `py export_babbel.py --tab all` ausfuehren (Skill: babbel-export). WICHTIG: Immer `--tab all` in EINEM Aufruf verwenden – NIEMALS einzelne Tabs nacheinander aufrufen (oeffnet sonst pro Aufruf ein neues Browser-Fenster).

## Typische Szenarien

- "Wer ist am inaktivsten?" → `py consolidate.py`
- "Ich brauche einen Slot fuer Professional" → `py consolidate.py --context professional`
- "Gibt es Unterschiede zur Excel?" → `py consolidate.py` (zeigt Diskrepanzen-Sektion)
