import os
from pathlib import Path


class Settings:
    llm_provider = os.getenv('LLM_PROVIDER', 'bedrock')
    bedrock_model_id = os.getenv('BEDROCK_MODEL_ID', 'us.anthropic.claude-sonnet-4-5-20250929-v1:0')
    aws_region = os.getenv('AWS_REGION', 'us-west-2')
    anthropic_model_id = os.getenv('ANTHROPIC_MODEL_ID', 'claude-sonnet-4-5')
    anthropic_api_key = os.getenv('ANTHROPIC_API_KEY')
    identity_dir = Path(os.getenv('IDENTITY_DIR', '/state/identity'))
    session_dir = Path(os.getenv('SESSION_DIR', '/state/sessions'))
    skills_dir = Path(os.getenv('SKILLS_DIR', '/state/skills'))
    agent_id = os.getenv('AGENT_ID', 'platform-ops')
    langfuse_host = os.getenv('LANGFUSE_HOST')
    langfuse_public_key = os.getenv('LANGFUSE_PUBLIC_KEY')
    langfuse_secret_key = os.getenv('LANGFUSE_SECRET_KEY')

    @property
    def langfuse_enabled(self):
        return bool(self.langfuse_host and self.langfuse_public_key and self.langfuse_secret_key)


settings = Settings()
