import logging
from typing import List, Optional, Dict, Any
import openai
from datetime import datetime

from ..config import settings
from ..models import AskResponse, DocumentSource
from .vector_store import LocalVectorStore
from .citations import CitationFormatter

logger = logging.getLogger(__name__)


class RAGChain:
    """Retrieval-Augmented Generation chain using local FAISS"""
    
    def __init__(self):
        if not settings.openai_api_key:
            raise ValueError("OpenAI API key not configured")
        
        self.client = openai.AsyncOpenAI(api_key=settings.openai_api_key)
        self.vector_store: Optional[LocalVectorStore] = None
        self.citation_formatter = CitationFormatter()
    
    async def initialize(self, vector_store: LocalVectorStore):
        """Initialize with vector store"""
        self.vector_store = vector_store
        logger.info("RAG chain initialized with local FAISS")
    
    async def ask(
        self,
        query: str,
        sku: Optional[str] = None,
        top_k: int = 4
    ) -> AskResponse:
        """Ask a question and get grounded answer with sources"""
        if not self.vector_store:
            raise RuntimeError("RAG chain not initialized")
        
        # Retrieve relevant documents
        search_results = await self.vector_store.similarity_search(
            query=query,
            top_k=top_k,
            sku_filter=sku
        )
        
        # Format sources
        sources = []
        context_parts = []
        
        for i, result in enumerate(search_results):
            # Create citation
            citation = self.citation_formatter.format_citation(
                document_name=result["document_name"],
                page_number=result.get("page_number"),
                style=settings.citation_style
            )
            
            # Create source
            source = DocumentSource(
                document=result["document_name"],
                page=result.get("page_number"),
                chunk_id=result["chunk_id"],
                relevance_score=result["score"],
                content=result["content"][:500] + "..." if len(result["content"]) > 500 else result["content"],
                citation=citation
            )
            sources.append(source)
            
            # Add to context
            context_parts.append(f"[{i+1}] {result['content']}")
        
        # Generate answer
        answer = await self._generate_answer(query, context_parts, sources)
        
        return AskResponse(
            query=query,
            answer=answer,
            sources=sources,
            sku_filter=sku,
            timestamp=datetime.utcnow().isoformat(),
            model_used=settings.openai_chat_model,
            total_sources=len(sources)
        )
    
    async def _generate_answer(
        self,
        query: str,
        context_parts: List[str],
        sources: List[DocumentSource]
    ) -> str:
        """Generate answer using OpenAI with context"""
        
        # Build context
        context = "\n\n".join(context_parts)
        
        # Truncate context if too long
        if len(context) > settings.max_context_length:
            context = context[:settings.max_context_length] + "..."
        
        # Build citations reference
        citations_ref = "\n".join([
            f"[{i+1}] {source.citation}"
            for i, source in enumerate(sources)
        ])
        
        # Create system prompt
        system_prompt = f"""You are an expert assistant for enterprise demand forecasting and business intelligence. 
Your role is to provide accurate, well-sourced answers based on the provided enterprise documents.

Guidelines:
1. Answer questions using ONLY the information provided in the context
2. Include specific citations using [1], [2], etc. format referring to the sources
3. If the context doesn't contain enough information, say so clearly
4. Be concise but comprehensive
5. Focus on actionable insights for business decision-making
6. When discussing forecasts, trends, or business metrics, be specific about timeframes and confidence levels

Citation Style: {settings.citation_style.upper()}

Available Sources:
{citations_ref}

Context from Enterprise Documents:
{context}
"""

        user_prompt = f"""Based on the enterprise documents provided, please answer this question:

{query}

Remember to:
- Use specific citations [1], [2], etc. for all claims
- Only use information from the provided context
- Be clear about any limitations in the available information
"""

        try:
            response = await self.client.chat.completions.create(
                model=settings.openai_chat_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                max_tokens=settings.openai_max_tokens,
                temperature=settings.openai_temperature
            )
            
            answer = response.choices[0].message.content
            logger.info(f"Generated answer for query: {query[:50]}...")
            return answer
            
        except Exception as e:
            logger.error(f"Failed to generate answer: {str(e)}")
            return f"I apologize, but I encountered an error while generating the answer: {str(e)}"