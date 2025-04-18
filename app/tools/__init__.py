"""
工具包初始化文件

此模块负责初始化和注册所有可用的工具
"""
from typing import Dict, List, Optional

from app.tools.base import BaseTool
from app.tools.tool_registry import ToolRegistry
from app.tools.browser import BrowserTool
from app.tools.code_execution import CodeExecutionTool
from app.tools.file_operations import FileOperationsTool
from app.tools.llm import LLMTool
from app.tools.search import SearchTool
from app.config.settings import get_settings
from app.utils.logger import get_logger

# 设置日志记录器
logger = get_logger(__name__)

# 创建全局工具注册表
tool_registry = ToolRegistry()

def register_tools() -> ToolRegistry:
    """注册所有可用的工具到全局注册表
    
    Returns:
        工具注册表实例
    """
    # 获取配置
    settings = get_settings()
    enabled_tools = settings.tools.enabled if hasattr(settings, 'tools') and hasattr(settings.tools, 'enabled') else []
    
    # 定义所有可用工具
    available_tools = {
        "browser": BrowserTool(),
        "code_execution": CodeExecutionTool(),
        "file_operations": FileOperationsTool(),
        "llm": LLMTool(),
        "search": SearchTool()
    }
    
    # 注册启用的工具
    for tool_name, tool in available_tools.items():
        # 检查工具是否启用
        if not enabled_tools or tool_name in enabled_tools:
            try:
                tool_registry.register_tool(tool)
                logger.info(f"已注册工具: {tool_name}")
            except ValueError as e:
                logger.warning(f"注册工具 {tool_name} 失败: {str(e)}")
    
    logger.info(f"已注册 {len(tool_registry.tools)} 个工具")
    return tool_registry

def get_tool_registry() -> ToolRegistry:
    """获取全局工具注册表
    
    如果注册表为空，会自动注册工具
    
    Returns:
        工具注册表实例
    """
    if not tool_registry.tools:
        register_tools()
    return tool_registry

# 在导入时自动注册工具
register_tools()
