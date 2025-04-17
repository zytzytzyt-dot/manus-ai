import asyncio
import os
import subprocess
import threading
from typing import Dict, Optional, List


class AsyncDockerizedTerminal:
    """Async interface for terminal interaction with Docker containers.
    
    Provides asynchronous command execution in Docker containers with
    timeout support and environment variable management.
    """
    def __init__(
        self, 
        container_id: str, 
        working_dir: str = "/", 
        env_vars: Optional[Dict[str, str]] = None
    ):
        """Initialize terminal for Docker container.
        
        Args:
            container_id: Docker container ID
            working_dir: Working directory in container
            env_vars: Environment variables
        """
        self.container_id = container_id
        self.working_dir = working_dir
        self.env_vars = env_vars or {}
        self._exec_lock = asyncio.Lock()
    
    async def init(self):
        """Initialize the terminal."""
        # Create working directory if it doesn't exist
        await self.run_command(f"mkdir -p {self.working_dir}")
    
    async def run_command(self, cmd: str, timeout: Optional[int] = None) -> str:
        """Run a command in the container.
        
        Args:
            cmd: Command to run
            timeout: Execution timeout in seconds
            
        Returns:
            Command output
            
        Raises:
            TimeoutError: If command execution times out
            Exception: If command execution fails
        """
        async with self._exec_lock:
            # Prepare environment variable arguments
            env_args = []
            for key, value in self.env_vars.items():
                env_args.extend(["-e", f"{key}={value}"])
                
            # Prepare docker exec command
            docker_cmd = [
                "docker", "exec",
                *env_args,
                "-w", self.working_dir,
                self.container_id,
                "/bin/sh", "-c", cmd
            ]
            
            # Set up process
            process = await asyncio.create_subprocess_exec(
                *docker_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            try:
                # Run with timeout
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(), 
                    timeout=timeout
                )
                
                # Check for errors
                if process.returncode != 0:
                    error_msg = stderr.decode('utf-8', errors='replace')
                    return f"Error (code {process.returncode}): {error_msg}"
                    
                # Return stdout
                return stdout.decode('utf-8', errors='replace')
                
            except asyncio.TimeoutError:
                # Kill process on timeout
                try:
                    process.kill()
                except ProcessLookupError:
                    pass
                    
                raise TimeoutError(f"Command execution timed out after {timeout} seconds")
    
    async def close(self):
        """Close the terminal."""
        # No specific cleanup needed for Docker exec
        pass


class AsyncStdioTerminal:
    """Async interface for stdio-based terminal processes.
    
    Provides asynchronous command execution via stdio streams with
    timeout support and environment variable management.
    """
    def __init__(
        self, 
        command: str, 
        args: Optional[List[str]] = None,
        working_dir: str = "/", 
        env_vars: Optional[Dict[str, str]] = None
    ):
        """Initialize stdio terminal.
        
        Args:
            command: Command to run
            args: Command arguments
            working_dir: Working directory
            env_vars: Environment variables
        """
        self.command = command
        self.args = args or []
        self.working_dir = working_dir
        self.env_vars = env_vars or {}
        self.process = None
        self._exec_lock = asyncio.Lock()
    
    async def init(self):
        """Initialize the terminal."""
        # Start the process
        env = os.environ.copy()
        env.update(self.env_vars)
        
        self.process = await asyncio.create_subprocess_exec(
            self.command,
            *self.args,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=self.working_dir,
            env=env
        )
    
    async def run_command(self, cmd: str, timeout: Optional[int] = None) -> str:
        """Run a command via stdio.
        
        Args:
            cmd: Command to run
            timeout: Execution timeout in seconds
            
        Returns:
            Command output
            
        Raises:
            TimeoutError: If command execution times out
            Exception: If command execution fails
        """
        if not self.process:
            raise RuntimeError("Terminal not initialized")
            
        async with self._exec_lock:
            try:
                # Write command to stdin
                cmd_bytes = (cmd + "\n").encode()
                self.process.stdin.write(cmd_bytes)
                await self.process.stdin.drain()
                
                # Read output with timeout
                output_future = asyncio.create_task(self._read_output())
                result = await asyncio.wait_for(output_future, timeout=timeout)
                
                return result
                
            except asyncio.TimeoutError:
                raise TimeoutError(f"Command execution timed out after {timeout} seconds")
            
    async def _read_output(self) -> str:
        """Read output from stdout until prompt."""
        # This is a simplified implementation
        # In a real implementation, you'd need to handle prompt detection
        output = []
        
        while True:
            line = await self.process.stdout.readline()
            if not line:
                break
                
            decoded = line.decode('utf-8', errors='replace')
            output.append(decoded)
            
            # Check for prompt indicator
            if decoded.rstrip().endswith('$ ') or decoded.rstrip().endswith('# '):
                break
        
        return ''.join(output)
    
    async def close(self):
        """Close the terminal."""
        if self.process:
            try:
                self.process.terminate()
                await asyncio.wait_for(self.process.wait(), timeout=5)
            except (asyncio.TimeoutError, ProcessLookupError):
                self.process.kill()
