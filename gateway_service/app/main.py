from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
import asyncio
import json
import logging
from typing import Dict, Any, AsyncGenerator
import httpx
from datetime import datetime
import uuid

from .config import settings
from .models import ChatMessage, SSEEvent
from .websocket_manager import WebSocketManager
from .sse_manager import SSEManager

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Gateway Service",
    description="WebSocket and SSE gateway for DemandBot",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize managers
websocket_manager = WebSocketManager()
sse_manager = SSEManager()


@app.websocket("/chat")
async def websocket_chat_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time chat"""
    connection_id = str(uuid.uuid4())
    
    try:
        await websocket_manager.connect(websocket, connection_id)
        logger.info(f"WebSocket connected: {connection_id}")
        
        while True:
            # Receive message from client
            data = await websocket.receive_text()
            message_data = json.loads(data)
            
            # Validate message
            chat_message = ChatMessage(**message_data.get("data", {}))
            
            # Process chat message
            await websocket_manager.process_chat_message(
                connection_id, 
                chat_message,
                message_data.get("id"),
                message_data.get("timestamp")
            )
            
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected: {connection_id}")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        await websocket_manager.send_error(connection_id, str(e))
    finally:
        await websocket_manager.disconnect(connection_id)


@app.get("/stream")
async def sse_stream_endpoint(request: Request):
    """Server-Sent Events endpoint for streaming responses"""
    
    async def event_stream() -> AsyncGenerator[str, None]:
        connection_id = str(uuid.uuid4())
        
        try:
            # Register SSE connection
            await sse_manager.connect(connection_id)
            
            # Send initial connection event
            yield f"data: {json.dumps({'type': 'connected', 'id': connection_id})}\n\n"
            
            # Stream events
            async for event in sse_manager.get_events(connection_id):
                if await request.is_disconnected():
                    break
                
                yield f"data: {json.dumps(event.dict())}\n\n"
                
        except Exception as e:
            logger.error(f"SSE stream error: {e}")
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
        finally:
            await sse_manager.disconnect(connection_id)
    
    return StreamingResponse(
        event_stream(),
        media_type="text/plain",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Cache-Control"
        }
    )


@app.post("/stream/chat")
async def sse_chat_endpoint(message: ChatMessage):
    """HTTP endpoint to send chat message via SSE"""
    try:
        # Process chat message and stream response
        response_id = await sse_manager.process_chat_message(message)
        
        return {
            "status": "processing",
            "response_id": response_id,
            "message": "Response will be streamed via SSE"
        }
        
    except Exception as e:
        logger.error(f"SSE chat error: {e}")
        return {"error": str(e)}, 500


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "websocket_connections": len(websocket_manager.connections),
        "sse_connections": len(sse_manager.connections)
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8004,
        log_level="info",
        reload=True
    )