import asyncio
import os
import shutil
import tempfile
import uuid
from typing import Dict, List, Optional

from pydantic import BaseModel, Field

from app.config.settings import get_settings
from app.utils.logger import get_logger

# Set up logger
logger = get_logger(__name__)

class VMConfig(BaseModel):
    """Configuration for a virtual machine sandbox."""
    
    memory_limit: str = Field(default="256m", description="Memory limit")
    cpu_limit: float = Field(default=0.5, description="CPU limit (cores)")
    disk_limit: str = Field(default="1g", description="Disk space limit")
    network_enabled: bool = Field(default=False, description="Whether networking is enabled")
    workspace_dir: str = Field(default="/workspace", description="VM workspace directory")
    timeout: int = Field(default=30, description="Default execution timeout")
    
    class Config:
        validate_assignment = True


class VirtualMachine:
    """Manages virtual machine sandboxes for code execution.
    
    Provides isolated execution environments with resource limits
    and security measures.
    """
    def __init__(self, config: Optional[VMConfig] = None):
        """Initialize virtual machine.
        
        Args:
            config: VM configuration
        """
        self.config = config or VMConfig()
        self.container_id: Optional[str] = None
        self.temp_dir: Optional[str] = None
        self._container_client = None
        
    async def create(self) -> str:
        """Create and start a new VM instance.
        
        Returns:
            Container ID
            
        Raises:
            RuntimeError: If VM creation fails
        """
        try:
            # Create temporary directory for VM files
            self.temp_dir = tempfile.mkdtemp(prefix="vm_")
            
            # Import Docker here to avoid dependency if not used
            try:
                import docker
                from docker.errors import DockerException
            except ImportError:
                raise RuntimeError("Docker SDK not installed. Install with: pip install docker")
            
            # Initialize Docker client
            self._container_client = docker.from_env()
            
            # Get settings
            settings = get_settings()
            
            # Prepare container configuration
            container_name = f"manus_vm_{uuid.uuid4().hex[:8]}"
            image = settings.sandbox.image or "python:3.9-slim"
            
            # Prepare host config
            host_config = {
                "mem_limit": self.config.memory_limit,
                "cpu_period": 100000,
                "cpu_quota": int(100000 * self.config.cpu_limit),
                "network_mode": "none" if not self.config.network_enabled else "bridge",
                "binds": {
                    self.temp_dir: {
                        "bind": self.config.workspace_dir,
                        "mode": "rw"
                    }
                }
            }
            
            # Create container
            container = self._container_client.containers.create(
                image=image,
                command="tail -f /dev/null",  # Keep container running
                hostname="sandbox",
                working_dir=self.config.workspace_dir,
                name=container_name,
                detach=True,
                tty=True,
                **host_config
            )
            
            # Start container
            container.start()
            
            # Store container ID
            self.container_id = container.id
            
            logger.info(f"Created VM container: {container_name} ({self.container_id})")
            
            return self.container_id
            
        except Exception as e:
            # Clean up on failure
            await self.cleanup()
            
            error_msg = f"Failed to create VM: {str(e)}"
            logger.error(error_msg)
            raise RuntimeError(error_msg)
    
    async def run_command(self, command: str, timeout: Optional[int] = None) -> str:
        """Run a command in the VM.
        
        Args:
            command: Command to execute
            timeout: Execution timeout
            
        Returns:
            Command output
            
        Raises:
            RuntimeError: If command execution fails
        """
        if not self.container_id or not self._container_client:
            raise RuntimeError("VM not initialized")
            
        try:
            # Get container
            container = self._container_client.containers.get(self.container_id)
            
            # Execute command
            exec_result = container.exec_run(
                command,
                workdir=self.config.workspace_dir,
                environment={"PYTHONUNBUFFERED": "1"},
                stdin=False,
                stdout=True,
                stderr=True
            )
            
            # Get command output
            exit_code = exec_result.exit_code
            output = exec_result.output.decode('utf-8', errors='replace')
            
            if exit_code != 0:
                logger.warning(f"Command exited with non-zero code: {exit_code}")
                logger.warning(f"Output: {output}")
                
            return output
            
        except Exception as e:
            error_msg = f"Failed to run command: {str(e)}"
            logger.error(error_msg)
            raise RuntimeError(error_msg)
    
    async def copy_to_vm(self, local_path: str, vm_path: str) -> None:
        """Copy a file from host to VM.
        
        Args:
            local_path: Local file path
            vm_path: Target path in VM
            
        Raises:
            RuntimeError: If copy operation fails
        """
        if not self.container_id or not self._container_client:
            raise RuntimeError("VM not initialized")
            
        try:
            # Get container
            container = self._container_client.containers.get(self.container_id)
            
            # Resolve VM path
            full_vm_path = os.path.join(self.config.workspace_dir, vm_path.lstrip('/'))
            
            # Ensure local file exists
            if not os.path.exists(local_path):
                raise RuntimeError(f"Local file not found: {local_path}")
                
            # Create target directory
            await self.run_command(f"mkdir -p $(dirname {full_vm_path})")
            
            # Copy file to container
            with open(local_path, 'rb') as f:
                data = f.read()
                container.put_archive(os.path.dirname(full_vm_path), data)
                
            logger.debug(f"Copied {local_path} to VM at {full_vm_path}")
            
        except Exception as e:
            error_msg = f"Failed to copy file to VM: {str(e)}"
            logger.error(error_msg)
            raise RuntimeError(error_msg)
    
    async def copy_from_vm(self, vm_path: str, local_path: str) -> None:
        """Copy a file from VM to host.
        
        Args:
            vm_path: Source path in VM
            local_path: Target local file path
            
        Raises:
            RuntimeError: If copy operation fails
        """
        if not self.container_id or not self._container_client:
            raise RuntimeError("VM not initialized")
            
        try:
            # Get container
            container = self._container_client.containers.get(self.container_id)
            
            # Resolve VM path
            full_vm_path = os.path.join(self.config.workspace_dir, vm_path.lstrip('/'))
            
            # Create target directory
            os.makedirs(os.path.dirname(local_path), exist_ok=True)
            
            # Get file from container
            bits, stat = container.get_archive(full_vm_path)
            
            # Write bits to file
            with open(local_path, 'wb') as f:
                for chunk in bits:
                    f.write(chunk)
                    
            logger.debug(f"Copied {full_vm_path} from VM to {local_path}")
            
        except Exception as e:
            error_msg = f"Failed to copy file from VM: {str(e)}"
            logger.error(error_msg)
            raise RuntimeError(error_msg)
    
    async def cleanup(self) -> None:
        """Clean up VM resources."""
        # Stop and remove container
        if self.container_id and self._container_client:
            try:
                container = self._container_client.containers.get(self.container_id)
                container.stop(timeout=5)
                container.remove(force=True)
                logger.info(f"Removed VM container: {self.container_id}")
            except Exception as e:
                logger.error(f"Error cleaning up VM container: {str(e)}")
            finally:
                self.container_id = None
                
        # Remove temporary directory
        if self.temp_dir and os.path.exists(self.temp_dir):
            try:
                shutil.rmtree(self.temp_dir)
                logger.debug(f"Removed VM temp directory: {self.temp_dir}")
            except Exception as e:
                logger.error(f"Error removing VM temp directory: {str(e)}")
            finally:
                self.temp_dir = None
    
    async def __aenter__(self):
        """Async context manager entry."""
        await self.create()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.cleanup()