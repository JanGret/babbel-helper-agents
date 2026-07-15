"""
BabbelBot: Self-Service Slack Bot fuer Jobcloud-Mitarbeiter.

Zwei Kernfunktionen:
1. Neuen Nutzer zum Babbel-Account einladen (Self-Service)
2. Intensive Credits nachfuellen (Self-Service)

Deployment: AWS Bedrock AgentCore Runtime (Container-Build mit Playwright/Chromium)
Region: eu-west-1 (EU-compliant)
Model: Claude via EU cross-region inference profile
"""

from strands import Agent, tool
from bedrock_agentcore.runtime import BedrockAgentCoreApp
from model.load import load_model

app = BedrockAgentCoreApp()
log = app.logger


# ---------------------------------------------------------------------------
# System Prompt
# ---------------------------------------------------------------------------

DEFAULT_SYSTEM_PROMPT = """
Du bist der Babbel Self-Service Bot fuer Jobcloud-Mitarbeiter.
Du sprichst die Sprache des Users (Deutsch, Franzoesisch oder Englisch).

## Was du kannst

1. **Babbel-Account erstellen** — Den User zum Babbel-Firmenaccount einladen.
2. **Intensive Credits nachfuellen** — Credits fuer Intensive-Nutzer auffuellen.

## Ablauf: Account erstellen

1. Pruefe mit `check_my_status` ob der User bereits existiert.
   - Falls ja: Sage "Du hast bereits einen Babbel-Account."
   - Falls nein: Weiter mit Schritt 2.
2. Frage nach dem Plan:
   - Professional (Standard, App-basiertes Lernen)
   - Intensive (1:1 Lektionen mit Sprachlehrern, inkl. 10 Start-Credits)
3. Frage nach der Einladungssprache. Mache einen Vorschlag basierend auf dem Namen:
   - Deutsch klingend → "Soll die Einladung auf Deutsch sein?"
   - Franzoesisch klingend → "En francais?"
   - Sonst → "Shall I send the invitation in English?"
4. Fuehre `invite_me` aus.
5. Bei Erfolg: Bestaetigung. Bei Slot-Problem: Informiere den User und nutze `notify_admin`.

## Ablauf: Credits nachfuellen

1. Pruefe mit `check_my_status` ob der User Intensive-Nutzer ist.
   - Falls nicht: "Du hast keinen Intensive-Plan. Wende dich an L&D (Jan Gretschuskin)."
2. Pruefe ob Credits-Stand niedrig genug ist (remaining < 5).
   - Falls remaining >= 5: "Du hast noch X Credits. Kein Nachfuellen noetig."
3. Fuehre `refill_my_credits` aus.
4. Bestaetigung mit neuem Credits-Stand.

## Regeln

- Du kennst die E-Mail des Users automatisch (wird vom System uebergeben als user_email).
  Verwende IMMER diese E-Mail, frage nie danach.
- Der Name wird aus der E-Mail extrahiert (vorname.nachname@jobcloud.ch → Vorname Nachname).
- Verwende IMMER zuerst `check_my_status` bevor du eine Aktion ausfuehrst.
- Sei freundlich, kurz und hilfreich. Kein Technik-Jargon.
- Bei Fehlern: Sage dem User er soll L&D kontaktieren (Jan Gretschuskin).
- Fuehre NIE Aktionen aus ohne Bestaetigung des Users.
"""


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------

@tool
def check_my_status(email: str) -> dict:
    """Prueft den Babbel-Status eines Nutzers.

    Gibt zurueck ob der User existiert, welchen Plan er hat,
    wie viele Intensive Credits remaining sind, und die Slot-Belegung.

    Args:
        email: E-Mail-Adresse des Nutzers (vorname.nachname@jobcloud.ch)

    Returns:
        dict mit: exists (bool), plan (str|None), credits_remaining (int|None),
        slots_used (int), slots_max (int)
    """
    from babbel_tools import check_user_status
    return check_user_status(email)


@tool
def invite_me(email: str, plan: str, lang: str) -> dict:
    """Laedt einen neuen Nutzer zum Babbel-Firmenaccount ein.

    Oeffnet das Babbel-Portal, navigiert zur Users-Seite und sendet eine Einladung.
    Bei Intensive-Plan werden automatisch 10 Start-Credits vergeben.

    Args:
        email: E-Mail-Adresse des neuen Nutzers (vorname.nachname@jobcloud.ch)
        plan: "professional" oder "intensive"
        lang: Einladungssprache ("en", "de", "fr", "es", "it", "pt")

    Returns:
        dict mit: success (bool), message (str)
    """
    from babbel_tools import invite_user
    return invite_user(email, plan, lang)


@tool
def refill_my_credits(email: str) -> dict:
    """Fuellt Intensive Credits fuer einen Nutzer auf 10 nach.

    Oeffnet das Babbel-Portal, navigiert zur Intensive Credits Seite,
    und fuegt Credits hinzu bis der Nutzer 10 remaining hat.

    Args:
        email: E-Mail-Adresse des Nutzers

    Returns:
        dict mit: success (bool), credits_added (int), new_remaining (int),
        pool_remaining (int), pool_total (int), message (str)
    """
    from babbel_tools import refill_credits
    return refill_credits(email)


@tool
def notify_admin(message: str) -> dict:
    """Sendet eine Benachrichtigung an den L&D-Admin (Jan Gretschuskin) via Slack DM.

    Verwende dies bei:
    - Slots sind voll (>= 100 Nutzer-Slots belegt)
    - Technische Fehler bei der Einladung oder Credits
    - Ungewoehnliche Situationen die menschliche Aufmerksamkeit brauchen

    Args:
        message: Nachricht an den Admin (kurz und klar, mit Kontext)

    Returns:
        dict mit: success (bool), message (str)
    """
    from babbel_tools import send_admin_notification
    return send_admin_notification(message)


tools = [check_my_status, invite_me, refill_my_credits, notify_admin]


# ---------------------------------------------------------------------------
# Agent Entrypoint
# ---------------------------------------------------------------------------

@app.entrypoint
async def invoke(payload, context):
    """Agent invocation entrypoint.

    Der Slack-App-Layer uebergibt:
    - payload.prompt: Die Nachricht des Users
    - context.user_id: Die Slack-E-Mail des Users (= Babbel-E-Mail)
    - context.session_id: Session-ID fuer Multi-Turn Konversation
    """
    log.info("Invoking BabbelBot...")

    session_id = getattr(context, "session_id", "default-session")
    user_id = getattr(context, "user_id", "default-user")

    agent = Agent(
        model=load_model(),
        system_prompt=DEFAULT_SYSTEM_PROMPT,
        tools=tools,
    )

    prompt = payload.get("prompt", "")

    # User-Email automatisch in den Kontext injizieren
    # So weiss der Agent wer fragt, ohne dass der User seine E-Mail angeben muss
    augmented_prompt = (
        f"[System-Kontext: Der User hat die E-Mail-Adresse: {user_id}. "
        f"Verwende diese fuer alle Tool-Aufrufe.]\n\n"
        f"{prompt}"
    )

    async for event in agent.stream_async(augmented_prompt):
        if not isinstance(event, dict) or "event" not in event:
            continue
        yield event


if __name__ == "__main__":
    app.run()
