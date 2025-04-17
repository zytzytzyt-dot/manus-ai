from typing import Any, Dict, List, Optional, Union
import json
import os
from pydantic import BaseModel, Field

class UserPreference(BaseModel):
    """Represents a user preference setting."""
    
    key: str = Field(..., description="Preference key")
    value: Any = Field(..., description="Preference value")
    category: str = Field(default="general", description="Preference category")
    description: Optional[str] = Field(None, description="Preference description")


class PreferenceStore(BaseModel):
    """Manages and persists user preferences.
    
    Provides storage, retrieval, and management of user preferences
    with support for defaults and persistence.
    """
    preferences: Dict[str, Any] = Field(default_factory=dict, description="Current preferences")
    defaults: Dict[str, Any] = Field(default_factory=dict, description="Default preferences")
    storage_path: Optional[str] = Field(None, description="Path to storage file")
    
    class Config:
        arbitrary_types_allowed = True
    
    def __init__(self, **data):
        super().__init__(**data)
        # Load preferences from storage if path provided
        if "storage_path" in data and data["storage_path"]:
            self.load_preferences()
    
    def set(self, key: str, value: Any, category: str = "general", description: Optional[str] = None) -> None:
        """Set a preference value.
        
        Args:
            key: Preference key
            value: Preference value
            category: Preference category
            description: Optional description
        """
        # Store preference
        if category not in self.preferences:
            self.preferences[category] = {}
            
        self.preferences[category][key] = value
        
        # Store metadata if provided
        if description and not self._has_metadata(key, category):
            self._set_metadata(key, category, description)
            
        # Save changes
        self.save_preferences()
    
    def get(self, key: str, category: str = "general", default: Any = None) -> Any:
        """Get a preference value.
        
        Args:
            key: Preference key
            category: Preference category
            default: Default value if not found
            
        Returns:
            Preference value or default
        """
        # Check if category exists
        if category not in self.preferences:
            # Try defaults
            if category in self.defaults and key in self.defaults[category]:
                return self.defaults[category][key]
            return default
            
        # Check if key exists
        if key not in self.preferences[category]:
            # Try defaults
            if category in self.defaults and key in self.defaults[category]:
                return self.defaults[category][key]
            return default
            
        return self.preferences[category][key]
    
    def get_all(self, category: Optional[str] = None) -> Dict[str, Any]:
        """Get all preferences in a category or all preferences.
        
        Args:
            category: Optional category filter
            
        Returns:
            Dictionary of preferences
        """
        if category:
            # Return preferences in specific category
            return self.preferences.get(category, {}).copy()
        else:
            # Return all preferences
            return {
                cat: prefs.copy() 
                for cat, prefs in self.preferences.items()
            }
    def delete(self, key: str, category: str = "general") -> bool:
        """Delete a preference.
        
        Args:
            key: Preference key
            category: Preference category
            
        Returns:
            True if preference deleted, False if not found
        """
        # Check if category exists
        if category not in self.preferences:
            return False
            
        # Check if key exists
        if key not in self.preferences[category]:
            return False
            
        # Delete preference
        del self.preferences[category][key]
        
        # Delete empty category
        if not self.preferences[category]:
            del self.preferences[category]
            
        # Delete metadata
        self._delete_metadata(key, category)
        
        # Save changes
        self.save_preferences()
        
        return True
    
    def set_default(self, key: str, value: Any, category: str = "general") -> None:
        """Set a default preference value.
        
        Args:
            key: Preference key
            value: Default value
            category: Preference category
        """
        # Store default
        if category not in self.defaults:
            self.defaults[category] = {}
            
        self.defaults[category][key] = value
    
    def load_preferences(self) -> bool:
        """Load preferences from storage.
        
        Returns:
            True if loaded successfully, False otherwise
        """
        if not self.storage_path:
            return False
            
        try:
            if os.path.exists(self.storage_path):
                with open(self.storage_path, 'r') as f:
                    data = json.load(f)
                    
                # Update preferences
                self.preferences = data.get('preferences', {})
                self._metadata = data.get('metadata', {})
                
                return True
            return False
        except Exception as e:
            print(f"Error loading preferences: {str(e)}")
            return False
    
    def save_preferences(self) -> bool:
        """Save preferences to storage.
        
        Returns:
            True if saved successfully, False otherwise
        """
        if not self.storage_path:
            return False
            
        try:
            # Create directory if it doesn't exist
            os.makedirs(os.path.dirname(self.storage_path), exist_ok=True)
            
            # Save preferences
            with open(self.storage_path, 'w') as f:
                json.dump({
                    'preferences': self.preferences,
                    'metadata': getattr(self, '_metadata', {})
                }, f, indent=2)
                
            return True
        except Exception as e:
            print(f"Error saving preferences: {str(e)}")
            return False
    
    def reset(self, category: Optional[str] = None) -> None:
        """Reset preferences to defaults.
        
        Args:
            category: Optional category to reset
        """
        if category:
            # Reset specific category
            if category in self.defaults:
                self.preferences[category] = self.defaults[category].copy()
            else:
                # Remove category if no defaults
                if category in self.preferences:
                    del self.preferences[category]
        else:
            # Reset all preferences to defaults
            self.preferences = {}
            for category, defaults in self.defaults.items():
                self.preferences[category] = defaults.copy()
                
        # Save changes
        self.save_preferences()
    
    def import_preferences(self, data: Dict[str, Any]) -> bool:
        """Import preferences from dictionary.
        
        Args:
            data: Preference data to import
            
        Returns:
            True if imported successfully
        """
        try:
            self.preferences = data.get('preferences', {})
            metadata = data.get('metadata', {})
            
            # Set metadata
            self._metadata = metadata
            
            # Save changes
            self.save_preferences()
            
            return True
        except Exception as e:
            print(f"Error importing preferences: {str(e)}")
            return False
    
    def export_preferences(self) -> Dict[str, Any]:
        """Export preferences to dictionary.
        
        Returns:
            Dictionary with preferences and metadata
        """
        return {
            'preferences': self.preferences,
            'metadata': getattr(self, '_metadata', {})
        }
    
    def _has_metadata(self, key: str, category: str) -> bool:
        """Check if metadata exists for preference.
        
        Args:
            key: Preference key
            category: Preference category
            
        Returns:
            True if metadata exists
        """
        if not hasattr(self, '_metadata'):
            self._metadata = {}
            
        if category not in self._metadata:
            return False
            
        return key in self._metadata[category]
    
    def _set_metadata(self, key: str, category: str, description: str) -> None:
        """Set metadata for preference.
        
        Args:
            key: Preference key
            category: Preference category
            description: Preference description
        """
        if not hasattr(self, '_metadata'):
            self._metadata = {}
            
        if category not in self._metadata:
            self._metadata[category] = {}
            
        self._metadata[category][key] = {'description': description}
    
    def _delete_metadata(self, key: str, category: str) -> None:
        """Delete metadata for preference.
        
        Args:
            key: Preference key
            category: Preference category
        """
        if not hasattr(self, '_metadata'):
            return
            
        if category not in self._metadata:
            return
            
        if key in self._metadata[category]:
            del self._metadata[category][key]
            
        # Delete empty category
        if not self._metadata[category]:
            del self._metadata[category]