import asyncio
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, TypeVar, Generic
from datetime import datetime
import json

from pydantic import BaseModel, Field

T = TypeVar('T')

class NotificationLevel(str, Enum):
    """Notification severity levels."""
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class Notification(BaseModel, Generic[T]):
    """Represents a notification message."""
    
    id: str = Field(..., description="Unique notification identifier")
    level: NotificationLevel = Field(default=NotificationLevel.INFO, description="Notification level")
    message: str = Field(..., description="Notification message")
    topic: str = Field(..., description="Notification topic")
    timestamp: datetime = Field(default_factory=datetime.now, description="Creation time")
    data: Optional[T] = Field(None, description="Additional notification data")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Notification metadata")
    
    class Config:
        arbitrary_types_allowed = True
    
    def to_json(self) -> str:
        """Convert notification to JSON string."""
        obj = {
            "id": self.id,
            "level": self.level,
            "message": self.message,
            "topic": self.topic,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata
        }
        
        # Add data if serializable
        if self.data:
            try:
                # Test if data is JSON serializable
                json.dumps(self.data)
                obj["data"] = self.data
            except (TypeError, OverflowError):
                # If not serializable, convert to string
                obj["data"] = str(self.data)
                
        return json.dumps(obj)


class NotificationCallback(BaseModel):
    """A subscription callback for notifications."""
    
    id: str = Field(..., description="Unique callback identifier")
    topics: Set[str] = Field(default_factory=set, description="Topics of interest")
    callback: Callable[[Notification], None] = Field(..., description="Callback function")
    
    class Config:
        arbitrary_types_allowed = True


class NotificationSystem:
    """System for managing notifications and subscriptions.
    
    Enables async publication and subscription of notifications
    across the application.
    """
    def __init__(self):
        """Initialize the notification system."""
        self.callbacks: Dict[str, NotificationCallback] = {}
        self.history: Dict[str, List[Notification]] = {}
        self.max_history_per_topic = 100
        self._lock = asyncio.Lock()
    
    async def publish(
        self, 
        topic: str, 
        message: str, 
        level: NotificationLevel = NotificationLevel.INFO,
        data: Any = None,
        metadata: Dict[str, Any] = None
    ) -> Notification:
        """Publish a notification.
        
        Args:
            topic: Notification topic
            message: Notification message
            level: Notification level
            data: Additional notification data
            metadata: Additional metadata
            
        Returns:
            Published notification
        """
        import uuid
        
        # Create notification
        notification = Notification(
            id=str(uuid.uuid4()),
            level=level,
            message=message,
            topic=topic,
            data=data,
            metadata=metadata or {}
        )
        
        # Store in history
        async with self._lock:
            if topic not in self.history:
                self.history[topic] = []
                
            # Add to history and limit size
            self.history[topic].append(notification)
            if len(self.history[topic]) > self.max_history_per_topic:
                self.history[topic] = self.history[topic][-self.max_history_per_topic:]
        
        # Dispatch to subscribers
        await self._dispatch_notification(notification)
        
        return notification
    
    async def subscribe(self, topics: List[str], callback: Callable[[Notification], None]) -> str:
        """Subscribe to notifications.
        
        Args:
            topics: List of topics to subscribe to
            callback: Function to call when notification occurs
            
        Returns:
            Subscription ID
        """
        import uuid
        
        # Create subscription
        subscription_id = str(uuid.uuid4())
        
        subscription = NotificationCallback(
            id=subscription_id,
            topics=set(topics),
            callback=callback
        )
        
        # Store subscription
        async with self._lock:
            self.callbacks[subscription_id] = subscription
            
        return subscription_id
    
    async def unsubscribe(self, subscription_id: str) -> bool:
        """Unsubscribe from notifications.
        
        Args:
            subscription_id: Subscription ID
            
        Returns:
            True if unsubscribed, False if not found
        """
        async with self._lock:
            if subscription_id in self.callbacks:
                del self.callbacks[subscription_id]
                return True
                
        return False
    
    async def get_history(self, topic: str, limit: int = 10) -> List[Notification]:
        """Get notification history for a topic.
        
        Args:
            topic: Topic to get history for
            limit: Maximum number of notifications to return
            
        Returns:
            List of notifications
        """
        if topic not in self.history:
            return []
            
        # Return most recent notifications first
        return list(reversed(self.history[topic][-limit:]))
    
    async def clear_history(self, topic: Optional[str] = None) -> None:
        """Clear notification history.
        
        Args:
            topic: Optional topic to clear (if None, clears all)
        """
        async with self._lock:
            if topic:
                # Clear specific topic
                if topic in self.history:
                    self.history[topic] = []
            else:
                # Clear all history
                self.history = {}
    
    async def _dispatch_notification(self, notification: Notification) -> None:
        """Dispatch a notification to all matching subscribers.
        
        Args:
            notification: Notification to dispatch
        """
        # Get matching callbacks
        matching_callbacks = [
            callback for callback in self.callbacks.values()
            if notification.topic in callback.topics
        ]
        
        # Dispatch to all matching callbacks
        for callback in matching_callbacks:
            try:
                # Schedule callback in event loop
                asyncio.create_task(self._run_callback(callback, notification))
            except Exception as e:
                print(f"Error dispatching notification: {str(e)}")
    
    async def _run_callback(self, callback: NotificationCallback, notification: Notification) -> None:
        """Run a callback function safely.
        
        Args:
            callback: Callback to run
            notification: Notification to pass to callback
        """
        try:
            # Run callback
            callback.callback(notification)
        except Exception as e:
            print(f"Error in notification callback: {str(e)}")
