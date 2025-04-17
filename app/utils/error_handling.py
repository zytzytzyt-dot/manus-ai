import sys
import traceback
from typing import Dict, Optional, Type, Union, Callable, Any
import functools
import inspect
import asyncio

from app.utils.logger import get_logger

# Set up logger
logger = get_logger(__name__)

class ManusError(Exception):
    """Base class for all Manus-AI exceptions."""
    
    def __init__(self, message: str, details: Optional[Dict] = None):
        """Initialize error.
        
        Args:
            message: Error message
            details: Additional error details
        """
        self.message = message
        self.details = details or {}
        super().__init__(message)


class ConfigurationError(ManusError):
    """Error raised for configuration issues."""
    pass


class ToolError(ManusError):
    """Error raised by tools."""
    pass


class AgentError(ManusError):
    """Error raised by agents."""
    pass


class ResourceError(ManusError):
    """Error raised for resource issues."""
    pass


class SecurityError(ManusError):
    """Error raised for security issues."""
    pass


class ValidationError(ManusError):
    """Error raised for validation issues."""
    pass


def handle_exceptions(
    error_classes: Optional[Union[Type[Exception], Dict[Type[Exception], str]]] = None,
    default_message: str = "An unexpected error occurred",
    log_error: bool = True,
    reraise: bool = False
) -> Callable:
    """Decorator for handling exceptions.
    
    Args:
        error_classes: Exception classes to handle
        default_message: Default error message
        log_error: Whether to log the error
        reraise: Whether to reraise the error
        
    Returns:
        Decorated function
    """
    if error_classes is None:
        error_classes = Exception
    
    def decorator(func: Callable) -> Callable:
        """Decorator function.
        
        Args:
            func: Function to decorate
            
        Returns:
            Decorated function
        """
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            """Function wrapper.
            
            Args:
                *args: Positional arguments
                **kwargs: Keyword arguments
                
            Returns:
                Function result or error result
            """
            try:
                return func(*args, **kwargs)
            except Exception as e:
                if isinstance(error_classes, dict):
                    for error_class, message in error_classes.items():
                        if isinstance(e, error_class):
                            if log_error:
                                logger.error(f"{message}: {str(e)}")
                                logger.debug(traceback.format_exc())
                            if reraise:
                                raise
                            return {"error": message, "details": str(e)}
                elif isinstance(e, error_classes):
                    if log_error:
                        logger.error(f"{default_message}: {str(e)}")
                        logger.debug(traceback.format_exc())
                    if reraise:
                        raise
                    return {"error": default_message, "details": str(e)}
                else:
                    # Unexpected error
                    if log_error:
                        logger.error(f"Unexpected error: {str(e)}")
                        logger.error(traceback.format_exc())
                    if reraise:
                        raise
                    return {"error": "An unexpected error occurred", "details": str(e)}
        
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            """Async function wrapper.
            
            Args:
                *args: Positional arguments
                **kwargs: Keyword arguments
                
            Returns:
                Function result or error result
            """
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                if isinstance(error_classes, dict):
                    for error_class, message in error_classes.items():
                        if isinstance(e, error_class):
                            if log_error:
                                logger.error(f"{message}: {str(e)}")
                                logger.debug(traceback.format_exc())
                            if reraise:
                                raise
                            return {"error": message, "details": str(e)}
                elif isinstance(e, error_classes):
                    if log_error:
                        logger.error(f"{default_message}: {str(e)}")
                        logger.debug(traceback.format_exc())
                    if reraise:
                        raise
                    return {"error": default_message, "details": str(e)}
                else:
                    # Unexpected error
                    if log_error:
                        logger.error(f"Unexpected error: {str(e)}")
                        logger.error(traceback.format_exc())
                    if reraise:
                        raise
                    return {"error": "An unexpected error occurred", "details": str(e)}
        
        # Return appropriate wrapper based on whether function is async
        if inspect.iscoroutinefunction(func):
            return async_wrapper
        else:
            return wrapper
    
    return decorator


def setup_global_exception_handler():
    """Set up global exception handlers."""
    # Get asyncio event loop
    loop = asyncio.get_event_loop()
    
    # Set up asyncio exception handler
    def handle_asyncio_exception(loop, context):
        exception = context.get('exception')
        message = context.get('message')
        
        if exception:
            logger.error(f"Unhandled exception in asyncio: {message}")
            logger.error(''.join(traceback.format_exception(
                type(exception), exception, exception.__traceback__
            )))
        else:
            logger.error(f"Asyncio error: {message}")
    
    loop.set_exception_handler(handle_asyncio_exception)
    
    # Set up global exception handler
    def handle_uncaught_exception(exc_type, exc_value, exc_traceback):
        if issubclass(exc_type, KeyboardInterrupt):
            # Let KeyboardInterrupt pass through
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return
            
        logger.critical("Uncaught exception", exc_info=(exc_type, exc_value, exc_traceback))
    
    sys.excepthook = handle_uncaught_exception