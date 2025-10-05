import asyncio
import json
import logging
import websockets
from typing import Dict, Any

logger = logging.getLogger(__name__)

# 存储WebSocket连接
websocket_connections: Dict[str, Any] = {}


async def connect_to_onebot(ws_url: str, token: str):
    """
    连接到OneBot WebSocket服务器
    
    Args:
        ws_url: WebSocket服务器地址
        token: 认证令牌
    """
    headers = {
        "Authorization": f"Bearer {token}"
    }
    
    while True:
        try:
            logger.info(f"正在连接到OneBot WebSocket服务器: {ws_url}")
            websocket = await websockets.connect(
                ws_url,
                additional_headers=headers
            )
            websocket_connections["onebot"] = websocket
            logger.info("成功连接到OneBot WebSocket服务器")
            
            # 开始接收消息
            await receive_messages(websocket)
            
        except websockets.exceptions.ConnectionClosed:
            logger.warning("与OneBot WebSocket服务器的连接已关闭，将在5秒后尝试重新连接...")
            await asyncio.sleep(5)
        except Exception as e:
            logger.error(f"连接OneBot WebSocket服务器时发生错误: {e}")
            logger.warning("将在5秒后尝试重新连接...")
            await asyncio.sleep(5)


async def receive_messages(websocket):
    """
    接收来自OneBot WebSocket服务器的消息
    
    Args:
        websocket: WebSocket连接对象
    """
    # 延迟导入以避免循环导入
    from modules.message_handler import handle_message
    
    async for message in websocket:
        try:
            # 解析接收到的消息
            data = json.loads(message)
            logger.info(f"收到消息: {data}")
            
            # 处理不同类型的消息
            await handle_message(data)
            
        except json.JSONDecodeError:
            logger.error(f"无法解析JSON消息: {message}")
        except Exception as e:
            logger.error(f"处理消息时发生错误: {e}")


async def send_message(message: Dict[str, Any]):
    """
    发送消息到OneBot WebSocket服务器
    
    Args:
        message: 要发送的消息数据
    """
    connection = websocket_connections.get("onebot")
    if connection:
        try:
            # 检查连接是否打开
            if hasattr(connection, 'open'):
                if not connection.open:
                    logger.warning("WebSocket连接已关闭，无法发送消息")
                    return
            # 如果没有open属性，则直接尝试发送并在异常中处理
            
            await connection.send(json.dumps(message, ensure_ascii=False))
            logger.info(f"发送消息: {message}")
        except Exception as e:
            logger.error(f"发送消息时发生错误: {e}")
    else:
        logger.warning("WebSocket连接不可用，无法发送消息")


def get_websocket_connections():
    """
    获取WebSocket连接字典
    """
    return websocket_connections