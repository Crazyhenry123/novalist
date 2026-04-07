from strands.models import BedrockModel
from app.config import settings


def get_model() -> BedrockModel:
    """Create the Bedrock model configured for Claude Sonnet 4.6."""
    return BedrockModel(
        model_id=settings.bedrock_model_id,
        region_name=settings.aws_region,
        streaming=True,
        temperature=0.7,
        max_tokens=8192,
    )


def get_planning_model() -> BedrockModel:
    """Lower temperature model for structured planning tasks."""
    return BedrockModel(
        model_id=settings.bedrock_model_id,
        region_name=settings.aws_region,
        streaming=True,
        temperature=0.4,
        max_tokens=8192,
    )


def get_creative_model() -> BedrockModel:
    """Higher temperature model for creative prose generation."""
    return BedrockModel(
        model_id=settings.bedrock_model_id,
        region_name=settings.aws_region,
        streaming=True,
        temperature=0.85,
        max_tokens=16384,
    )
