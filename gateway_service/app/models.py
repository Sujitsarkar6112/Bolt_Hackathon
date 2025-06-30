from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from datetime import datetime


class ChatMessage(BaseModel):
    """Chat message model"""
    content: str = Field(..., min_length=1, description="Message content")
    user_id: Optional[str] = Field(default="default", description="User identifier")


class WSMessage(BaseModel):
    """WebSocket message wrapper"""
    type: str = Field(..., description="Message type")
    data: Dict[str, Any] = Field(default_factory=dict, description="Message data")
    id: Optional[str] = Field(None, description="Message ID")
    timestamp: Optional[str] = Field(None, description="Message timestamp")


class SSEEvent(BaseModel):
    """Server-Sent Event model"""
    type: str = Field(..., description="Event type")
    data: Dict[str, Any] = Field(default_factory=dict, description="Event data")
    id: Optional[str] = Field(None, description="Event ID")
    retry: Optional[int] = Field(None, description="Retry interval in milliseconds")
    
    def dict(self, **kwargs) -> Dict[str, Any]:
        """Override dict method to exclude None values"""
        result = super().dict(exclude_none=True, **kwargs)
        return result


class ConnectionInfo(BaseModel):
    """Connection information"""
    connection_id: str
    connected_at: datetime
    connection_type: str  # 'websocket' or 'sse'
    user_id: Optional[str] = None
    last_activity: datetime