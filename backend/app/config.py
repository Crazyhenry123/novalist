import os
from pydantic import BaseModel


class Settings(BaseModel):
    aws_region: str = os.getenv("AWS_REGION", "us-east-1")
    bedrock_model_id: str = os.getenv(
        "BEDROCK_MODEL_ID", "us.anthropic.claude-sonnet-4-6"
    )
    novels_table: str = os.getenv("NOVELS_TABLE", "novalist-novels")
    chapters_table: str = os.getenv("CHAPTERS_TABLE", "novalist-chapters")
    cognito_user_pool_id: str = os.getenv("COGNITO_USER_POOL_ID", "")
    cognito_region: str = os.getenv("COGNITO_REGION", "us-east-1")
    websocket_api_endpoint: str = os.getenv("WEBSOCKET_API_ENDPOINT", "")
    log_level: str = os.getenv("LOG_LEVEL", "INFO")


settings = Settings()
