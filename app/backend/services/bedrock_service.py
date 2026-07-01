import json
import boto3
from typing import List
from app.backend.config.settings import settings


class BedrockService:
    def __init__(self):
        self.client = boto3.client(
            "bedrock-runtime",
            region_name=settings.aws_region
        )

    def classify_text(self, text: str) -> str:
        prompt = f"""
        Classify the following healthcare content into one category:
        - clinical guideline
        - patient report
        - claims dataset
        - healthcare policy
        - research publication
        - lab result
        - administrative document
        - unknown

       Return only the category name.

       Content:
         {text[:4000]}
        """

        body = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 100,
            "temperature": 0,
            "messages": [
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        }

        response = self.client.invoke_model(
            modelId=settings.bedrock_llm_model_id,
            body=json.dumps(body),
            contentType="application/json",
            accept="application/json"
        )

        result = json.loads(response["body"].read())
        return result["content"][0]["text"].strip()

    def create_embedding(self, text: str) -> List[float]:
        body = {
            "inputText": text
        }

        response = self.client.invoke_model(
            modelId=settings.bedrock_embedding_model_id,
            body=json.dumps(body),
            contentType="application/json",
            accept="application/json"
        )

        result = json.loads(response["body"].read())
        return result["embedding"]