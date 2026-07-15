---
name: babbel-invite
description: Lade einen neuen Nutzer zu Babbel ein. Nutze diesen Skill wenn der User einen neuen Mitarbeiter einladen, hinzufuegen oder anlegen will.
---

# Babbel: Nutzer einladen

## Script: `invite_user.py`

```bash
# Professional (Standard)
py invite_user.py --email new@example.com --name "Max Mustermann" --lang en
py invite_user.py --email new@example.com --name "Hans Mueller" --lang de

# Intensive (mit 10 Start-Credits)
py invite_user.py --email new@example.com --name "Marie Dupont" --plan intensive --lang fr
```

## Was es tut

1. Loggt sich im Babbel-Portal ein (Session wird wiederverwendet)
2. Navigiert zur Users-Seite (`/users`)
3. Klickt "Invite New Member"
4. Fuellt das Popup aus:
   - E-Mail-Adresse
   - Einladungssprache
   - Plan (Professional oder Intensive)
   - Start-Credits (nur bei Intensive, immer 10)
5. Klickt "Invite New Members"
6. Traegt den Nutzer in die SharePoint-Excel ein

## Parameter

| Parameter | Required | Default | Beschreibung |
|-----------|:--------:|---------|--------------|
| `--email` | Ja | - | E-Mail-Adresse des neuen Nutzers |
| `--name` | Nein | aus E-Mail | Vor- und Nachname (wird automatisch aus vorname.nachname@... extrahiert) |
| `--plan` | Nein | `professional` | `professional` oder `intensive` |
| `--lang` | Ja | - | Einladungssprache (`en`, `de`, `fr`, `es`, `it`, `pt`) |
| `--credits` | Nein | `10` | Start-Credits (nur bei Intensive) |
| `--headless` | Nein | - | Browser ohne Fenster |

## Agent-Verhalten

### Pflichtangaben sammeln

Bevor das Script ausgefuehrt wird, muss der Agent folgende Infos haben:

1. **E-Mail-Adresse** — Muss vom User angegeben werden
2. **Name** — Wird automatisch aus `vorname.nachname@...` extrahiert. Nur noetig wenn das E-Mail-Format abweicht (z.B. nur ein Wort vor dem @, oder Initialen).
3. **Einladungssprache** — Agent soll IMMER fragen. Dabei einen Vorschlag basierend auf dem Namen machen:
   - Deutsch klingend (Mueller, Schmidt, etc.) → "Soll ich Deutsch (`de`) nehmen?"
   - Franzoesisch klingend (Dupont, Lefebvre, etc.) → "Soll ich Franzoesisch (`fr`) nehmen?"
   - Sonst → "Soll ich Englisch (`en`) nehmen?"
4. **Plan** — Standard ist Professional. Nur fragen wenn der User explizit "Intensive" erwaehnt oder es unklar ist.

### Beispiel-Dialog

```
User: "Lade bitte max.mueller@jobcloud.ch ein"
Agent: "Name wird aus E-Mail extrahiert: Max Mueller.
        Soll die Einladung auf Deutsch sein (klingt deutschsprachig)?
        Plan ist Professional (Standard)."
User: "Ja, Deutsch passt"
Agent: → py invite_user.py --email max.mueller@jobcloud.ch --lang de
```

## Fuer Orchestratoren / aufrufende Agenten

| Befehl | Timeout | Braucht Browser? |
|--------|---------|:----------------:|
| `py invite_user.py --email ... --lang ...` | 300.000ms (5 Min) | Ja |

## Excel-Eintrag

Nach erfolgreicher Einladung wird automatisch eine neue Zeile in der SharePoint-Excel erstellt:

| Spalte | Professional | Intensive |
|--------|:---:|:---:|
| A (Name) | Name | Name |
| B (E-Mail) | E-Mail | E-Mail |
| C (Entry) | Heutiges Datum | Heutiges Datum |
| D (Professional) | TRUE | - |
| E (Intensive 2026) | - | TRUE |
| F (Credits Intensive) | - | 10 |
| G (Credit Restock) | - | Heutiges Datum |

## Hinweise

- **Session:** Login-Session in `.session/state.json` (Captcha nur beim ersten Mal)
- **Captcha:** Beim ersten Login muss ein Captcha manuell geloest werden (5 Min Timeout)
- **Headless:** Nicht verwenden wenn Captcha erwartet wird
- **Fehler-Screenshot:** Bei Problemen wird `daten/invite_error_screenshot.png` gespeichert
- **Duplikat-Pruefung:** Das Portal prueft selbst ob die E-Mail bereits existiert und zeigt ggf. einen Fehler.

## Slot-Pruefung (automatisch)

Das Script prueft vor der Einladung automatisch:

### Gesamt-Slots (Limit: 100 Nutzer-Slots)

- Liest "X members total" von der Users-Seite
- Zieht 3 Admin-Accounts ab (Kyra, Alla, Jan belegen keine Nutzer-Slots)
- Bei >= 100 Nutzer-Slots belegt: **Warnung** (Einladung wird trotzdem durchgefuehrt)

### Intensive-Slots (weiches Limit: 30)

- Nur bei `--plan intensive` relevant
- Zaehlt Nutzer mit "x" in Spalte E der SharePoint-Excel
- Bei >= 30 aktive Intensive-Nutzer: **Warnung** (Einladung wird trotzdem durchgefuehrt)
- Hinweis: Nutzer ohne Credits aber mit Intensive-Flag zaehlen mit

### Agent-Verhalten bei Slot-Warnung

Wenn das Script eine Slot-Warnung ausgibt:
1. Die Warnung dem User zeigen
2. Vorschlagen: "Der Account ist voll. Moechtest du die Liste der inaktiven Nutzer sehen?"
3. Falls User ja sagt → `py consolidate.py` ausfuehren (Skill `babbel-recommendations`)
