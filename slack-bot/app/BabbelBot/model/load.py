from strands.models.bedrock import BedrockModel


def load_model() -> BedrockModel:
    """Get Bedrock model client using IAM credentials.

    Verwendet das EU cross-region inference profile fuer EU-Datenresidenz.
    Alle Inference-Anfragen bleiben innerhalb europaeischer AWS-Regionen.
    """
    return BedrockModel(model_id="eu.anthropic.claude-sonnet-4-6")
