# uvicorn main:app --reload

import asyncio
import json
import os
import random
from typing import Dict, Any
import websockets
from fastapi import FastAPI
import uvicorn
import logging
from logging.handlers import RotatingFileHandler
from contextlib import asynccontextmanager

try:
    from openai import OpenAI
    AI_AVAILABLE = True
except ImportError:
    AI_AVAILABLE = False
    logging.warning("openai库未安装，AI功能不可用")

# 配置日志
log_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
log_file = os.path.join(os.path.dirname(__file__), 'bot.log')
log_handler = RotatingFileHandler(log_file, maxBytes=100*1024*1024, backupCount=5)  # 最大1MB，保留5个备份
log_handler.setFormatter(log_formatter)

# 添加控制台处理器
console_handler = logging.StreamHandler()
console_handler.setFormatter(log_formatter)

logger = logging.getLogger()
logger.setLevel(logging.INFO)
logger.addHandler(log_handler)
logger.addHandler(console_handler)

app = FastAPI()

# 存储WebSocket连接
websocket_connections: Dict[str, Any] = {}

def ensure_config_exists(config_path: str):
    """
    确保配置文件存在，如果不存在则创建示例配置文件
    """
    if not os.path.exists(config_path):
        # 确保config目录存在
        config_dir = os.path.dirname(config_path)
        if not os.path.exists(config_dir):
            os.makedirs(config_dir)
        
        # 创建示例配置
        sample_config = {
            "onebot": {
                "ws_url": "ws://127.0.0.1:3011/",
                "token": "your-token-here"
            },
            "server": {
                "host": "0.0.0.0",
                "port": 8000
            },
            "ai": {
                "api_key": "",
                "model": "qwen3-max",
                "system_prompt": "你是一个有用的助手"
            }
        }
        
        # 写入示例配置
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(sample_config, f, ensure_ascii=False, indent=4)
        
        logger.info(f"已创建示例配置文件: {config_path}")
        logger.info("请修改配置文件中的参数以匹配您的实际环境")

# 读取配置文件
config_path = os.path.join(os.path.dirname(__file__), 'config', 'config.json')
ensure_config_exists(config_path)

with open(config_path, 'r', encoding='utf-8') as f:
    config = json.load(f)

# OneBot WebSocket连接配置
ONEBOT_WS_URL = config['onebot']['ws_url']
ONEBOT_TOKEN = config['onebot']['token']

# AI配置
AI_CONFIG = config.get('ai', {})
AI_ENABLED = bool(AI_CONFIG.get('api_key')) and AI_AVAILABLE

# 初始化AI客户端
if AI_ENABLED:
    ai_client = OpenAI(
        api_key=AI_CONFIG['api_key'],
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1"
    )
else:
    ai_client = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("启动应用程序")
    task = asyncio.create_task(connect_to_onebot())
    try:
        yield
    finally:
        logger.info("关闭应用程序")
        for connection in websocket_connections.values():
            if hasattr(connection, 'open') and connection.open:
                await connection.close()
        # 取消后台任务
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

app = FastAPI(lifespan=lifespan)

# 连接服务器
async def connect_to_onebot():
    headers = {
        "Authorization": f"Bearer {ONEBOT_TOKEN}"
    }
    
    while True:
        try:
            logger.info(f"正在连接到OneBot WebSocket服务器: {ONEBOT_WS_URL}")
            websocket = await websockets.connect(
                ONEBOT_WS_URL,
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
    """
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

async def handle_message(data: Dict[str, Any]):
    """
    处理从OneBot服务器接收到的消息
    
    Args:
        data: 接收到的消息数据
    """
    # 检查消息类型
    message_type = data.get("post_type", "")
    
    if message_type == "message":
        # 处理消息事件
        await handle_message_event(data)
    elif message_type == "notice":
        # 处理通知事件
        await handle_notice_event(data)
    elif message_type == "request":
        # 处理请求事件
        await handle_request_event(data)
    elif message_type == "meta_event":
        # 处理元事件
        await handle_meta_event(data)
    else:
        # 处理其他类型事件
        logger.warning(f"收到未识别类型的消息: {data}")

async def handle_message_event(data: Dict[str, Any]):
    """
    处理消息事件
    
    Args:
        data: 消息事件数据
    """
    logger.info(f"处理消息事件: {data.get('message_type', 'unknown')}")
    
    # 获取消息内容
    message_type = data.get("message_type")
    raw_message = data.get("raw_message", "")
    user_id = data.get("user_id")
    self_id = data.get("self_id")
    
    # 判断是否需要AI回复
    if should_ai_reply(message_type, raw_message, self_id):
        # 获取AI回复
        ai_response = await get_ai_response(raw_message)
        if ai_response:
            # 构造回复消息
            reply_message = {
                "action": "send_msg",
                "params": {
                    "message_type": message_type,
                    "user_id": user_id if message_type == "private" else None,
                    "group_id": data.get("group_id") if message_type == "group" else None,
                    "message": ai_response
                }
            }
            # 发送回复
            await send_message(reply_message)

def should_ai_reply(message_type: str, message: str, self_id: str = None) -> bool:
    """
    判断是否应该使用AI回复消息
    
    Args:
        message_type: 消息类型(private/group)
        message: 消息内容
        self_id: 机器人自身ID，用于检测群聊中的@消息
        
    Returns:
        bool: 是否应该回复
    """
    if not AI_ENABLED:
        return False
    
    # 私聊全部回复
    if message_type == "private":
        return True
    
    # 群聊中只有在@机器人时才回复
    if message_type == "group" and self_id:
        # 检查是否包含@机器人的标记
        # OneBot协议中@消息格式为[CQ:at,qq=机器人QQ号]
        return f"[CQ:at,qq={self_id}]" in message
    
    return False

async def get_ai_response(message: str) -> str:
    """
    获取AI回复
    
    Args:
        message: 用户消息
        
    Returns:
        str: AI回复内容
    """
    if not ai_client:
        return ""
        
    try:
        system_prompt = AI_CONFIG.get("system_prompt", "")
        model = AI_CONFIG.get("model", "")
        
        completion = ai_client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": message},
                {"role": "assistant", "content": ""}
            ],
            stream=False
        )
        return completion.choices[0].message.content
    except Exception as e:
        logger.error(f"获取AI回复时发生错误: {e}")
        return ""

async def handle_notice_event(data: Dict[str, Any]):
    """
    处理通知事件
    
    Args:
        data: 通知事件数据
    """
    logger.info(f"处理通知事件: {data.get('notice_type', 'unknown')}")

async def handle_request_event(data: Dict[str, Any]):
    """
    处理请求事件
    
    Args:
        data: 请求事件数据
    """
    logger.info(f"处理请求事件: {data.get('request_type', 'unknown')}")

async def handle_meta_event(data: Dict[str, Any]):
    """
    处理元事件
    
    Args:
        data: 元事件数据
    """
    logger.info(f"处理元事件: {data.get('meta_event_type', 'unknown')}")

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
    connection = websocket_connections.get("onebot")
    status = "connected" if connection and not connection.closed else "disconnected"
    logger.info(f"检查连接状态: {status}")
    return {"status": status}

if __name__ == "__main__":
    uvicorn.run(app, host=config['server']['host'], port=config['server']['port'])