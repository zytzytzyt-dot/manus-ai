import asyncio
import os
import json
import tempfile
from typing import Dict, List, Optional, Union

from pydantic import BaseModel

from app.config.settings import get_settings
from app.sandbox.vm import VirtualMachine, VMConfig
from app.sandbox.security import SecurityManager, SecurityPolicy
from app.utils.logger import get_logger

# Set up logger
logger = get_logger(__name__)

class SandboxClient:
    """Client for interacting with sandbox environments.
    
    Provides a unified interface for executing code and managing
    sandbox resources securely.
    """
    def __init__(self):
        """Initialize the sandbox client."""
        self.vm: Optional[VirtualMachine] = None
        self.security_manager = SecurityManager()
        self._initialized = False
        self._lock = asyncio.Lock()
    
    async def create(
        self,
        config: Optional[VMConfig] = None,
        volume_bindings: Optional[Dict[str, str]] = None
    ) -> None:
        """Create and initialize the sandbox.
        
        Args:
            config: VM configuration
            volume_bindings: Volume bindings
            
        Raises:
            RuntimeError: If sandbox creation fails
        """
        async with self._lock:
            # Clean up existing VM if any
            await self.cleanup()
            
            # Get settings
            settings = get_settings()
            
            # Create new VM
            self.vm = VirtualMachine(config or settings.sandbox)
            await self.vm.create()
            
            # Set up volume bindings if provided
            if volume_bindings:
                for host_path, vm_path in volume_bindings.items():
                    # Ensure host path exists
                    if not os.path.exists(host_path):
                        os.makedirs(host_path, exist_ok=True)
                        
                    # Create directory in VM
                    await self.vm.run_command(f"mkdir -p {vm_path}")
            
            self._initialized = True
            logger.info("Sandbox initialized")
    
    async def run_command(self, command: str, timeout: Optional[int] = None) -> str:
        """Run a command in the sandbox.
        
        Args:
            command: Command to execute
            timeout: Execution timeout
            
        Returns:
            Command output
            
        Raises:
            RuntimeError: If sandbox not initialized or command execution fails
        """
        await self._ensure_initialized()
        
        if not self.vm:
            raise RuntimeError("Sandbox VM not initialized")
            
        return await self.vm.run_command(command, timeout)
    
    async def execute_python(self, code: str, timeout: Optional[int] = None) -> str:
        """Execute Python code in the sandbox.
        
        Args:
            code: Python code to execute
            timeout: Execution timeout
            
        Returns:
            Execution output
            
        Raises:
            RuntimeError: If code is unsafe or execution fails
        """
        # Validate code security
        is_safe, reason = self.security_manager.is_code_safe(code)
        if not is_safe:
            raise RuntimeError(f"Code rejected for security reasons: {reason}")
            
        await self._ensure_initialized()
        
        if not self.vm:
            raise RuntimeError("Sandbox VM not initialized")
            
        try:
            # Create temporary file
            file_id = os.urandom(4).hex()
            file_path = f"/tmp/script_{file_id}.py"
            
            # Write code to file
            await self.write_file(file_path, code)
            
            # Execute code
            command = f"cd /tmp && python3 {file_path}"
            result = await self.vm.run_command(command, timeout or 30)
            
            # Clean up
            await self.vm.run_command(f"rm -f {file_path}")
            
            return result
            
        except Exception as e:
            error_msg = f"Python execution failed: {str(e)}"
            logger.error(error_msg)
            raise RuntimeError(error_msg)
    
    async def copy_from(self, container_path: str, local_path: str) -> None:
        """Copy a file from the sandbox to the host.
        
        Args:
            container_path: Source path in sandbox
            local_path: Target path on host
            
        Raises:
            RuntimeError: If sandbox not initialized or copy fails
        """
        await self._ensure_initialized()
        
        if not self.vm:
            raise RuntimeError("Sandbox VM not initialized")
            
        await self.vm.copy_from_vm(container_path, local_path)
    
    async def copy_to(self, local_path: str, container_path: str) -> None:
        """Copy a file from the host to the sandbox.
        
        Args:
            local_path: Source path on host
            container_path: Target path in sandbox
            
        Raises:
            RuntimeError: If sandbox not initialized or copy fails
        """
        await self._ensure_initialized()
        
        if not self.vm:
            raise RuntimeError("Sandbox VM not initialized")
            
        await self.vm.copy_to_vm(local_path, container_path)
    
    async def read_file(self, path: str) -> str:
        """Read a file from the sandbox.
        
        Args:
            path: File path in sandbox
            
        Returns:
            File content
            
        Raises:
            RuntimeError: If sandbox not initialized or read fails
        """
        await self._ensure_initialized()
        
        if not self.vm:
            raise RuntimeError("Sandbox VM not initialized")
            
        # Create a temporary file to store the content
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            tmp_path = tmp.name
            
        try:
            # Copy file from sandbox to temporary file
            await self.vm.copy_from_vm(path, tmp_path)
            
            # Read content
            with open(tmp_path, 'r', encoding='utf-8') as f:
                content = f.read()
                
            return content
            
        except Exception as e:
            error_msg = f"Failed to read file {path}: {str(e)}"
            logger.error(error_msg)
            raise RuntimeError(error_msg)
            
        finally:
            # Clean up temporary file
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
    
    async def write_file(self, path: str, content: str) -> None:
        """Write content to a file in the sandbox.
        
        Args:
            path: File path in sandbox
            content: Content to write
            
        Raises:
            RuntimeError: If sandbox not initialized or write fails
        """
        await self._ensure_initialized()
        
        if not self.vm:
            raise RuntimeError("Sandbox VM not initialized")
            
        # Create a temporary file with the content
        with tempfile.NamedTemporaryFile(delete=False, mode='w', encoding='utf-8') as tmp:
            tmp.write(content)
            tmp_path = tmp.name
            
        try:
            # Copy file to sandbox
            await self.vm.copy_to_vm(tmp_path, path)
            
        except Exception as e:
            error_msg = f"Failed to write file {path}: {str(e)}"
            logger.error(error_msg)
            raise RuntimeError(error_msg)
            
        finally:
            # Clean up temporary file
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
    
    async def cleanup(self) -> None:
        """Clean up sandbox resources."""
        async with self._lock:
            if self.vm:
                await self.vm.cleanup()
                self.vm = None
                
            self._initialized = False
            logger.info("Sandbox cleaned up")
    
    async def _ensure_initialized(self) -> None:
        """Ensure sandbox is initialized.
        
        Raises:
            RuntimeError: If sandbox not initialized
        """
        if not self._initialized or not self.vm:
            # Auto-initialize with default settings
            await self.create()


# Global sandbox client instance
SANDBOX_CLIENT = SandboxClient()
