from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    aws_region: str = "us-east-1"

    s3_bucket_name: str

    bedrock_llm_model_id: str = "us.anthropic.claude-haiku-4-5-20251001-v1:0"
    bedrock_embedding_model_id: str = "amazon.titan-embed-text-v2:0"

    postgres_url: str

    opensearch_host: str
    opensearch_index: str = "healthcare_documents_index"

    redis_url: str = "redis://localhost:6379/0"

    glue_database_name: str = "healthcare_documents_db"
    
    athena_output_s3_uri: str = "s3://your-athena-query-results-bucket/"

    class Config:
        env_file = ".env"


settings = Settings()