import json
import os
import time
from typing import Any, Dict, List, Optional, Union
import aiofiles

from pydantic import BaseModel, Field

class StorageItem(BaseModel):
    """Represents an item in persistent storage."""
    
    key: str = Field(..., description="Unique key of the item")
    value: Any = Field(..., description="Item value")
    timestamp: float = Field(default_factory=time.time, description="Creation/update timestamp")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Item metadata")


class PersistentStorage(BaseModel):
    """Manages persistence of data to disk.
    
    Provides asynchronous storage, retrieval, and management of 
    persistent data with support for different storage formats.
    """
    storage_dir: str = Field(..., description="Directory for storage files")
    format: str = Field(default="json", description="Storage format (json)")
    namespace: str = Field(default="default", description="Storage namespace")
    cache: Dict[str, StorageItem] = Field(default_factory=dict, description="In-memory cache")
    cache_enabled: bool = Field(default=True, description="Whether to use cache")
    
    class Config:
        arbitrary_types_allowed = True
    
    def __init__(self, **data):
        super().__init__(**data)
        # Create storage directory if it doesn't exist
        os.makedirs(self.storage_dir, exist_ok=True)
    
    async def set(self, key: str, value: Any, **metadata) -> None:
        """Store an item.
        
        Args:
            key: Item key
            value: Item value
            **metadata: Additional metadata
        """
        # Create storage item
        item = StorageItem(
            key=key,
            value=value,
            timestamp=time.time(),
            metadata=metadata
        )
        
        # Update cache if enabled
        if self.cache_enabled:
            self.cache[key] = item
            
        # Persist to storage
        await self._write_item(key, item)
    
    async def get(self, key: str, default: Any = None) -> Any:
        """Retrieve an item.
        
        Args:
            key: Item key
            default: Default value if not found
            
        Returns:
            Item value or default
        """
        # Check cache first if enabled
        if self.cache_enabled and key in self.cache:
            return self.cache[key].value
            
        # Try to load from storage
        try:
            item = await self._read_item(key)
            
            # Update cache if enabled
            if self.cache_enabled:
                self.cache[key] = item
                
            return item.value
        except FileNotFoundError:
            return default
    
    async def get_with_metadata(self, key: str) -> Optional[StorageItem]:
        """Retrieve an item with its metadata.
        
        Args:
            key: Item key
            
        Returns:
            StorageItem or None if not found
        """
        # Check cache first if enabled
        if self.cache_enabled and key in self.cache:
            return self.cache[key]
            
        # Try to load from storage
        try:
            item = await self._read_item(key)
            
            # Update cache if enabled
            if self.cache_enabled:
                self.cache[key] = item
                
            return item
        except FileNotFoundError:
            return None
    
    async def has(self, key: str) -> bool:
        """Check if an item exists.
        
        Args:
            key: Item key
            
        Returns:
            True if item exists
        """
        # Check cache first if enabled
        if self.cache_enabled and key in self.cache:
            return True
            
        # Check if file exists
        file_path = self._get_file_path(key)
        return os.path.exists(file_path)
    
    async def delete(self, key: str) -> bool:
        """Delete an item.
        
        Args:
            key: Item key
            
        Returns:
            True if item deleted, False if not found
        """
        # Remove from cache if enabled
        if self.cache_enabled and key in self.cache:
            del self.cache[key]
            
        # Delete file if it exists
        file_path = self._get_file_path(key)
        if os.path.exists(file_path):
            os.remove(file_path)
            return True
        return False
    
    async def list_keys(self, prefix: str = "") -> List[str]:
        """List all keys in storage.
        
        Args:
            prefix: Optional key prefix filter
            
        Returns:
            List of keys
        """
        # Get all files in storage directory
        keys = []
        
        # Get namespace prefix
        namespace_prefix = f"{self.namespace}_" if self.namespace else ""
        
        # List files in storage directory
        for filename in os.listdir(self.storage_dir):
            # Check if file belongs to namespace
            if not filename.startswith(namespace_prefix):
                continue
                
            # Extract key from filename
            if self.format == "json" and filename.endswith(".json"):
                key = filename[len(namespace_prefix):-5]  # Remove namespace prefix and .json extension
                
                # Apply prefix filter
                if prefix and not key.startswith(prefix):
                    continue
                    
                keys.append(key)
                
        return keys
    
    async def clear(self) -> None:
        """Clear all items in storage."""
        # Clear cache if enabled
        if self.cache_enabled:
            self.cache.clear()
            
        # Get namespace prefix
        namespace_prefix = f"{self.namespace}_" if self.namespace else ""
        
        # Delete all files in storage directory
        for filename in os.listdir(self.storage_dir):
            # Check if file belongs to namespace
            if not filename.startswith(namespace_prefix):
                continue
                
            file_path = os.path.join(self.storage_dir, filename)
            if os.path.isfile(file_path):
                os.remove(file_path)
    
    async def _write_item(self, key: str, item: StorageItem) -> None:
        """Write item to storage.
        
        Args:
            key: Item key
            item: Storage item
        """
        file_path = self._get_file_path(key)
        
        # Serialize item
        if self.format == "json":
            async with aiofiles.open(file_path, 'w') as f:
                await f.write(json.dumps(item.dict(), indent=2))
        else:
            raise ValueError(f"Unsupported storage format: {self.format}")
    
    async def _read_item(self, key: str) -> StorageItem:
        """Read item from storage.
        
        Args:
            key: Item key
            
        Returns:
            Storage item
            
        Raises:
            FileNotFoundError: If item not found
        """
        file_path = self._get_file_path(key)
        
        # Check if file exists
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Item not found: {key}")
            
        # Deserialize item
        if self.format == "json":
            async with aiofiles.open(file_path, 'r') as f:
                content = await f.read()
                data = json.loads(content)
                return StorageItem(**data)
        else:
            raise ValueError(f"Unsupported storage format: {self.format}")
    
    def _get_file_path(self, key: str) -> str:
        """Get file path for key.
        
        Args:
            key: Item key
            
        Returns:
            File path
        """
        # Sanitize key
        sanitized_key = key.replace("/", "_").replace("\\", "_")
        
        # Add namespace prefix if needed
        if self.namespace:
            file_name = f"{self.namespace}_{sanitized_key}.{self.format}"
        else:
            file_name = f"{sanitized_key}.{self.format}"
            
        return os.path.join(self.storage_dir, file_name)