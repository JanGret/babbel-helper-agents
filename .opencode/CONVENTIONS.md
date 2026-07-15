# Projekt-Konventionen

Regeln fuer alle Agenten die in diesem Projekt arbeiten.

## Git

- **Nach jeder groesseren Aenderung** (neue Scripts, Skill-Updates, Bugfixes, etc.) automatisch committen und pushen.
- Commit-Messages auf Deutsch, kurz und beschreibend.
- Keine sensiblen Daten committen (.env, Credentials, Session-State).

## Code-Stil

- Python-Scripts: Deutsche Kommentare, ASCII-kompatible Strings (keine Umlaute in Code/Variablen).
- Alle Print-Ausgaben auf Deutsch (fuer den Admin-User).
- Neue Scripts folgen dem Muster der bestehenden (Login, Session-Wiederverwendung, Screenshot bei Fehler).

## Agent-Skills

- Jedes neue Feature bekommt: Script + Skill-Datei (.md) + Eintrag in babbel.md (Routing, Schnellreferenz, Beispiel).
- Skills werden einzeln geladen, nie mehrere gleichzeitig.
- Timeouts fuer Browser-Scripts immer dokumentieren.

## Testing

- Neue Browser-Automations-Scripts immer mit einem echten Testlauf verifizieren.
- Bei Fehlern: Screenshot analysieren, Selektoren anpassen, erneut testen.
- Nach erfolgreichem Test: Testdaten zuruecksetzen (z.B. Credits wieder entfernen).
