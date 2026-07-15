# BabbelBot — Self-Service Slack Bot (Entwurf)

> **Status: ENTWURF** — Dieser Code zeigt die Ziel-Architektur fuer einen Slack-Bot
> der Jobcloud-Mitarbeitern Self-Service Zugang zu Babbel ermoeglicht.

## Was es macht

Zwei Funktionen fuer Endnutzer (via Slack):

1. **"Fuege mich auf Babbel hinzu"** — Einladung zum Firmenaccount (Professional/Intensive)
2. **"Fuell meine Credits nach"** — Intensive Credits auffuellen (wenn < 5 remaining)

## Architektur

```
Slack User → @BabbelBot "Fueg mich hinzu"
                ↓
         Slack App (Webhook → AgentCore)
                ↓
         Strands Agent (main.py)
           • System Prompt (Konversationslogik)
           • Claude via Bedrock (EU inference)
           • Tools: check_status, invite, refill, notify_admin
                ↓
         babbel_tools.py
           • Playwright Browser-Automation → Babbel Portal
           • CSV-Lookup fuer Status-Checks
```

## Dateien

| Datei | Zweck |
|-------|-------|
| `main.py` | Strands Agent: Prompt, Tools, Entrypoint |
| `babbel_tools.py` | Tool-Implementierungen (Playwright + CSV) |
| `model/load.py` | Bedrock Model-Konfiguration (EU Claude) |
| `pyproject.toml` | Python Dependencies |

## Deployment-Anforderungen

### Build-Type: Container (nicht CodeZip)

Da Playwright + Chromium benoetigt wird (~500MB), muss der Agent als
**Container** deployt werden. Ein `Dockerfile` ist noetig:

```dockerfile
FROM mcr.microsoft.com/playwright/python:v1.52.0-jammy
# ... Agent-Code installieren ...
RUN playwright install chromium
```

### Secrets (agentcore/.env.local)

```
BABBEL_EMAIL=admin@jobcloud.ch
BABBEL_PASSWORD=...
ADMIN_SLACK_USER_ID=U12345678
```

### Session-Persistenz

Die Babbel-Login-Session muss persistent gespeichert werden (S3 oder EFS),
um nicht bei jedem Aufruf ein Captcha loesen zu muessen.

**Erster Login:** Manuell durchfuehren, Session-State speichern.
Danach reicht der gespeicherte Cookie fuer weitere Aufrufe.

## Offene Punkte (zu klaeren mit dem Experten)

1. **Container-Build moeglich?** AgentCore BuildType `Container` statt `CodeZip`?
2. **Timeout-Limit?** Playwright-Sessions dauern 30-60s. Hat die Runtime ein Limit?
3. **Session-Storage:** S3 oder EFS fuer die Babbel-Session (`state.json`)?
4. **Slack User-ID → E-Mail:** Wie wird die Slack-E-Mail des Users an den Agent uebergeben?
   (Vermutlich als `context.user_id` — muss von der Slack-App gemappt werden)
5. **Admin DM:** Kann der Agent direkt Slack DMs senden, oder muss die Slack-App das uebernehmen?
6. **CSV-Daten:** Wie kommen die CSVs (memberships.csv, intensive_credits.csv) in die Cloud?
   Optionen: S3-Upload via Cron, oder Agent exportiert selbst mit Playwright.
7. **SharePoint Excel:** Zugriff via Microsoft Graph API oder nur lokaler Agent pflegt die Excel?

## Beziehung zum lokalen Agent

Der lokale OpenCode-basierte Babbel Agent bleibt parallel bestehen fuer Admin-Aufgaben:
- Statistiken generieren
- Inaktive Nutzer identifizieren
- Nutzer loeschen (geplant)
- SharePoint-Excel pflegen

Der Slack-Bot ist NUR fuer Self-Service (Invite + Credits) der Endnutzer.
