import os
import json
import base64
from typing import Dict, List, Optional, Union, ClassVar

from pydantic import Field

from app.tools.base import BaseTool, ToolResult
from app.config.settings import get_settings
from app.utils.logger import get_logger

# Set up logger
logger = get_logger(__name__)

class FileOperationsTool(BaseTool):
    """Tool for file system operations.
    
    Provides capabilities for reading, writing, listing, and managing files
    within the workspace directory.
    """
    name: ClassVar[str] = "file_operations"
    description: ClassVar[str] = "Performs file operations (read, write, list, etc.) in the workspace"
    parameters: Dict = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["read", "write", "append", "list", "delete", "exists", "mkdir"],
                "description": "The file operation to perform"
            },
            "path": {
                "type": "string",
                "description": "Path to the file or directory (relative to workspace)"
            },
            "content": {
                "type": "string",
                "description": "Content to write to the file"
            },
            "encoding": {
                "type": "string",
                "default": "utf-8",
                "description": "Encoding to use for file operations"
            }
        },
        "required": ["action", "path"]
    }
    
    # Workspace settings
    workspace_dir: str = Field(default="")
    
    def __init__(self, **data):
        super().__init__(**data)
        # Initialize workspace directory from settings
        settings = get_settings()
        self.workspace_dir = settings.workspace_dir
    
    async def execute(self, **kwargs) -> ToolResult:
        """Execute a file operation.
        
        Args:
            **kwargs: Operation parameters:
                - action: Operation to perform (read, write, etc.)
                - path: Target file or directory path
                - content: Content for write operations
                - encoding: File encoding
                
        Returns:
            ToolResult with operation output or error
        """
        action = kwargs.get("action")
        if not action:
            return ToolResult(error="No action specified")
            
        path = kwargs.get("path")
        if not path:
            return ToolResult(error="No path specified")
            
        try:
            # Convert relative path to absolute path within workspace
            absolute_path = self._get_safe_path(path)
            
            # Execute appropriate action
            if action == "read":
                return await self._read_file(absolute_path, kwargs.get("encoding", "utf-8"))
            elif action == "write":
                content = kwargs.get("content")
                if content is None:
                    return ToolResult(error="No content provided for write operation")
                return await self._write_file(absolute_path, content, kwargs.get("encoding", "utf-8"))
            elif action == "append":
                content = kwargs.get("content")
                if content is None:
                    return ToolResult(error="No content provided for append operation")
                return await self._append_file(absolute_path, content, kwargs.get("encoding", "utf-8"))
            elif action == "list":
                return await self._list_directory(absolute_path)
            elif action == "delete":
                return await self._delete_file(absolute_path)
            elif action == "exists":
                return await self._file_exists(absolute_path)
            elif action == "mkdir":
                return await self._make_directory(absolute_path)
            else:
                return ToolResult(error=f"Unknown file operation: {action}")
                
        except Exception as e:
            logger.error(f"File operation error: {str(e)}")
            return ToolResult(error=f"File operation failed: {str(e)}")
    
    def _get_safe_path(self, path: str) -> str:
        """Convert path to safe absolute path within workspace.
        
        Args:
            path: Relative or absolute path
            
        Returns:
            Safe absolute path
            
        Raises:
            ValueError: If path attempts to escape workspace
        """
        # Normalize path to prevent directory traversal
        norm_path = os.path.normpath(path)
        if norm_path.startswith("..") or norm_path.startswith("/"):
            # Convert absolute paths to workspace-relative
            norm_path = norm_path.lstrip("/")
        
        # Join with workspace directory
        absolute_path = os.path.join(self.workspace_dir, norm_path)
        
        # Ensure path is within workspace
        if not os.path.abspath(absolute_path).startswith(os.path.abspath(self.workspace_dir)):
            raise ValueError(f"Path '{path}' attempts to escape workspace directory")
            
        return absolute_path
    
    async def _read_file(self, path: str, encoding: str) -> ToolResult:
        """Read a file.
        
        Args:
            path: Path to file
            encoding: File encoding
            
        Returns:
            ToolResult with file content
        """
        if not os.path.exists(path):
            return ToolResult(error=f"File not found: {path}")
            
        if not os.path.isfile(path):
            return ToolResult(error=f"Not a file: {path}")
            
        try:
            with open(path, "r", encoding=encoding) as f:
                content = f.read()
                
            return ToolResult(
                output=content,
                metadata={
                    "path": path,
                    "size": os.path.getsize(path),
                    "encoding": encoding
                }
            )
        except UnicodeDecodeError:
            # Try reading as binary for non-text files
            try:
                with open(path, "rb") as f:
                    binary_content = f.read()
                
                # For binary files, return info but not content
                return ToolResult(
                    output=f"Binary file read successfully: {path}",
                    metadata={
                        "path": path,
                        "size": os.path.getsize(path),
                        "is_binary": True
                    }
                )
            except Exception as e:
                return ToolResult(error=f"Failed to read file: {str(e)}")
    async def _write_file(self, path: str, content: str, encoding: str) -> ToolResult:
        """Write content to a file, creating it if necessary.
        
        Args:
            path: Path to file
            content: Content to write
            encoding: File encoding
            
        Returns:
            ToolResult with operation result
        """
        try:
            # Create directory if it doesn't exist
            directory = os.path.dirname(path)
            if directory and not os.path.exists(directory):
                os.makedirs(directory, exist_ok=True)
                
            # Write file
            with open(path, "w", encoding=encoding) as f:
                f.write(content)
                
            return ToolResult(
                output=f"File written successfully: {path}",
                metadata={
                    "path": path,
                    "size": len(content.encode(encoding)),
                    "encoding": encoding
                }
            )
        except Exception as e:
            return ToolResult(error=f"Failed to write file: {str(e)}")
    
    async def _append_file(self, path: str, content: str, encoding: str) -> ToolResult:
        """Append content to a file, creating it if necessary.
        
        Args:
            path: Path to file
            content: Content to append
            encoding: File encoding
            
        Returns:
            ToolResult with operation result
        """
        try:
            # Create directory if it doesn't exist
            directory = os.path.dirname(path)
            if directory and not os.path.exists(directory):
                os.makedirs(directory, exist_ok=True)
                
            # Append to file
            with open(path, "a", encoding=encoding) as f:
                f.write(content)
                
            return ToolResult(
                output=f"Content appended successfully to file: {path}",
                metadata={
                    "path": path,
                    "appended_size": len(content.encode(encoding)),
                    "total_size": os.path.getsize(path),
                    "encoding": encoding
                }
            )
        except Exception as e:
            return ToolResult(error=f"Failed to append to file: {str(e)}")
    
    async def _list_directory(self, path: str) -> ToolResult:
        """List contents of a directory.
        
        Args:
            path: Path to directory
            
        Returns:
            ToolResult with directory contents
        """
        if not os.path.exists(path):
            return ToolResult(error=f"Directory not found: {path}")
            
        if not os.path.isdir(path):
            return ToolResult(error=f"Not a directory: {path}")
            
        try:
            entries = os.listdir(path)
            
            # Get detailed information about each entry
            contents = []
            for entry in entries:
                entry_path = os.path.join(path, entry)
                is_dir = os.path.isdir(entry_path)
                
                contents.append({
                    "name": entry,
                    "type": "directory" if is_dir else "file",
                    "size": 0 if is_dir else os.path.getsize(entry_path),
                    "modified": os.path.getmtime(entry_path)
                })
                
            return ToolResult(
                output=f"Directory listing for {path}:\n" + "\n".join(
                    f"{'[DIR]' if item['type'] == 'directory' else '[FILE]'} {item['name']}"
                    for item in contents
                ),
                metadata={
                    "path": path,
                    "contents": contents,
                    "count": len(contents)
                }
            )
        except Exception as e:
            return ToolResult(error=f"Failed to list directory: {str(e)}")
    
    async def _delete_file(self, path: str) -> ToolResult:
        """Delete a file or directory.
        
        Args:
            path: Path to file or directory
            
        Returns:
            ToolResult with operation result
        """
        if not os.path.exists(path):
            return ToolResult(error=f"Path not found: {path}")
            
        try:
            if os.path.isdir(path):
                import shutil
                shutil.rmtree(path)
                return ToolResult(
                    output=f"Directory deleted successfully: {path}",
                    metadata={"path": path, "type": "directory"}
                )
            else:
                os.remove(path)
                return ToolResult(
                    output=f"File deleted successfully: {path}",
                    metadata={"path": path, "type": "file"}
                )
        except Exception as e:
            return ToolResult(error=f"Failed to delete path: {str(e)}")
    
    async def _file_exists(self, path: str) -> ToolResult:
        """Check if a file or directory exists.
        
        Args:
            path: Path to check
            
        Returns:
            ToolResult with existence information
        """
        exists = os.path.exists(path)
        if exists:
            is_dir = os.path.isdir(path)
            return ToolResult(
                output=f"{'Directory' if is_dir else 'File'} exists: {path}",
                metadata={
                    "path": path,
                    "exists": True,
                    "type": "directory" if is_dir else "file",
                    "size": 0 if is_dir else os.path.getsize(path),
                    "modified": os.path.getmtime(path)
                }
            )
        else:
            return ToolResult(
                output=f"Path does not exist: {path}",
                metadata={"path": path, "exists": False}
            )
    
    async def _make_directory(self, path: str) -> ToolResult:
        """Create a directory.
        
        Args:
            path: Path to create
            
        Returns:
            ToolResult with operation result
        """
        if os.path.exists(path):
            if os.path.isdir(path):
                return ToolResult(
                    output=f"Directory already exists: {path}",
                    metadata={"path": path, "created": False}
                )
            else:
                return ToolResult(error=f"Cannot create directory: a file with the same name exists")
                
        try:
            os.makedirs(path, exist_ok=True)
            return ToolResult(
                output=f"Directory created successfully: {path}",
                metadata={"path": path, "created": True}
            )
        except Exception as e:
            return ToolResult(error=f"Failed to create directory: {str(e)}")