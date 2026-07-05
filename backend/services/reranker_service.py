from __future__ import annotations
import logging
from typing import TYPE_CHECKING
import httpx
from backend.config.settings import Settings

if TYPE_CHECKING:
    from backend.rag.retrieval import RetrievedChunk

logger = logging.getLogger(__name__)

class RerankerService:
    """Rerank retrieval candidates using a Hugging Face cross-encoder model."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.model_name = settings.reranker_model_name
        self.api_url = f"https://router.huggingface.co/hf-inference/models/{self.model_name}"
        
        headers = {}
        if settings.hf_token:
            headers["Authorization"] = f"Bearer {settings.hf_token}"
        
        self.client = httpx.AsyncClient(headers=headers, timeout=20.0)

    async def rerank(self, query: str, chunks: list[RetrievedChunk], top_k: int) -> list[RetrievedChunk]:
        """Score and reorder ``chunks`` by relevance to ``query``, returning top ``top_k``."""
        if not self.settings.reranker_enabled or not chunks:
            return chunks[:top_k]
            
        if not self.settings.hf_token:
            logger.warning("HF_TOKEN is missing. Skipping reranking and returning top candidates.")
            return chunks[:top_k]

        # Prepare text-pair inputs for the CrossEncoder classification task
        payload = {
            "inputs": [
                {"text": query, "text_pair": chunk.chunk_text}
                for chunk in chunks
            ]
        }

        try:
            response = await self.client.post(self.api_url, json=payload)
            response.raise_for_status()
            results = response.json()
            
            # Parse scores. The HF Serverless Classification API returns a list of results:
            # e.g., [[{"label": "LABEL_0", "score": 0.89}, {"label": "LABEL_1", "score": 0.11}]]
            for chunk, result in zip(chunks, results):
                score = 0.0
                if isinstance(result, list):
                    # Map labels to their scores
                    label_map = {
                        item.get("label"): float(item.get("score", 0.0))
                        for item in result
                        if isinstance(item, dict)
                    }
                    
                    if "LABEL_1" in label_map:
                        # Standard positive relevance label for binary cross-encoders
                        score = label_map["LABEL_1"]
                    elif "LABEL_0" in label_map:
                        # If only LABEL_0 is present, use it directly (single-output cross-encoder)
                        # Otherwise, calculate complement (binary classifier)
                        if len(label_map) == 1:
                            score = label_map["LABEL_0"]
                        else:
                            score = 1.0 - label_map["LABEL_0"]
                    elif len(result) == 1:
                        # Single output score (regression models)
                        score = float(result[0].get("score", 0.0))
                    elif result:
                        # Fallback to the first item's score
                        score = float(result[0].get("score", 0.0))
                elif isinstance(result, dict):
                    score = float(result.get("score", 0.0))
                
                chunk.score = score
            
            # Sort descending by rerank score
            chunks.sort(key=lambda x: -x.score)
            
        except Exception as exc:
            logger.error("Hugging Face Reranking failed: %s. Returning raw candidates.", exc)
            
        return chunks[:top_k]

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        await self.client.aclose()
