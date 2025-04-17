import os
import re
import json
import uuid
import hashlib
from typing import Any, Dict, List, Optional, Union
import time
from datetime import datetime

def generate_id(prefix: str = "") -> str:
    """Generate a unique ID.
    
    Args:
        prefix: ID prefix
        
    Returns:
        Unique ID
    """
    return f"{prefix}{uuid.uuid4().hex[:16]}"

def hash_text(text: str) -> str:
    """Hash text using SHA-256.
    
    Args:
        text: Text to hash
        
    Returns:
        Hashed text
    """
    return hashlib.sha256(text.encode()).hexdigest()

def stringify(value: Any) -> str:
    """Convert a value to string.
    
    Args:
        value: Value to convert
        
    Returns:
        String representation
    """
    if isinstance(value, (dict, list)):
        try:
            return json.dumps(value, ensure_ascii=False)
        except:
            return str(value)
    return str(value)

def ensure_directory(path: str) -> str:
    """Ensure a directory exists.
    
    Args:
        path: Directory path
        
    Returns:
        Absolute path
    """
    abs_path = os.path.abspath(path)
    os.makedirs(abs_path, exist_ok=True)
    return abs_path

def parse_timestring(timestring: str) -> datetime:
    """Parse a time string into a datetime object.
    
    Args:
        timestring: Time string (e.g., "2023-01-01T12:00:00Z")
        
    Returns:
        Datetime object
        
    Raises:
        ValueError: If time string is invalid
    """
    formats = [
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%dT%H:%M:%S.%fZ",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d"
    ]
    
    for fmt in formats:
        try:
            return datetime.strptime(timestring, fmt)
        except ValueError:
            continue
            
    raise ValueError(f"Invalid time string format: {timestring}")

def timeit(func):
    """Decorator to measure function execution time.
    
    Args:
        func: Function to decorate
        
    Returns:
        Decorated function
    """
    import functools
    import inspect
    
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()
        result = func(*args, **kwargs)
        end_time = time.time()
        print(f"Function {func.__name__} took {end_time - start_time:.4f} seconds to execute")
        return result
    
    @functools.wraps(func)
    async def async_wrapper(*args, **kwargs):
        start_time = time.time()
        result = await func(*args, **kwargs)
        end_time = time.time()
        print(f"Function {func.__name__} took {end_time - start_time:.4f} seconds to execute")
        return result
    
    if inspect.iscoroutinefunction(func):
        return async_wrapper
    else:
        return wrapper

def truncate_text(text: str, max_length: int = 100, suffix: str = "...") -> str:
    """Truncate text to a maximum length.
    
    Args:
        text: Text to truncate
        max_length: Maximum length
        suffix: Suffix to append
        
    Returns:
        Truncated text
    """
    if len(text) <= max_length:
        return text
    return text[:max_length] + suffix

def extract_urls(text: str) -> List[str]:
    """Extract URLs from text.
    
    Args:
        text: Text to extract URLs from
        
    Returns:
        List of URLs
    """
    url_pattern = r'https?://(?:[-\w.]|(?:%[\da-fA-F]{2}))+'
    return re.findall(url_pattern, text)

def deep_merge(dict1: Dict, dict2: Dict) -> Dict:
    """Deep merge two dictionaries.
    
    Args:
        dict1: First dictionary
        dict2: Second dictionary
        
    Returns:
        Merged dictionary
    """
    result = dict1.copy()
    
    for key, value in dict2.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value
            
    return result

def sanitize_filename(filename: str) -> str:
    """Sanitize a filename.
    
    Args:
        filename: Filename to sanitize
        
    Returns:
        Sanitized filename
    """
    # Replace invalid characters with underscores
    sanitized = re.sub(r'[\\/*?:"<>|]', "_", filename)
    
    # Limit length to 255 characters
    if len(sanitized) > 255:
        extension = os.path.splitext(sanitized)[1]
        sanitized = sanitized[:255 - len(extension)] + extension
        
    return sanitized

def format_duration(seconds: float) -> str:
    """Format a duration in seconds to a human-readable string.
    
    Args:
        seconds: Duration in seconds
        
    Returns:
        Formatted duration string
    """
    if seconds < 60:
        return f"{seconds:.1f} seconds"
    elif seconds < 3600:
        minutes = seconds / 60
        return f"{minutes:.1f} minutes"
    else:
        hours = seconds / 3600
        return f"{hours:.1f} hours"

def is_valid_json(text: str) -> bool:
    """Check if text is valid JSON.
    
    Args:
        text: Text to check
        
    Returns:
        True if valid JSON, False otherwise
    """
    try:
        json.loads(text)
        return True
    except:
        return False

def retry(max_attempts: int = 3, delay: float = 1.0, backoff: float = 2.0, exceptions: tuple = (Exception,)):
    """Decorator for retrying a function on exception.
    
    Args:
        max_attempts: Maximum number of attempts
        delay: Initial delay between attempts
        backoff: Backoff factor
        exceptions: Exceptions to catch
        
    Returns:
        Decorated function
    """
    import functools
    import inspect
    
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            mtries, mdelay = max_attempts, delay
            while mtries > 1:
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    msg = f"{str(e)}, Retrying in {mdelay} seconds..."
                    print(msg)
                    time.sleep(mdelay)
                    mtries -= 1
                    mdelay *= backoff
            return func(*args, **kwargs)
        
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            import asyncio
            mtries, mdelay = max_attempts, delay
            while mtries > 1:
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    msg = f"{str(e)}, Retrying in {mdelay} seconds..."
                    print(msg)
                    await asyncio.sleep(mdelay)
                    mtries -= 1
                    mdelay *= backoff
            return await func(*args, **kwargs)
        
        if inspect.iscoroutinefunction(func):
            return async_wrapper
        else:
            return wrapper
        
    return decorator