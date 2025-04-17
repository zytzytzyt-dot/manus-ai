import os
from typing import Dict, List, Optional, Any
import tomli

from pydantic import BaseModel, Field

from app.sandbox.vm import VMConfig


class LLMConfig(BaseModel):
    """LLM configuration."""
    
    model: str = Field(default="gpt-4o", description="Model name")
    base_url: str = Field(default="https://api.openai.com/v1", description="API base URL")
    api_key: Optional[str] = Field(None, description="API key")
    max_tokens: int = Field(default=4096, description="Maximum tokens")
    temperature: float = Field(default=0.0, description="Temperature")


class BrowserConfig(BaseModel):
    """Browser configuration."""
    
    browser_type: str = Field(default="chromium", description="Browser type")
    headless: bool = Field(default=True, description="Whether to run in headless mode")
    disable_security: bool = Field(default=True, description="Whether to disable security features")
    max_content_length: int = Field(default=10000, description="Maximum content length")
    extra_chromium_args: List[str] = Field(default_factory=list, description="Extra Chromium args")
    chrome_instance_path: Optional[str] = Field(None, description="Chrome instance path")


class ProxyConfig(BaseModel):
    """Proxy configuration."""
    
    server: Optional[str] = Field(None, description="Proxy server URL")
    username: Optional[str] = Field(None, description="Proxy username")
    password: Optional[str] = Field(None, description="Proxy password")


class Settings(BaseModel):
    """Application settings."""
    
    # Path configuration
    workspace_dir: str = Field(default="./workspace", description="Workspace directory")
    log_dir: str = Field(default="./logs", description="Log directory")
    
    # LLM configuration
    llm: LLMConfig = Field(default_factory=LLMConfig, description="LLM configuration")
    
    # Vision LLM configuration (for image processing)
    vision_llm: Optional[LLMConfig] = Field(None, description="Vision LLM configuration")
    
    # Browser configuration
    browser: BrowserConfig = Field(default_factory=BrowserConfig, description="Browser configuration")
    browser_proxy: Optional[ProxyConfig] = Field(None, description="Browser proxy configuration")
    
    # Sandbox configuration
    sandbox: VMConfig = Field(default_factory=VMConfig, description="Sandbox configuration")
    
    # Search configuration
    search_api_key: Optional[str] = Field(None, description="Search API key")
    search_endpoint: Optional[str] = Field(None, description="Search API endpoint")
    
    # Agent configuration
    max_agent_steps: int = Field(default=20, description="Maximum agent steps")
    max_agent_execution_time: int = Field(default=300, description="Maximum agent execution time (seconds)")
    
    # Async configuration
    worker_count: int = Field(default=2, description="Number of background workers")
    
    # Other settings
    debug: bool = Field(default=False, description="Debug mode")
    cache_enabled: bool = Field(default=True, description="Whether to use cache")


_settings_instance = None

def load_settings() -> Settings:
    """Load settings from config file and environment variables.
    
    Returns:
        Settings instance
    """
    # Default config file path
    config_file = os.environ.get("MANUS_CONFIG_FILE", "config/config.toml")
    
    settings_dict = {}
    
    # Load from config file if it exists
    if os.path.exists(config_file):
        try:
            with open(config_file, "rb") as f:
                config_data = tomli.load(f)
                settings_dict.update(config_data)
        except Exception as e:
            print(f"Error loading config file: {str(e)}")
    
    # Override with environment variables
    
    # LLM settings
    llm_model = os.environ.get("MANUS_LLM_MODEL")
    if llm_model:
        if "llm" not in settings_dict:
            settings_dict["llm"] = {}
        settings_dict["llm"]["model"] = llm_model
        
    llm_api_key = os.environ.get("MANUS_LLM_API_KEY")
    if llm_api_key:
        if "llm" not in settings_dict:
            settings_dict["llm"] = {}
        settings_dict["llm"]["api_key"] = llm_api_key
        
    llm_base_url = os.environ.get("MANUS_LLM_BASE_URL")
    if llm_base_url:
        if "llm" not in settings_dict:
            settings_dict["llm"] = {}
        settings_dict["llm"]["base_url"] = llm_base_url
    
    # Path settings
    workspace_dir = os.environ.get("MANUS_WORKSPACE_DIR")
    if workspace_dir:
        settings_dict["workspace_dir"] = workspace_dir
        
    log_dir = os.environ.get("MANUS_LOG_DIR")
    if log_dir:
        settings_dict["log_dir"] = log_dir
    
    # Debug mode
    debug = os.environ.get("MANUS_DEBUG")
    if debug:
        settings_dict["debug"] = debug.lower() in ("true", "1", "yes")
    
    # Create settings instance
    return Settings(**settings_dict)

def get_settings() -> Settings:
    """Get settings instance (singleton).
    
    Returns:
        Settings instance
    """
    global _settings_instance
    if _settings_instance is None:
        _settings_instance = load_settings()
    return _settings_instance