import logging
import openai
from typing import List
import asyncio
from tenacity import retry, stop_after_attempt, wait_exponential

from ..config import settings

logger = logging.getLogger(__name__)


class EmbeddingService:
    """Service for generating embeddings using OpenAI"""
    
    def __init__(self):
        if not settings.openai_api_key:
            raise ValueError("OpenAI API key not configured")
        
        openai.api_key = settings.openai_api_key
        self.client = openai.AsyncOpenAI(api_key=settings.openai_api_key)
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10)
    )
    async def get_embedding(self, text: str) -> List[float]:
        """Get embedding for a single text"""
        try:
            # Clean and truncate text if necessary
            text = text.strip()
            if len(text) > 8000:  # OpenAI token limit approximation
                text = text[:8000]
            
            response = await self.client.embeddings.create(
                model=settings.openai_embedding_model,
                input=text
            )
            
            embedding = response.data[0].embedding
            logger.debug(f"Generated embedding for text of length {len(text)}")
            return embedding
            
        except Exception as e:
            logger.error(f"Failed to generate embedding: {str(e)}")
            raise
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10)
    )
    async def get_embeddings_batch(self, texts: List[str]) -> List[List[float]]:
        """Get embeddings for multiple texts"""
        try:
            # Clean and truncate texts
            cleaned_texts = []
            for text in texts:
                text = text.strip()
                if len(text) > 8000:
                    text = text[:8000]
                cleaned_texts.append(text)
            
            response = await self.client.embeddings.create(
                model=settings.openai_embedding_model,
                input=cleaned_texts
            )
            
            embeddings = [item.embedding for item in response.data]
            logger.debug(f"Generated {len(embeddings)} embeddings")
            return embeddings
            
        except Exception as e:
            logger.error(f"Failed to generate batch embeddings: {str(e)}")
            raise