import logging
import httpx
from typing import Dict, Any

logger = logging.getLogger(__name__)

# HTTP客户端用于外部API调用
http_client = httpx.AsyncClient()

# 文件API配置
FILE_API_CONFIG = {}
FILE_API_BASE_URL = ""
FILE_API_KEY = ""
FILE_DEFAULT_DAEMON_ID = ""
FILE_DEFAULT_UUID = ""


def init_file_api(config):
    """
    初始化文件API配置
    
    Args:
        config: 文件API配置
    """
    global FILE_API_CONFIG, FILE_API_BASE_URL, FILE_API_KEY
    global FILE_DEFAULT_DAEMON_ID, FILE_DEFAULT_UUID
    
    FILE_API_CONFIG = config
    FILE_API_BASE_URL = FILE_API_CONFIG.get('base_url', '')
    FILE_API_KEY = FILE_API_CONFIG.get('api_key', '')
    FILE_DEFAULT_DAEMON_ID = FILE_API_CONFIG.get('default_daemon_id', '')
    FILE_DEFAULT_UUID = FILE_API_CONFIG.get('default_uuid', '')


async def api_get_file(
    daemonId: str,
    uuid: str,
    target: str
):
    """
    GET /api/files/ 接口，用于获取远程文件内容
    
    Args:
        daemonId: Daemon ID (查询参数)
        uuid: Instance UUID (查询参数)
        target: 目标文件路径 (查询参数)
        
    Returns:
        远程API的响应结果
    """
    if not FILE_API_BASE_URL or not FILE_API_KEY:
        logger.error("文件API请求失败: 配置缺失")
        return {"status": "error", "message": "文件API配置缺失"}
    
    # 构建请求URL
    url = FILE_API_BASE_URL
    params = {
        "apikey": FILE_API_KEY,
        "daemonId": daemonId,
        "uuid": uuid,
        "target": target
    }
    
    try:
        # 发送GET请求到远程API
        response = await http_client.get(url, params=params)
        response.raise_for_status()
        
        # 记录成功状态
        logger.info("文件API请求成功")
        
        # 返回远程API的响应
        return {
            "status": "success",
            "data": response.json() if response.content else None
        }
    except httpx.HTTPError as e:
        logger.error(f"文件API请求失败: {e}")
        return {
            "status": "error",
            "message": f"请求失败: {str(e)}",
            "detail": str(e)
        }
    except Exception as e:
        logger.error(f"处理文件API请求时发生错误: {e}")
        return {
            "status": "error",
            "message": f"处理请求时发生错误: {str(e)}",
            "detail": str(e)
        }


async def api_put_file(
    daemonId: str,
    uuid: str,
    target: str
):
    """
    PUT /api/files/ 接口，用于访问远程文件API
    
    Args:
        daemonId: Daemon ID (查询参数)
        uuid: Instance UUID (查询参数)
        target: 目标文件路径 (请求体)
        
    Returns:
        远程API的响应结果
    """
    if not FILE_API_BASE_URL or not FILE_API_KEY:
        logger.error("文件API请求失败: 配置缺失")
        return {"status": "error", "message": "文件API配置缺失"}
    
    # 构建请求URL
    url = FILE_API_BASE_URL
    params = {
        "apikey": FILE_API_KEY,
        "daemonId": daemonId,
        "uuid": uuid
    }
    
    # 构建请求体
    body = {
        "target": target
    }
    
    try:
        # 发送PUT请求到远程API
        response = await http_client.put(url, params=params, json=body)
        response.raise_for_status()
        
        # 记录成功状态
        logger.info("文件API请求成功")
        
        # 返回远程API的响应
        return {
            "status": "success",
            "data": response.json() if response.content else None
        }
    except httpx.HTTPError as e:
        logger.error(f"文件API请求失败: {e}")
        return {
            "status": "error",
            "message": f"请求失败: {str(e)}",
            "detail": str(e)
        }
    except Exception as e:
        logger.error(f"处理文件API请求时发生错误: {e}")
        return {
            "status": "error",
            "message": f"处理请求时发生错误: {str(e)}",
            "detail": str(e)
        }


async def get_http_client():
    """
    获取HTTP客户端实例
    """
    return http_client


async def execute_command(
    daemonId: str,
    uuid: str,
    command: str
):
    """
    执行远程实例命令
    
    Args:
        daemonId: Daemon ID (查询参数)
        uuid: Instance UUID (查询参数)
        command: 要执行的命令
        
    Returns:
        远程API的响应结果
    """
    if not FILE_API_BASE_URL or not FILE_API_KEY:
        logger.error("命令执行API请求失败: 配置缺失")
        return {"status": "error", "message": "文件API配置缺失"}
    
    url = FILE_API_BASE_URL.replace('/api/files', '/api/protected_instance/command')
    params = {
        "apikey": FILE_API_KEY,
        "daemonId": daemonId,
        "uuid": uuid,
        "command": command
    }
    
    try:
        # 发送GET请求到远程API
        response = await http_client.get(url, params=params)
        response.raise_for_status()
        
        # 记录成功状态
        logger.info("命令执行API请求成功")
        
        # 返回远程API的响应
        return {
            "status": "success",
            "data": response.json() if response.content else None
        }
    except httpx.HTTPError as e:
        logger.error(f"命令执行API请求失败: {e}")
        return {
            "status": "error",
            "message": f"请求失败: {str(e)}",
            "detail": str(e)
        }
    except Exception as e:
        logger.error(f"处理命令执行API请求时发生错误: {e}")
        return {
            "status": "error",
            "message": f"处理请求时发生错误: {str(e)}",
            "detail": str(e)
        }