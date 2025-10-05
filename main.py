# uvicorn main:app --reload

import asyncio
import os
import json
from typing import Dict, Any
from fastapi import FastAPI, Query, Body
import uvicorn
import logging
from contextlib import asynccontextmanager

from modules.log_config import setup_logging
from modules.config_manager import ensure_config_exists, load_config
from modules.websocket_manager import connect_to_onebot, get_websocket_connections
from modules.ai_handler import init_ai
from modules.file_api_handler import init_file_api, api_get_file, api_put_file
from modules.minecraft_log_parser import parse_minecraft_logs
from modules.websocket_manager import send_message
from modules.memory_manager import refresh_user_memory, SHORT_TERM_DIR
import glob
import os

# 配置日志
setup_logging()
logger = logging.getLogger(__name__)

# 读取配置文件
config_path = os.path.join(os.path.dirname(__file__), 'config', 'config.json')
ensure_config_exists(config_path)
config = load_config(config_path)

# OneBot WebSocket连接配置
ONEBOT_WS_URL = config['onebot']['ws_url']
ONEBOT_TOKEN = config['onebot']['token']

# 初始化AI
init_ai(config.get('ai', {}))

# 初始化文件API
init_file_api(config.get('file_api', {}))


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("启动应用程序")
    task = asyncio.create_task(connect_to_onebot(ONEBOT_WS_URL, ONEBOT_TOKEN))
    # 启动日志解析任务
    log_task = asyncio.create_task(parse_minecraft_logs(config))
    # 启动记忆刷新任务
    memory_task = asyncio.create_task(memory_refresh_task())
    try:
        yield
    finally:
        logger.info("关闭应用程序")
        websocket_connections = get_websocket_connections()
        for connection in websocket_connections.values():
            if hasattr(connection, 'open') and connection.open:
                await connection.close()
        # 取消后台任务
        task.cancel()
        log_task.cancel()
        memory_task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        try:
            await log_task
        except asyncio.CancelledError:
            pass
        try:
            await memory_task
        except asyncio.CancelledError:
            pass
        try:
            await task
        except asyncio.CancelledError:
            pass
        try:
            await log_task
        except asyncio.CancelledError:
            pass

app = FastAPI(lifespan=lifespan)


@app.post("/api/send_message")
async def api_send_message(message: Dict[str, Any]):
    """
    API接口，用于发送消息到OneBot服务器
    
    Args:
        message: 要发送的消息数据
        
    Returns:
        发送结果
    """
    await send_message(message)
    return {"status": "success", "message": "消息已发送"}


@app.post("/api/send_private_msg")
async def api_send_private_msg(user_id: str, message: str):
    """
    API接口，用于发送私聊消息
    
    Args:
        user_id: 用户ID
        message: 要发送的文本消息
        
    Returns:
        发送结果
    """
    message_data = {
        "action": "send_private_msg",
        "params": {
            "user_id": user_id,
            "message": [
                {
                    "type": "text",
                    "data": {
                        "text": message
                    }
                }
            ]
        }
    }
    await send_message(message_data)
    return {"status": "success", "message": "私聊消息已发送"}


@app.post("/api/send_group_msg")
async def api_send_group_msg(group_id: str, message: str):
    """
    API接口，用于发送群聊消息
    
    Args:
        group_id: 群组ID
        message: 要发送的文本消息
        
    Returns:
        发送结果
    """
    message_data = {
        "action": "send_group_msg",
        "params": {
            "group_id": group_id,
            "message": [
                {
                    "type": "text",
                    "data": {
                        "text": message
                    }
                }
            ]
        }
    }
    await send_message(message_data)
    return {"status": "success", "message": "群聊消息已发送"}


@app.post("/api/send_private_message")
async def api_send_private_message(data: Dict[str, Any]):
    """
    API接口，用于发送私聊消息到OneBot服务器
    
    Args:
        data: 包含user_id和message字段的消息数据
              {
                "user_id": 123456,
                "message": "要发送的消息内容"
              }
        
    Returns:
        发送结果
    """
    message = {
        "action": "send_msg",
        "params": {
            "message_type": "private",
            "user_id": data.get("user_id"),
            "message": data.get("message", "")
        }
    }
    await send_message(message)
    return {"status": "success", "message": "私聊消息已发送"}


@app.post("/api/send_group_message")
async def api_send_group_message(data: Dict[str, Any]):
    """
    API接口，用于发送群聊消息到OneBot服务器
    
    Args:
        data: 包含group_id和message字段的消息数据
              {
                "group_id": 123456,
                "message": "要发送的消息内容"
              }
        
    Returns:
        发送结果
    """
    message = {
        "action": "send_msg",
        "params": {
            "message_type": "group",
            "group_id": data.get("group_id"),
            "message": data.get("message", "")
        }
    }
    await send_message(message)
    return {"status": "success", "message": "群聊消息已发送"}


@app.get("/api/status")
async def api_status():
    """
    API接口，用于获取WebSocket连接状态
    
    Returns:
        连接状态
    """
    websocket_connections = get_websocket_connections()
    connection = websocket_connections.get("onebot")
    status = "connected" if connection and hasattr(connection, 'open') and connection.open else "disconnected"
    logger.info(f"检查连接状态: {status}")
    return {"status": status}


@app.get("/api/files/")
async def api_get_file_endpoint(
    daemonId: str = Query(..., description="Daemon ID"),
    uuid: str = Query(..., description="Instance UUID"),
    target: str = Query(..., description="Target file path")
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
    return await api_get_file(daemonId, uuid, target)


@app.put("/api/files/")
async def api_put_file_endpoint(
    daemonId: str = Query(..., description="Daemon ID"),
    uuid: str = Query(..., description="Instance UUID"),
    target: str = Body(..., embed=True, description="Target file path")
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
    return await api_put_file(daemonId, uuid, target)


@app.get("/api/protected_instance/command")
async def api_execute_command(
    daemonId: str = Query(..., description="Daemon ID"),
    uuid: str = Query(..., description="Instance UUID"),
    command: str = Query(..., description="Command to execute")
):
    """
    GET /api/protected_instance/command 接口，用于执行远程实例命令
    
    Args:
        daemonId: Daemon ID (查询参数)
        uuid: Instance UUID (查询参数)
        command: 要执行的命令 (查询参数)
        
    Returns:
        远程API的响应结果
    """
    from modules.file_api_handler import execute_command
    return await execute_command(daemonId, uuid, command)


async def memory_refresh_task():
    """
    定期刷新记忆的任务
    """
    while True:
        try:
            # 每小时执行一次记忆刷新
            await asyncio.sleep(86400)  # 1天
            
            # 获取所有用户ID（通过短期记忆文件名）
            user_ids = set()
            if os.path.exists(SHORT_TERM_DIR):
                for filename in os.listdir(SHORT_TERM_DIR):
                    if filename.endswith('.json'):
                        user_id = filename.split('_')[0]
                        user_ids.add(user_id)
            
            # 为每个用户刷新记忆
            for user_id in user_ids:
                try:
                    refresh_user_memory(user_id)
                except Exception as e:
                    logger.error(f"刷新用户 {user_id} 的记忆时出错: {e}")
                    
        except Exception as e:
            logger.error(f"记忆刷新任务出错: {e}")


if __name__ == "__main__":
    uvicorn.run(app, host=config['server']['host'], port=config['server']['port'])