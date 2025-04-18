import os
import docker
import shutil
import tempfile
import asyncio
from typing import Optional, Dict, Any
from app.utils.logger import get_logger

# 设置日志记录器
logger = get_logger(__name__)

class SandboxVM:
    """沙盒虚拟机实现
    
    提供一个隔离的环境来执行不受信任的代码，
    基于Docker容器实现。
    """
    
    def __init__(self, config=None):
        """初始化沙盒VM
        
        Args:
            config: 可选的VM配置，如果未提供则从全局设置加载
        """
        # 延迟导入，避免循环依赖
        if config is None:
            from app.config.settings import get_settings
            self.config = get_settings().sandbox
        else:
            self.config = config
            
        self.container_id = None
        self.temp_dir = None
        self._container_client = None
        
    async def create(self) -> None:
        """创建沙盒VM
        
        创建一个Docker容器作为沙盒环境
        
        Raises:
            RuntimeError: 如果创建失败
        """
        try:
            # 创建Docker客户端
            self._container_client = docker.from_env()
            
            # 创建临时目录作为工作空间
            self.temp_dir = tempfile.mkdtemp()
            logger.debug(f"创建临时目录: {self.temp_dir}")
            
            # 创建容器
            container = self._container_client.containers.run(
                self.config.image,
                detach=True,
                remove=True,
                volumes={
                    self.temp_dir: {
                        'bind': self.config.workspace_dir,
                        'mode': 'rw'
                    }
                }
            )
            
            self.container_id = container.id
            logger.info(f"创建VM容器: {self.container_id}")
            
        except Exception as e:
            error_msg = f"创建VM失败: {str(e)}"
            logger.error(error_msg)
            
            # 清理资源
            await self.cleanup()
            
            raise RuntimeError(error_msg)
    
    async def run_command(self, command: str) -> str:
        """在VM中运行命令
        
        Args:
            command: 要执行的命令
            
        Returns:
            命令输出
            
        Raises:
            RuntimeError: 如果命令执行失败
        """
        if not self.container_id or not self._container_client:
            raise RuntimeError("VM未初始化")
            
        try:
            # 获取容器
            container = self._container_client.containers.get(self.container_id)
            
            # 执行命令
            exec_result = container.exec_run(
                command,
                workdir=self.config.workspace_dir,
                environment={"PYTHONUNBUFFERED": "1"},
                stdin=False,
                stdout=True,
                stderr=True
            )
            
            # 获取命令输出
            exit_code = exec_result.exit_code
            output = exec_result.output.decode('utf-8', errors='replace')
            
            if exit_code != 0:
                logger.warning(f"命令退出码非零: {exit_code}")
                logger.warning(f"输出: {output}")
                
            return output
            
        except Exception as e:
            error_msg = f"运行命令失败: {str(e)}"
            logger.error(error_msg)
            raise RuntimeError(error_msg)
    
    async def copy_to_vm(self, local_path: str, vm_path: str) -> None:
        """从主机复制文件到VM
        
        Args:
            local_path: 本地文件路径
            vm_path: VM中的目标路径
            
        Raises:
            RuntimeError: 如果复制操作失败
        """
        if not self.container_id or not self._container_client:
            raise RuntimeError("VM未初始化")
            
        try:
            # 获取容器
            container = self._container_client.containers.get(self.container_id)
            
            # 解析VM路径
            full_vm_path = os.path.join(self.config.workspace_dir, vm_path.lstrip('/'))
            
            # 确保本地文件存在
            if not os.path.exists(local_path):
                raise RuntimeError(f"本地文件不存在: {local_path}")
                
            # 创建目标目录
            await self.run_command(f"mkdir -p $(dirname {full_vm_path})")
            
            # 复制文件到容器
            with open(local_path, 'rb') as f:
                data = f.read()
                container.put_archive(os.path.dirname(full_vm_path), data)
                
            logger.debug(f"复制 {local_path} 到VM的 {full_vm_path}")
            
        except Exception as e:
            error_msg = f"复制文件到VM失败: {str(e)}"
            logger.error(error_msg)
            raise RuntimeError(error_msg)
    
    async def copy_from_vm(self, vm_path: str, local_path: str) -> None:
        """从VM复制文件到主机
        
        Args:
            vm_path: VM中的源路径
            local_path: 本地目标文件路径
            
        Raises:
            RuntimeError: 如果复制操作失败
        """
        if not self.container_id or not self._container_client:
            raise RuntimeError("VM未初始化")
            
        try:
            # 获取容器
            container = self._container_client.containers.get(self.container_id)
            
            # 解析VM路径
            full_vm_path = os.path.join(self.config.workspace_dir, vm_path.lstrip('/'))
            
            # 创建目标目录
            os.makedirs(os.path.dirname(local_path), exist_ok=True)
            
            # 从容器获取文件
            bits, stat = container.get_archive(full_vm_path)
            
            # 写入文件
            with open(local_path, 'wb') as f:
                for chunk in bits:
                    f.write(chunk)
                    
            logger.debug(f"复制VM的 {full_vm_path} 到 {local_path}")
            
        except Exception as e:
            error_msg = f"从VM复制文件失败: {str(e)}"
            logger.error(error_msg)
            raise RuntimeError(error_msg)
    
    async def cleanup(self) -> None:
        """清理VM资源"""
        # 停止并移除容器
        if self.container_id and self._container_client:
            try:
                container = self._container_client.containers.get(self.container_id)
                container.stop(timeout=5)
                container.remove(force=True)
                logger.info(f"移除VM容器: {self.container_id}")
            except Exception as e:
                logger.error(f"清理VM容器时出错: {str(e)}")
            finally:
                self.container_id = None
                
        # 移除临时目录
        if self.temp_dir and os.path.exists(self.temp_dir):
            try:
                shutil.rmtree(self.temp_dir)
                logger.debug(f"移除VM临时目录: {self.temp_dir}")
            except Exception as e:
                logger.error(f"移除VM临时目录时出错: {str(e)}")
            finally:
                self.temp_dir = None
    
    async def __aenter__(self):
        """异步上下文管理器入口"""
        await self.create()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器退出"""
        await self.cleanup()
