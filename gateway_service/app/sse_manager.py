import asyncio
import json
import logging
from typing import Dict, AsyncGenerator, Optional
import httpx
from datetime import datetime
import uuid
import re

from .models import ChatMessage, SSEEvent
from .config import settings

logger = logging.getLogger(__name__)


class SSEManager:
    """Manages Server-Sent Events connections and streaming"""
    
    def __init__(self):
        self.connections: Dict[str, asyncio.Queue] = {}
        self.http_client = httpx.AsyncClient(timeout=30.0)
    
    async def connect(self, connection_id: str):
        """Register new SSE connection"""
        self.connections[connection_id] = asyncio.Queue()
        logger.info(f"SSE connection registered: {connection_id}")
    
    async def disconnect(self, connection_id: str):
        """Remove SSE connection"""
        if connection_id in self.connections:
            del self.connections[connection_id]
            logger.info(f"SSE connection removed: {connection_id}")
    
    async def get_events(self, connection_id: str) -> AsyncGenerator[SSEEvent, None]:
        """Get event stream for specific connection"""
        if connection_id not in self.connections:
            return
        
        queue = self.connections[connection_id]
        
        try:
            while True:
                # Wait for event with timeout
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=30.0)
                    yield event
                except asyncio.TimeoutError:
                    # Send keepalive event
                    yield SSEEvent(
                        type="keepalive",
                        data={"timestamp": datetime.utcnow().isoformat()}
                    )
        except Exception as e:
            logger.error(f"Error in SSE event stream: {e}")
    
    async def send_event(self, connection_id: str, event: SSEEvent):
        """Send event to specific SSE connection"""
        if connection_id in self.connections:
            try:
                await self.connections[connection_id].put(event)
            except Exception as e:
                logger.error(f"Failed to send SSE event: {e}")
    
    async def broadcast_event(self, event: SSEEvent):
        """Broadcast event to all SSE connections"""
        for connection_id in list(self.connections.keys()):
            await self.send_event(connection_id, event)
    
    async def process_chat_message(self, message: ChatMessage) -> str:
        """Process chat message and return response ID for tracking"""
        response_id = str(uuid.uuid4())
        
        # Start background task to process and stream response
        asyncio.create_task(self._stream_chat_response(message, response_id))
        
        return response_id
    
    async def _stream_chat_response(self, message: ChatMessage, response_id: str):
        """Stream chat response via SSE with proper service routing"""
        try:
            # Send processing start event
            await self.broadcast_event(SSEEvent(
                type="chat_start",
                data={
                    "response_id": response_id,
                    "message": message.dict()
                }
            ))
            
            content = message.content.lower()
            
            # Route to appropriate service
            if "/forecast" in content or "forecast" in content:
                await self._stream_forecast_response(message, response_id)
            elif "/ask" in content or "ask" in content:
                await self._stream_rag_response(message, response_id)
            else:
                await self._stream_backend_response(message, response_id)
            
        except Exception as e:
            logger.error(f"Error streaming chat response: {e}")
            
            # Send error event
            await self.broadcast_event(SSEEvent(
                type="chat_error",
                data={
                    "response_id": response_id,
                    "error": str(e)
                }
            ))
    
    async def _stream_backend_response(self, message: ChatMessage, response_id: str):
        """Stream backend chat response"""
        # Call backend API with streaming
        async with self.http_client.stream(
            "POST",
            f"{settings.backend_url}/chat",
            json={
                "content": message.content,
                "user_id": message.user_id
            }
        ) as response:
            
            if response.status_code != 200:
                raise Exception(f"Backend error: {response.status_code}")
            
            # Stream response chunks
            accumulated_content = ""
            async for chunk in response.aiter_text():
                if chunk.strip():
                    accumulated_content += chunk
                    
                    await self.broadcast_event(SSEEvent(
                        type="chat_chunk",
                        data={
                            "response_id": response_id,
                            "content": chunk,
                            "accumulated": accumulated_content
                        }
                    ))
                    
                    # Small delay to prevent overwhelming clients
                    await asyncio.sleep(0.01)
        
        # Send completion event
        await self.broadcast_event(SSEEvent(
            type="chat_complete",
            data={
                "response_id": response_id,
                "final_content": accumulated_content
            }
        ))
    
    async def _stream_forecast_response(self, message: ChatMessage, response_id: str):
        """Stream forecast response via forecast service"""
        # Extract SKU from message
        sku_match = re.search(r'sku[-_]?(\w+)', message.content.lower())
        sku = sku_match.group(0) if sku_match else "default"
        
        # Call forecast service
        response = await self.http_client.get(f"{settings.forecast_url}/forecast/{sku}")
        
        if response.status_code != 200:
            raise Exception(f"Forecast service error: {response.status_code}")
        
        forecast_data = response.json()
        
        # Validate through filter service
        validated_response = await self._validate_response(forecast_data)
        
        # Send forecast event
        await self.broadcast_event(SSEEvent(
            type="forecast_complete",
            data={
                "response_id": response_id,
                "forecast_data": validated_response
            }
        ))
    
    async def _stream_rag_response(self, message: ChatMessage, response_id: str):
        """Stream RAG response via RAG service"""
        # Call RAG service
        response = await self.http_client.post(
            f"{settings.rag_url}/ask",
            json={"query": message.content}
        )
        
        if response.status_code != 200:
            raise Exception(f"RAG service error: {response.status_code}")
        
        rag_data = response.json()
        
        # Validate through filter service
        validated_response = await self._validate_response(rag_data)
        
        # Send RAG event
        await self.broadcast_event(SSEEvent(
            type="rag_complete",
            data={
                "response_id": response_id,
                "rag_data": validated_response
            }
        ))
    
    async def _validate_response(self, response_data: dict) -> dict:
        """Validate response through filter service"""
        try:
            # Extract text content for validation
            text_content = ""
            if isinstance(response_data, dict):
                text_content = str(response_data.get("content", ""))
            else:
                text_content = str(response_data)
            
            # Call filter service
            filter_response = await self.http_client.post(
                f"{settings.filter_url}/validate",
                json={"text": text_content}
            )
            
            if filter_response.status_code == 422:
                # Filter service rejected the response
                return {"error": "Response blocked by safety filter", "details": filter_response.json()}
            elif filter_response.status_code != 200:
                logger.warning(f"Filter service error: {filter_response.status_code}")
                # Continue with original response if filter service fails
                return response_data
            
            # Use validated response
            filter_data = filter_response.json()
            if not filter_data.get("is_safe", True):
                return {"error": "Response blocked by safety filter", "warnings": filter_data.get("warnings", [])}
            
            # Update content with validated text if available
            if isinstance(response_data, dict) and "validated_text" in filter_data:
                response_data["content"] = filter_data["validated_text"]
            
            return response_data
            
        except Exception as e:
            logger.error(f"Filter validation error: {e}")
            # Return original response if validation fails
            return response_data