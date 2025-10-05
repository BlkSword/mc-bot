import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)


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
    # 延迟导入以避免循环导入
    from modules.ai_handler import should_ai_reply, get_ai_response
    from modules.websocket_manager import send_message
    from modules.file_api_handler import execute_command
    import main
    
    logger.info(f"处理消息事件: {data.get('message_type', 'unknown')}")
    
    # 获取消息内容
    message_type = data.get("message_type")
    raw_message = data.get("raw_message", "")
    user_id = data.get("user_id")
    self_id = data.get("self_id")
    
    # 判断是否需要AI回复
    if should_ai_reply(message_type, raw_message, self_id):
        # 获取AI回复，传递用户ID以启用记忆功能
        ai_response = await get_ai_response(
            message=raw_message, 
            config=main.config, 
            execute_command_func=execute_command,
            user_id=str(user_id)  # 传递用户ID
        )
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