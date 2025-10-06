import os
import json
import logging
from datetime import datetime, timedelta
from typing import Dict
from threading import Lock

logger = logging.getLogger(__name__)

# 事件存储文件路径
EVENTS_STORAGE_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "events_storage.json")

# 内存中的事件缓存
processed_events: Dict[str, datetime] = {}

# 添加线程锁确保线程安全
_lock = Lock()

# 初始化时确保文件存在
try:
    if not os.path.exists(EVENTS_STORAGE_FILE):
        with open(EVENTS_STORAGE_FILE, 'w', encoding='utf-8') as f:
            json.dump({}, f, ensure_ascii=False, indent=2)
        logger.info("已创建事件存储文件")
except Exception as e:
    logger.error(f"创建事件存储文件时出错: {e}")


def _load_events_from_file() -> Dict[str, datetime]:
    """
    从文件加载已处理的事件
    
    Returns:
        包含事件标识符和时间戳的字典
    """
    try:
        if os.path.exists(EVENTS_STORAGE_FILE):
            with open(EVENTS_STORAGE_FILE, 'r', encoding='utf-8') as f:
                events_data = json.load(f)
            
            # 将字符串时间转换为datetime对象
            events = {}
            for event_key, timestamp_str in events_data.items():
                try:
                    events[event_key] = datetime.fromisoformat(timestamp_str)
                except ValueError:
                    logger.warning(f"无法解析事件时间戳: {timestamp_str}")
            
            logger.info(f"从文件加载了 {len(events)} 个已处理事件")
            return events
        else:
            logger.info("事件存储文件不存在，将创建新文件")
            return {}
    except Exception as e:
        logger.error(f"加载事件存储文件时出错: {e}")
        return {}


def _save_events_to_file(events: Dict[str, datetime]):
    """
    将事件保存到文件
    
    Args:
        events: 包含事件标识符和时间戳的字典
    """
    try:
        # 将datetime对象转换为字符串
        events_data = {}
        for event_key, timestamp in events.items():
            events_data[event_key] = timestamp.isoformat()
        
        with open(EVENTS_STORAGE_FILE, 'w', encoding='utf-8') as f:
            json.dump(events_data, f, ensure_ascii=False, indent=2)
        
        logger.debug(f"保存了 {len(events)} 个事件到存储文件")
    except Exception as e:
        logger.error(f"保存事件存储文件时出错: {e}")


def get_processed_events() -> Dict[str, datetime]:
    """
    获取已处理事件的全局缓存，如果缓存为空则从文件加载
    
    Returns:
        包含事件标识符和时间戳的字典
    """
    global processed_events
    
    with _lock:
        if not processed_events:
            processed_events = _load_events_from_file()
        return processed_events.copy()


def add_processed_event(event_key: str, timestamp: datetime):
    """
    添加已处理事件到缓存和文件
    
    Args:
        event_key: 事件标识符（格式：事件类型:玩家名）
        timestamp: 事件处理时间戳
    """
    global processed_events
    
    with _lock:
        # 如果缓存为空，先加载现有数据
        if not processed_events:
            processed_events = _load_events_from_file()
        
        # 添加新事件
        processed_events[event_key] = timestamp
        
        # 清理过期事件（超过1小时的事件）
        current_time = datetime.now()
        expired_keys = [
            key for key, event_time in processed_events.items()
            if (current_time - event_time).total_seconds() > 3600
        ]
        
        for key in expired_keys:
            del processed_events[key]
        
        # 保存到文件
        _save_events_to_file(processed_events)


def cleanup_expired_events():
    """
    清理过期事件并保存到文件
    """
    global processed_events
    
    with _lock:
        # 如果缓存为空，先加载现有数据
        if not processed_events:
            processed_events = _load_events_from_file()
        
        # 清理过期事件（超过1小时的事件）
        current_time = datetime.now()
        expired_keys = [
            key for key, event_time in processed_events.items()
            if (current_time - event_time).total_seconds() > 3600
        ]
        
        for key in expired_keys:
            del processed_events[key]
        
        if expired_keys:
            logger.info(f"清理了 {len(expired_keys)} 个过期事件")
        
        # 保存到文件
        _save_events_to_file(processed_events)