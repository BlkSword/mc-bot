import asyncio
import logging
import re
from datetime import datetime
from typing import Dict
from modules.persistent_events_storage import get_processed_events, add_processed_event, cleanup_expired_events

logger = logging.getLogger(__name__)


async def parse_minecraft_logs(config: Dict):
    """
    定时解析Minecraft日志文件，检测玩家加入和离开事件
    
    Args:
        config: 配置信息
    """
    # 延迟导入以避免循环导入
    from modules.file_api_handler import get_http_client, FILE_DEFAULT_DAEMON_ID, FILE_DEFAULT_UUID
    from modules.websocket_manager import send_message
    
    # 获取已处理的事件列表
    global processed_events
    processed_events = get_processed_events()
    
    http_client = await get_http_client()
    FILE_API_BASE_URL = config.get('file_api', {}).get('base_url', '')
    FILE_API_KEY = config.get('file_api', {}).get('api_key', '')
    
    # 等待应用启动完成
    await asyncio.sleep(5)
    
    last_position = -1
    server_started = False
    
    while True:
        try:
            # 更新已处理事件列表
            processed_events = get_processed_events()
            
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
                    
                    if last_position == -1:
                        last_position = len(lines)
                        logger.info(f"初始化日志位置: {last_position}，将只处理之后的日志")
                        continue  # 跳过本次循环，下次再处理新日志
                    
                    # 检查服务器是否已启动完成
                    if not server_started:
                        logger.info("检查服务器是否已启动完成...")
                        for line in lines:
                            # 修复服务器启动检测逻辑，支持更多日志格式
                            if 'Done (' in line and ('For help, type "help"' in line or "For help, type 'help'" in line):
                                logger.info("检测到服务器启动完成")
                                server_started = True
                                # 记录当前日志位置，只处理之后的新事件
                                last_position = len(lines)
                                break
                            # 添加额外的服务器启动检测方式
                            if re.search(r'\[Server thread/INFO\].*Done .* Took .*,* seconds', line):
                                logger.info("检测到服务器启动完成（备用方式）")
                                server_started = True
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
                        new_lines_count = 0
                        for i in range(last_position, len(lines)):
                            line = lines[i]
                            if line.strip():  # 只处理非空行
                                await process_log_line(line, config)
                                new_lines_count += 1
                        last_position = len(lines)
                        logger.info(f"处理了 {new_lines_count} 行日志")
                else:
                    logger.warning("获取到的日志内容为空")
            else:
                logger.error(f"获取日志HTTP错误: {response.status_code}")
            
            # 等待10秒再检查
            logger.info("等待10秒后再次检查日志...")
            await asyncio.sleep(10)
            
        except Exception as e:
            logger.error(f"解析Minecraft日志时出错: {e}", exc_info=True)
            await asyncio.sleep(10)


async def process_log_line(line: str, config: Dict):
    """
    处理单行日志，检测玩家加入或离开事件
    
    Args:
        line: 日志行
        config: 配置信息
    """
    from .websocket_manager import send_message
    
    logger.debug(f"处理日志行: {line}")
    current_time = datetime.now()
    
    # 检测玩家加入游戏
    # 支持多种日志格式
    join_patterns = [
        r'\[Server thread/INFO\] \[net\.minecraft\.server\.MinecraftServer/\]: (.+) joined the game',
        r'\[Server thread/INFO\] \[minecraft/MinecraftServer\]: (.+) joined the game',
        r'\[Server thread/INFO\]: (.+) joined the game',
        r'(.+) joined the game'
    ]
    
    player_name = None
    event_type = None
    
    for pattern in join_patterns:
        join_match = re.search(pattern, line)
        if join_match:
            player_name = join_match.group(1).strip()  # 添加.strip()去除可能的空白字符
            event_type = "join"
            logger.info(f"检测到玩家加入游戏事件: {player_name} (使用模式: {pattern})")
            break
    
    if not player_name:
        # 检测玩家登录事件（在加入游戏之前）
        login_patterns = [
            r'\[Server thread/INFO\] \[minecraft/PlayerList\]: (.+)\[/.+\] logged in with entity id .+'
        ]
        
        for pattern in login_patterns:
            login_match = re.search(pattern, line)
            if login_match:
                player_name = login_match.group(1).strip()  # 添加.strip()去除可能的空白字符
                event_type = "login"
                logger.info(f"检测到玩家登录事件: {player_name} (使用模式: {pattern})")
                break
    
    if not player_name:
        # 检测玩家离开游戏
        leave_patterns = [
            r'\[Server thread/INFO\] \[net\.minecraft\.server\.MinecraftServer/\]: (.+) left the game',
            r'\[Server thread/INFO\] \[minecraft/MinecraftServer\]: (.+) left the game',
            r'\[Server thread/INFO\]: (.+) left the game',
            r'(.+) left the game'
        ]
        
        for pattern in leave_patterns:
            leave_match = re.search(pattern, line)
            if leave_match:
                player_name = leave_match.group(1).strip()  # 添加.strip()去除可能的空白字符
                event_type = "leave"
                logger.info(f"检测到玩家离开游戏事件: {player_name} (使用模式: {pattern})")
                break
    
    if not player_name:
        # 检测玩家断开连接
        disconnect_patterns = [
            r'\[Server thread/INFO\] \[net\.minecraft\.server\.network\.ServerGamePacketListenerImpl/\]: (.+) lost connection: Disconnected',
            r'\[Server thread/INFO\] \[minecraft\.server\.network\.ServerGamePacketListenerImpl/\]: (.+) lost connection: Disconnected',
            r'\[Server thread/INFO\]: (.+) lost connection: Disconnected',
            r'(.+) lost connection: Disconnected',
            r'\[Server thread/INFO\] \[minecraft/ServerLoginPacketListenerImpl\]: com\.mojang\.authlib\.GameProfile@.+?\[id=.+?,name=(.+?),properties=.+?\] \(.+\) lost connection: Disconnected'
        ]
        
        for pattern in disconnect_patterns:
            disconnect_match = re.search(pattern, line)
            if disconnect_match:
                player_name = disconnect_match.group(1).strip()  # 添加.strip()去除可能的空白字符
                event_type = "disconnect"
                logger.info(f"检测到玩家断开连接事件: {player_name} (使用模式: {pattern})")
                break
    
    # 如果检测到玩家事件
    if player_name and event_type:
        # 使用更精确的事件键，包含事件类型和日志行内容
        event_key = f"{event_type}:{player_name}"
        
        # 检查事件是否已处理且在短时间内（避免重复通知）
        should_process = True
        global processed_events
        if event_key in processed_events:
            last_processed_time = processed_events[event_key]
            # 如果在5分钟内已经处理过相同事件，则跳过
            if (current_time - last_processed_time).total_seconds() < 300:
                should_process = False
                logger.info(f"事件 {event_key} 在5分钟内已处理过，跳过通知")
        
        if should_process:
            # 添加事件到持久化存储
            add_processed_event(event_key, current_time)
            # 重新获取处理过的事件列表（可能已更新）
            processed_events = get_processed_events()
            
            # 清理过期的事件记录（超过1小时的记录）
            cleanup_expired_events()
            
            # 发送消息到群聊（需要在配置中指定群号）
            group_id = config.get("server_group_id", "")  # 需要在配置中添加
            if group_id:
                message = ""
                if event_type == "join":
                    message = f"欢迎 {player_name} 加入游戏！"
                elif event_type == "login":
                    message = f"玩家 {player_name} 正在登录游戏..."
                elif event_type == "leave":
                    message = f"{player_name} 离开了游戏，再见！"
                elif event_type == "disconnect":
                    message = f"{player_name} 断开了连接，再见！"
                
                if message:
                    try:
                        message_data = {
                            "action": "send_group_msg",
                            "params": {
                                "group_id": group_id,
                                "message": message
                            }
                        }
                        await send_message(message_data)
                        logger.info(f"已发送{event_type}消息到群聊 {group_id}: {message}")
                    except Exception as e:
                        logger.error(f"发送消息到群聊时出错: {e}", exc_info=True)
            else:
                logger.warning(f"检测到玩家{event_type}事件但未配置server_group_id，无法发送通知")
        else:
            logger.info(f"跳过处理事件: {event_type}:{player_name}")
    else:
        logger.debug(f"未匹配到任何玩家事件: {line}")