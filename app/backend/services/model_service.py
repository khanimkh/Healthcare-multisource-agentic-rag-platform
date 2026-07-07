import json
from typing import Any, Dict, List, Optional

import boto3

from app.backend.config.settings import settings


class ModelService:
    def __init__(self):
        self.client = boto3.client(
            "bedrock-runtime",
            region_name=settings.aws_region
        )

    def invoke_text_model(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        model_id: Optional[str] = None,
        max_tokens: int = 1024,
        temperature: float = 0.3
    ) -> str:
        body: Dict[str, Any] = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": [
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        }

        if system_prompt:
            body["system"] = system_prompt

        response = self.client.invoke_model(
            modelId=model_id or settings.bedrock_llm_model_id,
            body=json.dumps(body),
            contentType="application/json",
            accept="application/json"
        )

        result = json.loads(response["body"].read())
        return result["content"][0]["text"].strip()

    def invoke_embedding_model(
        self,
        text: str,
        model_id: Optional[str] = None
    ) -> List[float]:
        body = {
            "inputText": text
        }

        response = self.client.invoke_model(
            modelId=model_id or settings.bedrock_embedding_model_id,
            body=json.dumps(body),
            contentType="application/json",
            accept="application/json"
        )

        result = json.loads(response["body"].read())
        return result["embedding"]
