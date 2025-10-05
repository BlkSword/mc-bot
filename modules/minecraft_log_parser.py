import asyncio
import logging
import re
from datetime import datetime
from typing import Dict

logger = logging.getLogger(__name__)

# 存储已处理过的玩家事件，避免重复通知
# 修改为字典，键为事件标识符，值为事件处理的时间戳
processed_events = {}


async def parse_minecraft_logs(config: Dict):
    """
    定时解析Minecraft日志文件，检测玩家加入和离开事件
    
    Args:
        config: 配置信息
    """
    # 延迟导入以避免循环导入
    from modules.file_api_handler import get_http_client, FILE_DEFAULT_DAEMON_ID, FILE_DEFAULT_UUID
    from modules.websocket_manager import send_message
    
    http_client = await get_http_client()
    FILE_API_BASE_URL = config.get('file_api', {}).get('base_url', '')
    FILE_API_KEY = config.get('file_api', {}).get('api_key', '')
    
    # 等待应用启动完成
    await asyncio.sleep(5)
    
    last_position = 0
    server_started = False
    
    while True:
        try:
            logger.info("开始获取Minecraft日志文件...")
            # 调用API获取日志内容
            params = {
                "apikey": FILE_API_KEY,
                "daemonId": FILE_DEFAULT_DAEMON_ID,
                "uuid": FILE_DEFAULT_UUID
            }
            body = {
                "target": "/logs/latest.log"
            }
            logger.info(f"请求参数: URL={FILE_API_BASE_URL}, params={params}, body={body}")
            response = await http_client.put(FILE_API_BASE_URL, params=params, json=body)
            logger.info(f"日志API响应状态码: {response.status_code}")
            
            if response.status_code == 200:
                result = response.json()
                logger.info("日志API请求成功")
                # 检查响应格式并提取日志内容
                if isinstance(result, dict):
                    if result.get("status") == "success":
                        log_content = result.get("data", "")
                    elif "data" in result:
                        # 直接从响应中获取数据（适配不同的API响应格式）
                        log_content = result.get("data", "")
                    else:
                        # 如果响应是一个字典但没有预期的结构，记录详细信息
                        logger.warning("API响应格式不匹配预期结构")
                        log_content = ""
                elif isinstance(result, str):
                    # 如果响应是纯文本（日志内容）
                    log_content = result
                else:
                    log_content = ""
                
                if log_content:
                    # 解析日志内容
                    lines = log_content.split("\n")
                    logger.info(f"成功获取日志内容，共 {len(lines)} 行")
                    
                    # 检查服务器是否已启动完成
                    if not server_started:
                        logger.info("检查服务器是否已启动完成...")
                        for line in lines:
                            if 'Done (' in line and 'For help, type "help"' in line:
                                logger.info("检测到服务器启动完成")
                                server_started = True
                                # 记录当前日志位置，只处理之后的新事件
                                last_position = len(lines)
                                break
                    
                    # 如果服务器已启动，则开始处理玩家事件
                    if server_started:
                        logger.info(f"服务器已启动，开始处理日志事件，当前位置: {last_position}")
                        new_lines_count = 0
                        # 处理新的日志行
                        for i in range(last_position, len(lines)):
                            line = lines[i]
                            if line.strip():  # 只处理非空行
                                await process_log_line(line, config)
                                new_lines_count += 1
                        
                        # 更新位置
                        last_position = len(lines)
                        logger.info(f"日志处理完成，新增 {new_lines_count} 行日志")
                    else:
                        logger.info("服务器尚未启动完成，等待中...")
                else:
                    logger.warning("获取到的日志内容为空")
            else:
                logger.error(f"获取日志HTTP错误: {response.status_code}")
            
            # 等待1分钟再检查
            logger.info("等待60秒后再次检查日志...")
            await asyncio.sleep(60)
            
        except Exception as e:
            logger.error(f"解析Minecraft日志时出错: {e}", exc_info=True)
            await asyncio.sleep(60)


async def process_log_line(line: str, config: Dict):
    """
    处理单行日志，检测玩家加入或离开事件
    
    Args:
        line: 日志行
        config: 配置信息
    """
    from .websocket_manager import send_message
    
    logger.info(f"处理日志行: {line}")
    current_time = datetime.now()
    
    # 检测玩家加入游戏
    join_match = re.search(r'\[Server thread/INFO\] \[net\.minecraft\.server\.MinecraftServer/\]: (.+) joined the game', line)
    if join_match:
        player_name = join_match.group(1)
        event_key = f"join:{player_name}"
        logger.info(f"检测到玩家加入游戏事件: {player_name}")
        
        # 检查事件是否已处理且在短时间内（避免重复通知）
        should_process = True
        if event_key in processed_events:
            last_processed_time = processed_events[event_key]
            # 如果在5分钟内已经处理过相同事件，则跳过
            if (current_time - last_processed_time).total_seconds() < 300:
                should_process = False
                logger.info(f"事件 {event_key} 在5分钟内已处理过，跳过通知")
        
        if should_process:
            processed_events[event_key] = current_time
            # 清理过期的事件记录（超过1小时的记录）
            expired_keys = []
            for key, timestamp in processed_events.items():
                if (current_time - timestamp).total_seconds() > 3600:
                    expired_keys.append(key)
            for key in expired_keys:
                del processed_events[key]
            
            logger.info(f"玩家 {player_name} 加入游戏")
            # 发送欢迎消息到群聊（需要在配置中指定群号）
            group_id = config.get("server_group_id", "")  # 需要在配置中添加
            if group_id:
                message_data = {
                    "action": "send_group_msg",
                    "params": {
                        "group_id": group_id,
                        "message": f"欢迎 {player_name} 加入游戏！"
                    }
                }
                await send_message(message_data)
                logger.info(f"已发送欢迎消息到群聊 {group_id}")
    
    # 检测玩家离开游戏
    leave_match = re.search(r'\[Server thread/INFO\] \[net\.minecraft\.server\.MinecraftServer/\]: (.+) left the game', line)
    if leave_match:
        player_name = leave_match.group(1)
        event_key = f"leave:{player_name}"
        logger.info(f"检测到玩家离开游戏事件: {player_name}")
        
        # 检查事件是否已处理且在短时间内（避免重复通知）
        should_process = True
        if event_key in processed_events:
            last_processed_time = processed_events[event_key]
            # 如果在5分钟内已经处理过相同事件，则跳过
            if (current_time - last_processed_time).total_seconds() < 300:
                should_process = False
                logger.info(f"事件 {event_key} 在5分钟内已处理过，跳过通知")
        
        if should_process:
            processed_events[event_key] = current_time
            # 清理过期的事件记录（超过1小时的记录）
            expired_keys = []
            for key, timestamp in processed_events.items():
                if (current_time - timestamp).total_seconds() > 3600:
                    expired_keys.append(key)
            for key in expired_keys:
                del processed_events[key]
            
            logger.info(f"玩家 {player_name} 离开游戏")
            # 发送告别消息到群聊（需要在配置中指定群号）
            group_id = config.get("server_group_id", "")  # 需要在配置中添加
            if group_id:
                message_data = {
                    "action": "send_group_msg",
                    "params": {
                        "group_id": group_id,
                        "message": f"{player_name} 离开了游戏，再见！"
                    }
                }
                await send_message(message_data)
                logger.info(f"已发送告别消息到群聊 {group_id}")
    
    # 检测玩家断开连接 (Disconnected)
    disconnect_match = re.search(r'\[Server thread/INFO\] \[net\.minecraft\.server\.network\.ServerGamePacketListenerImpl/\]: (.+) lost connection: Disconnected', line)
    if disconnect_match:
        player_name = disconnect_match.group(1)
        event_key = f"disconnect:{player_name}"
        logger.info(f"检测到玩家断开连接事件: {player_name}")
        
        # 检查事件是否已处理且在短时间内（避免重复通知）
        should_process = True
        if event_key in processed_events:
            last_processed_time = processed_events[event_key]
            # 如果在5分钟内已经处理过相同事件，则跳过
            if (current_time - last_processed_time).total_seconds() < 300:
                should_process = False
                logger.info(f"事件 {event_key} 在5分钟内已处理过，跳过通知")
        
        if should_process:
            processed_events[event_key] = current_time
            # 清理过期的事件记录（超过1小时的记录）
            expired_keys = []
            for key, timestamp in processed_events.items():
                if (current_time - timestamp).total_seconds() > 3600:
                    expired_keys.append(key)
            for key in expired_keys:
                del processed_events[key]
            
            logger.info(f"玩家 {player_name} 断开连接")
            # 发送告别消息到群聊（需要在配置中指定群号）
            group_id = config.get("server_group_id", "")  # 需要在配置中添加
            if group_id:
                message_data = {
                    "action": "send_group_msg",
                    "params": {
                        "group_id": group_id,
                        "message": f"{player_name} 断开了连接，再见！"
                    }
                }
                await send_message(message_data)
                logger.info(f"已发送断开连接消息到群聊 {group_id}")