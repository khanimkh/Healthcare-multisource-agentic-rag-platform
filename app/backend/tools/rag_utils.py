from typing import List, Dict, Any
from langchain_text_splitters import RecursiveCharacterTextSplitter
from app.backend.services.bedrock_service import BedrockService


def chunk_documents(
    text: str,
    chunk_size: int = 1000,
    chunk_overlap: int = 150
) -> List[str]:
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap
    )

    return splitter.split_text(text)


def create_embeddings_for_chunks(
    chunks: List[str]
) -> List[Dict[str, Any]]:
    bedrock = BedrockService()
    embedded_chunks = []

    for chunk in chunks:
        embedding = bedrock.create_embedding(chunk)

        embedded_chunks.append({
            "text": chunk,
            "embedding": embedding
        })

    return embedded_chunks