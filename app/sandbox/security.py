import os
import re
import json
from typing import Dict, List, Optional, Set, Tuple, Union

from pydantic import BaseModel, Field

from app.utils.logger import get_logger

# Set up logger
logger = get_logger(__name__)

class SecurityPolicy(BaseModel):
    """Security policy for sandboxed environments."""
    
    allowed_modules: Set[str] = Field(
        default_factory=lambda: {
            # Standard library safe modules
            "math", "random", "time", "datetime", "collections", 
            "itertools", "functools", "operator", "string", "re",
            "json", "base64", "hashlib", "uuid", "os.path",
            
            # Web-related modules
            "urllib.parse", "http.client", "urllib.request",
            
            # Data processing
            "csv", "io", "tempfile"
        },
        description="Allowed Python modules"
    )
    
    blocked_modules: Set[str] = Field(
        default_factory=lambda: {
            # System access
            "subprocess", "sys", "os.system", "os.popen", "os.execl",
            "os.execle", "os.execlp", "os.execlpe", "os.execv", "os.execve",
            "os.execvp", "os.execvpe", "os.spawn", "os.spawnl", "os.spawnle",
            "os.spawnlp", "os.spawnlpe", "os.spawnv", "os.spawnve", "os.spawnvp",
            
            # File operations beyond sandbox
            "os.remove", "os.unlink", "os.rmdir", "os.chmod", "os.chown",
            "shutil.rmtree", "shutil.copy", "shutil.move",
            
            # Network access (if not explicitly allowed)
            "socket", "asyncio.subprocess", "telnetlib", "smtplib",
            
            # Code execution
            "eval", "exec", "compile", "__import__", "builtins.__import__"
        },
        description="Blocked Python modules/functions"
    )
    
    allowed_directories: Set[str] = Field(
        default_factory=lambda: {"/tmp", "/workspace"},
        description="Allowed filesystem directories"
    )
    
    max_execution_time: int = Field(
        default=30, 
        description="Maximum execution time in seconds"
    )
    
    memory_limit_mb: int = Field(
        default=256,
        description="Memory limit in MB"
    )


class SecurityCheck(BaseModel):
    """Security check result."""
    
    status: bool = Field(..., description="Whether check passed")
    rule: str = Field(..., description="Rule that was checked")
    details: str = Field(..., description="Check details")


class SecurityManager:
    """Manages security policies and code validation.
    
    Provides security checks and policy enforcement for
    sandboxed code execution.
    """
    def __init__(self, policy: Optional[SecurityPolicy] = None):
        """Initialize security manager.
        
        Args:
            policy: Security policy
        """
        self.policy = policy or SecurityPolicy()
        
    def validate_code(self, code: str) -> List[SecurityCheck]:
        """Validate code against security policy.
        
        Args:
            code: Code to validate
            
        Returns:
            List of security check results
        """
        results = []
        
        # Check for blocked modules and functions
        module_check = self._check_modules(code)
        results.append(module_check)
        
        # Check for file operations outside allowed directories
        file_check = self._check_file_operations(code)
        results.append(file_check)
        
        # Check for potential infinite loops
        loop_check = self._check_infinite_loops(code)
        results.append(loop_check)
        
        # Check for network access
        network_check = self._check_network_access(code)
        results.append(network_check)
        
        # Check for eval/exec
        eval_check = self._check_eval_exec(code)
        results.append(eval_check)
        
        return results
    
    def is_code_safe(self, code: str) -> Tuple[bool, Optional[str]]:
        """Check if code is safe to execute.
        
        Args:
            code: Code to check
            
        Returns:
            Tuple of (is_safe, reason)
        """
        results = self.validate_code(code)
        
        # Check if any check failed
        for check in results:
            if not check.status:
                return False, check.details
                
        return True, None
    
    def _check_modules(self, code: str) -> SecurityCheck:
        """Check for blocked modules and functions.
        
        Args:
            code: Code to check
            
        Returns:
            Security check result
        """
        # Look for import statements
        import_pattern = r"(import\s+([^\s,;]+))|"
        import_pattern += r"(from\s+([^\s,;]+)\s+import)"
        
        imports = re.findall(import_pattern, code)
        
        # Extract module names
        imported_modules = set()
        for match in imports:
            if match[1]:  # import module
                module = match[1].strip()
                imported_modules.add(module)
            elif match[3]:  # from module import
                module = match[3].strip()
                imported_modules.add(module)
        
        # Check for blocked modules
        blocked = [m for m in imported_modules if self._is_module_blocked(m)]
        
        if blocked:
            return SecurityCheck(
                status=False,
                rule="blocked_modules",
                details=f"Code uses blocked modules: {', '.join(blocked)}"
            )
            
        return SecurityCheck(
            status=True,
            rule="blocked_modules",
            details="No blocked modules detected"
        )
    
    def _check_file_operations(self, code: str) -> SecurityCheck:
        """Check for file operations outside allowed directories.
        
        Args:
            code: Code to check
            
        Returns:
            Security check result
        """
        # Look for file operations
        file_patterns = [
            r"open\s*\(\s*['\"]([^'\"]+)['\"]",
            r"os\.path\.join\s*\(\s*['\"]([^'\"]+)['\"]",
            r"with\s+open\s*\(\s*['\"]([^'\"]+)['\"]",
            r"os\.(?:mkdir|rmdir|remove|unlink)\s*\(\s*['\"]([^'\"]+)['\"]"
        ]
        
        paths = []
        for pattern in file_patterns:
            paths.extend(re.findall(pattern, code))
        
        # Check if paths are within allowed directories
        suspicious_paths = []
        for path in paths:
            # Skip relative paths (they're confined to working directory)
            if not os.path.isabs(path):
                continue
                
            # Check if path is in allowed directories
            if not any(path.startswith(allowed) for allowed in self.policy.allowed_directories):
                suspicious_paths.append(path)
        
        if suspicious_paths:
            return SecurityCheck(
                status=False,
                rule="file_operations",
                details=f"Code attempts to access files outside allowed directories: {', '.join(suspicious_paths)}"
            )
            
        return SecurityCheck(
            status=True,
            rule="file_operations",
            details="File operations appear safe"
        )
    
    def _check_infinite_loops(self, code: str) -> SecurityCheck:
        """Check for potential infinite loops.
        
        Args:
            code: Code to check
            
        Returns:
            Security check result
        """
        # Look for loops without clear exit conditions
        # This is a simplistic check and could have false positives
        loop_patterns = [
            r"while\s+True\s*:",
            r"while\s+1\s*:",
            r"for\s+.+\s+in\s+range\s*\(\s*[^,)]+\s*\)\s*:"
        ]
        
        for pattern in loop_patterns:
            matches = re.findall(pattern, code)
            
            # For each potential infinite loop, check if there's a break statement in the same block
            if matches:
                # Simple check: if there's no break statement after a while True or similar
                if "break" not in code and "return" not in code:
                    return SecurityCheck(
                        status=False,
                        rule="infinite_loops",
                        details="Code may contain infinite loops without exit conditions"
                    )
        
        return SecurityCheck(
            status=True,
            rule="infinite_loops",
            details="No obvious infinite loops detected"
        )
    
    def _check_network_access(self, code: str) -> SecurityCheck:
        """Check for network access.
        
        Args:
            code: Code to check
            
        Returns:
            Security check result
        """
        # Look for common network-related operations
        network_patterns = [
            r"socket\.",
            r"requests\.",
            r"urllib\.request",
            r"http\.client",
            r"aiohttp\.",
            r"ftplib\.",
            r"smtplib\."
        ]
        
        # If network is not allowed, check for attempts
        network_allowed = any("requests" in m or "urllib" in m for m in self.policy.allowed_modules)
        
        if not network_allowed:
            for pattern in network_patterns:
                if re.search(pattern, code):
                    return SecurityCheck(
                        status=False,
                        rule="network_access",
                        details="Code attempts to access network, which is not allowed"
                    )
        
        return SecurityCheck(
            status=True,
            rule="network_access",
            details="No unauthorized network access detected"
        )
    
    def _check_eval_exec(self, code: str) -> SecurityCheck:
        """Check for eval/exec usage.
        
        Args:
            code: Code to check
            
        Returns:
            Security check result
        """
        # Look for eval/exec usage
        eval_patterns = [
            r"eval\s*\(",
            r"exec\s*\(",
            r"__import__\s*\(",
            r"globals\s*\(\s*\)\s*\[\s*['\"]__builtins__['\"]\s*\]\s*\[\s*['\"]__import__['\"]\s*\]"
        ]
        
        for pattern in eval_patterns:
            if re.search(pattern, code):
                return SecurityCheck(
                    status=False,
                    rule="eval_exec",
                    details="Code uses eval() or exec(), which are not allowed for security reasons"
                )
        
        return SecurityCheck(
            status=True,
            rule="eval_exec",
            details="No eval/exec usage detected"
        )
    
    def _is_module_blocked(self, module: str) -> bool:
        """Check if a module is blocked.
        
        Args:
            module: Module name
            
        Returns:
            True if module is blocked
        """
        # Check if module is explicitly blocked
        if module in self.policy.blocked_modules:
            return True
            
        # Check if module is a submodule of a blocked module
        for blocked in self.policy.blocked_modules:
            if module.startswith(f"{blocked}."):
                return True
                
        # If we have an allowlist and module is not in it, it's blocked
        if self.policy.allowed_modules and module not in self.policy.allowed_modules:
            # Allow submodules of allowed modules
            for allowed in self.policy.allowed_modules:
                if module.startswith(f"{allowed}."):
                    return False
            return True
            
        return False
