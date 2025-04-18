import asyncio
import os
import uuid
import tempfile
from typing import Dict, Optional, ClassVar


from pydantic import Field

from app.tools.base import BaseTool, ToolResult
from app.sandbox.client import SANDBOX_CLIENT
from app.utils.logger import get_logger

# Set up logger
logger = get_logger(__name__)

class CodeExecutionTool(BaseTool):
    """Tool for executing code in a sandboxed environment.
    
    Supports execution of Python code with safety restrictions
    and resource limits.
    """
    name: ClassVar[str] = "code_execution"
    description: ClassVar[str] = "Executes code in a secure sandboxed environment"
    parameters: Dict = {
        "type": "object",
        "properties": {
            "code": {
                "type": "string",
                "description": "The code to execute"
            },
            "language": {
                "type": "string",
                "enum": ["python"],
                "default": "python",
                "description": "Programming language"
            },
            "timeout": {
                "type": "integer",
                "default": 10,
                "description": "Execution timeout in seconds"
            },
            "memory_limit": {
                "type": "string",
                "default": "100m",
                "description": "Memory limit"
            }
        },
        "required": ["code"]
    }
    
    execution_lock: asyncio.Lock = Field(default_factory=asyncio.Lock)
    
    async def execute(self, **kwargs) -> ToolResult:
        """Execute code in a sandboxed environment.
        
        Args:
            **kwargs: Execution parameters:
                - code: The code to execute
                - language: Programming language (python)
                - timeout: Execution timeout in seconds
                - memory_limit: Memory limit for execution
                
        Returns:
            ToolResult with execution output or error
        """
        code = kwargs.get("code")
        if not code:
            return ToolResult(error="No code provided")
            
        language = kwargs.get("language", "python")
        timeout = kwargs.get("timeout", 10)
        memory_limit = kwargs.get("memory_limit", "100m")
        
        # Only Python supported for now
        if language.lower() != "python":
            return ToolResult(error=f"Unsupported language: {language}")
        
        async with self.execution_lock:
            try:
                return await self._execute_python(code, timeout)
            except Exception as e:
                logger.error(f"Code execution error: {str(e)}")
                return ToolResult(error=f"Code execution failed: {str(e)}")
    
    async def _execute_python(self, code: str, timeout: int) -> ToolResult:
        """Execute Python code.
        
        Args:
            code: Python code to execute
            timeout: Execution timeout in seconds
            
        Returns:
            ToolResult with execution output or error
        """
        # Ensure sandbox is initialized
        await self._ensure_sandbox()
        
        # Create a unique file name for this execution
        file_id = str(uuid.uuid4())[:8]
        file_name = f"execution_{file_id}.py"
        file_path = f"/tmp/{file_name}"
        
        try:
            # Write code to file in sandbox
            await SANDBOX_CLIENT.write_file(file_path, code)
            
            # Execute code
            command = f"cd /tmp && python3 {file_name}"
            result = await SANDBOX_CLIENT.run_command(command, timeout)
            
            return ToolResult(
                output=result,
                metadata={
                    "language": "python",
                    "execution_time": timeout
                }
            )
            
        except asyncio.TimeoutError:
            return ToolResult(error=f"Code execution timed out after {timeout} seconds")
            
        except Exception as e:
            return ToolResult(error=f"Code execution error: {str(e)}")
            
        finally:
            # Clean up the file
            try:
                await SANDBOX_CLIENT.run_command(f"rm -f {file_path}")
            except Exception as e:
                logger.error(f"Failed to clean up execution file: {str(e)}")
    
    async def _ensure_sandbox(self):
        """Ensure the sandbox environment is initialized."""
        try:
            # Try running a simple command to test if sandbox is initialized
            await SANDBOX_CLIENT.run_command("echo 'test'")
        except Exception:
            # Initialize sandbox
            from app.config.settings import get_settings
            settings = get_settings()
            
            await SANDBOX_CLIENT.create(
                config=settings.sandbox,
                volume_bindings={}
            )