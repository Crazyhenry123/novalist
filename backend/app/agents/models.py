from botocore.config import Config as BotocoreConfig
from strands.models import BedrockModel
from app.config import settings

# Bedrock streaming with long Chinese prompts can take well over 120s.
_BEDROCK_CLIENT_CONFIG = BotocoreConfig(
    read_timeout=600,
    retries={"max_attempts": 3, "mode": "adaptive"},
)


def get_model() -> BedrockModel:
    """Create the Bedrock model configured for Claude Sonnet 4.6."""
    return BedrockModel(
        model_id=settings.bedrock_model_id,
        region_name=settings.aws_region,
        streaming=True,
        temperature=0.7,
        max_tokens=16384,
        boto_client_config=_BEDROCK_CLIENT_CONFIG,
    )


def get_planning_model() -> BedrockModel:
    """Lower temperature model for structured planning tasks.

    8192 tokens is enough for structure/characters/world/plot outlines.
    With 1 continuation retry, max output is ~16K tokens.
    """
    return BedrockModel(
        model_id=settings.bedrock_model_id,
        region_name=settings.aws_region,
        streaming=True,
        temperature=0.4,
        max_tokens=8192,
        boto_client_config=_BEDROCK_CLIENT_CONFIG,
    )


def get_creative_model() -> BedrockModel:
    """Higher temperature model for creative prose generation."""
    return BedrockModel(
        model_id=settings.bedrock_model_id,
        region_name=settings.aws_region,
        streaming=True,
        temperature=0.85,
        max_tokens=32768,
        boto_client_config=_BEDROCK_CLIENT_CONFIG,
    )
