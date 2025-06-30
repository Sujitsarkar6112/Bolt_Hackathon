import asyncio
import json
import logging
from typing import Dict, Optional
from fastapi import WebSocket
import httpx
from datetime import datetime

from .models import ChatMessage, WSMessage
from .config import settings

logger = logging.getLogger(__name__)


class WebSocketManager:
    """Manages WebSocket connections and message routing"""
    
    def __init__(self):
        self.connections: Dict[str, WebSocket] = {}
        self.http_client = httpx.AsyncClient(timeout=30.0)
    
    async def connect(self, websocket: WebSocket, connection_id: str):
        """Accept WebSocket connection"""
        await websocket.accept()
        self.connections[connection_id] = websocket
        
        # Send connection confirmation
        await self.send_message(connection_id, {
            "type": "connected",
            "data": {"connection_id": connection_id}
        })
    
    async def disconnect(self, connection_id: str):
        """Remove WebSocket connection"""
        if connection_id in self.connections:
            del self.connections[connection_id]
    
    async def send_message(self, connection_id: str, message: Dict):
        """Send message to specific WebSocket connection"""
        if connection_id in self.connections:
            try:
                await self.connections[connection_id].send_text(json.dumps(message))
            except Exception as e:
                logger.error(f"Failed to send WebSocket message: {e}")
                await self.disconnect(connection_id)
    
    async def send_error(self, connection_id: str, error_message: str):
        """Send error message to WebSocket connection"""
        await self.send_message(connection_id, {
            "type": "error",
            "data": {"error": error_message}
        })
    
    async def process_chat_message(
        self, 
        connection_id: str, 
        message: ChatMessage,
        message_id: Optional[str] = None,
        timestamp: Optional[str] = None
    ):
        """Process chat message and route to appropriate services"""
        try:
            # Send stream start event
            await self.send_message(connection_id, {
                "type": "stream_start",
                "data": {"message_id": message_id}
            })
            
            content = message.content.lower()
            
            # Route forecast requests to forecast service
            if "/forecast" in content or "forecast" in content:
                await self._handle_forecast_request(connection_id, message, message_id)
            # Route RAG ask requests to RAG service
            elif "/ask" in content or "ask" in content:
                await self._handle_rag_request(connection_id, message, message_id)
            # Route general chat to backend
            else:
                await self._handle_chat_request(connection_id, message, message_id)
            
            # Send stream end event
            await self.send_message(connection_id, {
                "type": "stream_end", 
                "data": {"message_id": message_id}
            })
            
        except Exception as e:
            logger.error(f"Error processing chat message: {e}")
            await self.send_error(connection_id, str(e))
    
    async def _handle_chat_request(self, connection_id: str, message: ChatMessage, message_id: str):
        """Handle general chat requests via backend"""
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
            async for chunk in response.aiter_text():
                if chunk.strip():
                    await self.send_message(connection_id, {
                        "type": "stream_chunk",
                        "data": {"content": chunk}
                    })
                    
                    # Small delay to prevent overwhelming client
                    await asyncio.sleep(0.01)
    
    async def _handle_forecast_request(self, connection_id: str, message: ChatMessage, message_id: str):
        """Handle forecast requests via forecast service"""
        # Extract SKU from message (simple parsing)
        import re
        sku_match = re.search(r'sku[-_]?(\w+)', message.content.lower())
        sku = sku_match.group(0) if sku_match else "default"
        
        # Call forecast service
        response = await self.http_client.get(f"{settings.forecast_url}/forecast/{sku}")
        
        if response.status_code != 200:
            raise Exception(f"Forecast service error: {response.status_code}")
        
        forecast_data = response.json()
        
        # Validate through filter service
        validated_response = await self._validate_response(forecast_data)
        
        # Send forecast response
        await self.send_message(connection_id, {
            "type": "forecast_response",
            "data": validated_response
        })
    
    async def _handle_rag_request(self, connection_id: str, message: ChatMessage, message_id: str):
        """Handle RAG ask requests via RAG service"""
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
        
        # Send RAG response
        await self.send_message(connection_id, {
            "type": "rag_response", 
            "data": validated_response
        })
    
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
    
    async def broadcast(self, message: Dict):
        """Broadcast message to all connected WebSocket clients"""
        disconnected = []
        
        for connection_id, websocket in self.connections.items():
            try:
                await websocket.send_text(json.dumps(message))
            except Exception as e:
                logger.error(f"Failed to broadcast to {connection_id}: {e}")
                disconnected.append(connection_id)
        
        # Clean up disconnected clients
        for connection_id in disconnected:
            await self.disconnect(connection_id)