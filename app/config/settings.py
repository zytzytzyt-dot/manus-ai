import os
import tomli
from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field

# 配置文件路径
DEFAULT_CONFIG_PATH = "config/default.toml"

class VMConfig(BaseModel):
    image: str = "manus-sandbox:latest"
    workspace_dir: str = "/workspace"
    timeout: int = 60
    memory_limit: str = "1g"
    cpu_limit: float = 1.0

class ToolConfig(BaseModel):
    """工具配置"""
    enabled: List[str] = Field(default_factory=lambda: ["file", "browser", "code", "search"])

class LLMConfig(BaseModel):
    """LLM配置"""
    provider: str = "openai"
    model: str = "gpt-4"
    api_key: str = ""
    base_url: str = "https://api.openai.com/v1"  
    temperature: float = 0.7
    max_tokens: int = 1000
    timeout: int = 30

class MemoryConfig(BaseModel):
    """记忆系统配置"""
    storage_path: str = "data/memory"
    max_history: int = 100
    ttl: int = 86400  # 24小时

class LoggingConfig(BaseModel):
    """日志配置"""
    level: str = "INFO"
    file: str = "logs/manus.log"
    max_size: int = 10485760  # 10MB
    backup_count: int = 5

class UIConfig(BaseModel):
    """UI配置"""
    port: int = 8000
    host: str = "0.0.0.0"
    debug: bool = False
    static_dir: str = "app/ui/static"
    template_dir: str = "app/ui/templates"

class Settings(BaseModel):
    """应用程序设置
    
    包含所有配置项的主类
    """
    workspace_dir: str = "workspace"
    temp_dir: str = "temp"
    
    llm: LLMConfig = LLMConfig()
    tools: ToolConfig = ToolConfig()
    memory: MemoryConfig = MemoryConfig()
    logging: LoggingConfig = LoggingConfig()
    ui: UIConfig = UIConfig()
    sandbox: VMConfig = VMConfig()  # 使用本地定义的VMConfig
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Settings":
        """从字典创建设置
        
        Args:
            data: 配置字典
            
        Returns:
            Settings实例
        """
        settings = Settings()
        
        # 更新顶级设置
        if "workspace_dir" in data:
            settings.workspace_dir = data["workspace_dir"]
        if "temp_dir" in data:
            settings.temp_dir = data["temp_dir"]
            
        # 更新LLM设置
        if "llm" in data:
            settings.llm = LLMConfig(**data["llm"])
            
        # 更新工具设置
        if "tools" in data:
            settings.tools = ToolConfig(**data["tools"])
            
        # 更新记忆设置
        if "memory" in data:
            settings.memory = MemoryConfig(**data["memory"])
            
        # 更新日志设置
        if "logging" in data:
            settings.logging = LoggingConfig(**data["logging"])
            
        # 更新UI设置
        if "ui" in data:
            settings.ui = UIConfig(**data["ui"])
            
        # 更新沙盒设置
        if "sandbox" in data:
            settings.sandbox = VMConfig(**data["sandbox"])
            
        return settings

# 全局设置实例
_settings: Optional[Settings] = None

def load_settings(config_path: Optional[str] = None) -> Settings:
    """加载设置
    
    Args:
        config_path: 配置文件路径，如果未提供则使用环境变量或默认路径
        
    Returns:
        Settings实例
        
    Raises:
        FileNotFoundError: 如果配置文件不存在
        tomli.TOMLDecodeError: 如果配置文件格式无效
    """
    global _settings
    
    # 确定配置文件路径
    if config_path is None:
        config_path = os.environ.get("CONFIG_FILE", DEFAULT_CONFIG_PATH)
        
    # 检查文件是否存在
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"配置文件不存在: {config_path}")
        
    # 读取配置文件
    with open(config_path, "rb") as f:
        config_data = tomli.load(f)
        
    # 创建设置
    _settings = Settings.from_dict(config_data)
    
    # 从环境变量覆盖LLM API密钥
    if "LLM_API_KEY" in os.environ:
        _settings.llm.api_key = os.environ["LLM_API_KEY"]
        
    return _settings

def get_settings() -> Settings:
    """获取设置
    
    如果设置尚未加载，则使用默认路径加载
    
    Returns:
        Settings实例
    """
    global _settings
    
    if _settings is None:
        try:
            _settings = load_settings()
        except (FileNotFoundError, tomli.TOMLDecodeError):
            # 如果加载失败，使用默认设置
            _settings = Settings()
            
    return _settings
