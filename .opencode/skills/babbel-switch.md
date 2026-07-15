---
name: babbel-switch
description: Wechsle einen Professional-Nutzer auf den Intensive-Plan (Private Classes). Nutze diesen Skill wenn ein bestehender Nutzer auf Intensive umgestellt, upgegradet oder fuer Private Classes freigeschaltet werden soll.
---

# Babbel: Plan wechseln (Professional → Intensive)

## Script: `switch_plan.py`

```bash
py switch_plan.py --email user@example.com             # Switch + 10 Start-Credits
py switch_plan.py --email user@example.com --credits 20  # Switch + 20 Start-Credits
```

## Was es tut

1. Prueft ob der User existiert und noch nicht Intensive ist
2. Loggt sich im Babbel-Portal ein (Session wird wiederverwendet)
3. Navigiert zur Users-Seite (`/users`)
4. Sucht den User per E-Mail, waehlt ihn per Checkbox aus
5. Klickt "Switch Plan"
6. Waehlt "Private Classes" (= Intensive)
7. Klickt "Continue"
8. Klickt "Confirm new Plan"
9. Navigiert zur Intensive Credits Seite
10. Fuellt 10 Start-Credits nach
11. Aktualisiert die SharePoint-Excel (Spalte E = "x", Spalte F = Credits, Spalte G = Datum)
12. Gibt Pool-Status aus

## Exit-Codes

| Code | Bedeutung |
|------|-----------|
| 0 | Erfolg (Plan gewechselt + Credits aufgefuellt) |
| 1 | Fehler (User nicht gefunden, Login fehlgeschlagen, etc.) |
| 2 | User ist bereits Intensive (kein Switch noetig) |

## Fuer Orchestratoren / aufrufende Agenten

| Befehl | Timeout | Braucht Browser? |
|--------|---------|:----------------:|
| `py switch_plan.py --email ...` | 600.000ms (10 Min) | Ja |

## Agent-Verhalten

- IMMER vorher pruefen ob der User bereits Intensive ist (Exit-Code 2)
- Falls bereits Intensive: "User hat bereits den Intensive-Plan. Moechtest du Credits nachfuellen?"
  → Dann Skill `babbel-refill` verwenden
- Standard: 10 Start-Credits nach dem Switch

## Typische Szenarien

- "Stelle max@jobcloud.ch auf Intensive um" → `py switch_plan.py --email max@jobcloud.ch`
- "Upgrade Florian auf Private Classes" → `py switch_plan.py --email florian.vallet@jobcloud.ch`
- "Plan wechseln fuer anna@jobcloud.ch" → `py switch_plan.py --email anna@jobcloud.ch`

## Hinweise

- **Session:** Login-Session in `.session/state.json` (Captcha nur beim ersten Mal)
- **Captcha:** Beim ersten Login muss ein Captcha manuell geloest werden (5 Min Timeout)
- **Headless:** Nicht verwenden wenn Captcha erwartet wird
- **Fehler-Screenshot:** Bei Problemen wird `daten/switch_error_screenshot.png` gespeichert
- **Credits:** Werden im selben Browser-Fenster direkt nach dem Switch aufgefuellt (effizient, kein zweiter Browser-Start)
- **Excel:** Spalte D (Professional) bleibt unveraendert — Intensive ist ein Addon zu Professional
