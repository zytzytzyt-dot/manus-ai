import uuid
from datetime import datetime
from typing import Dict, List, Optional, Any

from pydantic import BaseModel, Field, EmailStr


class UserSettings(BaseModel):
    """User settings and preferences."""
    
    theme: str = Field(default="light", description="UI theme")
    language: str = Field(default="en", description="Language preference")
    notifications_enabled: bool = Field(default=True, description="Whether notifications are enabled")
    max_tasks_per_page: int = Field(default=10, description="Maximum tasks to display per page")
    default_agent: Optional[str] = Field(None, description="Default agent to use")
    custom_settings: Dict[str, Any] = Field(default_factory=dict, description="Custom user settings")


class User(BaseModel):
    """Represents a user of the system.
    
    Encapsulates user details, preferences, and authentication info.
    """
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="Unique user identifier")
    username: str = Field(..., description="Username")
    email: EmailStr = Field(..., description="Email address")
    full_name: Optional[str] = Field(None, description="Full name")
    created_at: datetime = Field(default_factory=datetime.now, description="Account creation time")
    last_login: Optional[datetime] = Field(None, description="Last login time")
    is_active: bool = Field(default=True, description="Whether user account is active")
    is_admin: bool = Field(default=False, description="Whether user is an administrator")
    settings: UserSettings = Field(default_factory=UserSettings, description="User settings")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")
    
    def update_setting(self, key: str, value: Any) -> None:
        """Update a user setting.
        
        Args:
            key: Setting key
            value: Setting value
        """
        if hasattr(self.settings, key):
            setattr(self.settings, key, value)
        else:
            self.settings.custom_settings[key] = value
    
    def get_setting(self, key: str, default: Any = None) -> Any:
        """Get a user setting.
        
        Args:
            key: Setting key
            default: Default value if setting not found
            
        Returns:
            Setting value or default
        """
        if hasattr(self.settings, key):
            return getattr(self.settings, key)
        return self.settings.custom_settings.get(key, default)
    
    def update_last_login(self) -> None:
        """Update last login time to current time."""
        self.last_login = datetime.now()
    
    @property
    def account_age_days(self) -> float:
        """Calculate account age in days."""
        return (datetime.now() - self.created_at).total_seconds() / 86400
    
    def add_metadata(self, key: str, value: Any) -> None:
        """Add metadata to user.
        
        Args:
            key: Metadata key
            value: Metadata value
        """
        self.metadata[key] = value
