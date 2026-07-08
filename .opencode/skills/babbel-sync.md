---
name: babbel-sync
description: Synchronisiere die SharePoint-Excel mit Babbel-Daten. Nutze diesen Skill wenn die manuelle Liste aktualisiert werden soll.
---

# Babbel: SharePoint-Excel synchronisieren

## Script: `sync_sharepoint.py`

```bash
py sync_sharepoint.py
```

## Was es tut

1. Liest `daten/memberships.csv` (offizielle Babbel Join Dates)
2. Oeffnet die SharePoint-Excel (ueber OneDrive-Sync-Pfad)
3. Ergaenzt fehlende Entry-Daten (wo das Feld leer ist)
4. Speichert die Excel

## Voraussetzungen

- `daten/memberships.csv` muss aktuell sein (ggf. vorher: `py export_babbel.py --tab memberships`)
- SharePoint-Excel muss ueber OneDrive synchronisiert sein
- Pfad konfigurierbar via `SHAREPOINT_EXCEL_PATH` in `.env`

## Was es NICHT tut

- Ueberschreibt keine bestehenden Entry-Werte
- Aendert keine anderen Spalten (nur Entry)
- Loescht oder fuegt keine Zeilen hinzu

## Fuer Orchestratoren / aufrufende Agenten

| Befehl | Timeout | Braucht Browser? |
|--------|---------|:----------------:|
| `py sync_sharepoint.py` | 120.000ms (Standard) | Nein |

**Voraussetzung:** Aktuelle `memberships.csv`. Falls veraltet, vorher `py export_babbel.py --tab memberships`.

## Spaetere Erweiterungen (geplant)

- Plan-Typ (Professional/Intensive) synchronisieren
- Status-Updates nach Loeschung/Einladung
- Neue Nutzer automatisch in die Excel eintragen
