---
name: babbel-refill
description: Verwalte Intensive Credits fuer Babbel-Nutzer (hinzufuegen oder entfernen). Nutze diesen Skill wenn der User Credits nachfuellen, auffuellen, hinzufuegen, entfernen oder wegnehmen will.
---

# Babbel: Intensive Credits verwalten

## Script: `refill_credits.py`

```bash
# Credits hinzufuegen
py refill_credits.py --email user@example.com             # 10 Credits hinzufuegen (Standard)
py refill_credits.py --email user@example.com --credits 20  # 20 Credits hinzufuegen

# Credits entfernen
py refill_credits.py --email user@example.com --remove      # 10 Credits entfernen
py refill_credits.py --email user@example.com --remove --credits 5  # 5 Credits entfernen

# Pruefung ueberspringen
py refill_credits.py --email user@example.com --force       # Keine Remaining-Pruefung
```

## Was es tut

1. Loggt sich im Babbel-Portal ein (Session wird wiederverwendet)
2. Navigiert zur Intensive Credits Seite (`/intensivecredits`)
3. Sucht den Nutzer per E-Mail im Suchfeld
4. **Prueft aktuelle Remaining Credits** (nur beim Hinzufuegen)
5. Waehlt den Nutzer per Checkbox aus
6. Klickt "Add Credits" oder "Remove Credits" (je nach Modus)
7. Setzt die gewuenschte Anzahl im Popup-Eingabefeld
8. Klickt "Confirm"
9. Gibt den aktuellen **Pool-Status** aus (remaining / total / assigned)

## Credits-Pruefung (nur beim Hinzufuegen)

Das Script prueft vor dem Auffuellen, ob der Nutzer bereits genug Credits hat:

### Soft-Warnung (Exit-Code 2)
- Wenn der Nutzer **>= 5 Credits remaining** hat
- Script bricht ab mit Empfehlung (z.B. "Nutzer hat 8 remaining, nur 2 auffuellen auf 10")
- Agent soll dem User die Optionen zeigen und fragen was er will

### Hard-Cap (Exit-Code 3)
- Wenn `remaining + hinzuzufuegende Credits > 20` waere
- Script bricht ab mit Hinweis auf Maximum
- Agent soll dem User das Limit erklaeren

### Override mit `--force`
- Ueberspringt beide Pruefungen
- Nur verwenden wenn der User explizit bestaetigt

## Agent-Verhalten bei Exit-Codes

| Exit-Code | Bedeutung | Agent-Aktion |
|-----------|-----------|--------------|
| 0 | Erfolg | Ergebnis praesentieren |
| 1 | Technischer Fehler | Fehlermeldung zeigen |
| 2 | Soft-Warnung (>= 5 remaining) | Empfehlung zeigen, User fragen: Differenz auffuellen ODER volle Menge mit --force? |
| 3 | Hard-Cap (wuerde > 20) | Maximum erklaeren, reduzierte Menge vorschlagen |

**Wichtig:** Bei Exit 2 oder 3 den Output des Scripts dem User zeigen — dort steht die Empfehlung. Falls der User trotzdem will, erneut mit `--force` oder angepasstem `--credits` ausfuehren.

## Fuer Orchestratoren / aufrufende Agenten

| Befehl | Timeout | Braucht Browser? |
|--------|---------|:----------------:|
| `py refill_credits.py --email ... --credits 10` | 300.000ms (5 Min) | Ja |
| `py refill_credits.py --email ... --remove --credits 10` | 300.000ms (5 Min) | Ja |
| `py refill_credits.py --email ... --force` | 300.000ms (5 Min) | Ja |

## Typische Szenarien

### Credits hinzufuegen
- "Fuelle Credits fuer max@example.com nach" → `py refill_credits.py --email max@example.com`
- "Gib Florian Vallet 20 Credits" → `py refill_credits.py --email florian.vallet@... --credits 20`
- "10 Credits fuer anna@jobcloud.ch" → `py refill_credits.py --email anna@jobcloud.ch`

### Credits entfernen
- "Entferne Credits von max@example.com" → `py refill_credits.py --email max@example.com --remove`
- "Nimm Florian 5 Credits weg" → `py refill_credits.py --email florian.vallet@... --remove --credits 5`
- "Credits wegnehmen wegen Inaktivitaet" → `py refill_credits.py --email ... --remove`

## Hinweise

- **Session:** Login-Session in `.session/state.json` (Captcha nur beim ersten Mal)
- **Captcha:** Beim ersten Login muss ein Captcha manuell geloest werden (5 Min Timeout)
- **Headless:** Nicht verwenden wenn Captcha erwartet wird
- **Standard-Credits:** 10 (fuer Powernutzer wie Florian Vallet: 20)
- **Fehler-Screenshot:** Bei Problemen wird `daten/refill_error_screenshot.png` gespeichert
- **E-Mail benoetigt:** Der Agent muss die exakte Babbel-E-Mail-Adresse des Nutzers kennen. Falls nur ein Name gegeben wird, vorher in den vorhandenen CSV-Daten (`daten/memberships.csv` oder `daten/intensive_credits.csv`) die E-Mail nachschlagen.
