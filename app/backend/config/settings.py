from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    aws_region: str = "us-east-1"

    s3_bucket_name: str

    bedrock_llm_model_id: str = "anthropic.claude-3-5-sonnet-20240620-v1:0"
    bedrock_embedding_model_id: str = "amazon.titan-embed-text-v2:0"

    postgres_url: str

    opensearch_host: str
    opensearch_index: str = "healthcare-documents"

    redis_url: str = "redis://localhost:6379/0"

    glue_database_name: str = "healthcare_metadata_catalog"

    class Config:
        env_file = ".env"


settings = Settings()