import os
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any
import asyncio
from pathlib import Path

logger = logging.getLogger(__name__)

# 记忆存储目录
MEMORY_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "memory")
SHORT_TERM_DIR = os.path.join(MEMORY_DIR, "short_term")
LONG_TERM_DIR = os.path.join(MEMORY_DIR, "long_term")

# 确保目录存在
os.makedirs(SHORT_TERM_DIR, exist_ok=True)
os.makedirs(LONG_TERM_DIR, exist_ok=True)

# 内存中的记忆缓存
memory_cache: Dict[str, Dict[str, Any]] = {}


class MemoryManager:
    """管理AI的记忆，包括短期记忆和长期记忆"""
    
    def __init__(self):
        self.last_refresh_date = datetime.now().date()
        self._check_and_refresh_short_term_memory()
    
    def _check_and_refresh_short_term_memory(self):
        """检查是否需要刷新短期记忆（每天刷新一次）"""
        current_date = datetime.now().date()
        if self.last_refresh_date != current_date:
            self._refresh_short_term_memory()
            self.last_refresh_date = current_date
    
    def _refresh_short_term_memory(self):
        """刷新短期记忆"""
        logger.info("开始刷新短期记忆")
        try:
            current_date = datetime.now().strftime("%Y-%m-%d")
            short_term_files = os.listdir(SHORT_TERM_DIR)
            
            logger.info("短期记忆刷新完成")
        except Exception as e:
            logger.error(f"刷新短期记忆时出错: {e}")
    
    def _get_user_short_term_file(self, user_id: str) -> str:
        """获取用户的短期记忆文件路径"""
        current_date = datetime.now().strftime("%Y-%m-%d")
        return os.path.join(SHORT_TERM_DIR, f"{user_id}_{current_date}.json")
    
    def _get_long_term_file(self, user_id: str) -> str:
        """获取用户的长期记忆文件路径"""
        return os.path.join(LONG_TERM_DIR, f"{user_id}_long_term.json")
    
    def add_short_term_memory(self, user_id: str, message: str, response: str = None):
        """添加短期记忆"""
        self._check_and_refresh_short_term_memory()
        
        try:
            file_path = self._get_user_short_term_file(user_id)
            
            # 读取现有记忆
            memory_data = []
            if os.path.exists(file_path):
                with open(file_path, 'r', encoding='utf-8') as f:
                    memory_data = json.load(f)
            
            # 添加新记忆
            timestamp = datetime.now().isoformat()
            memory_entry = {
                "timestamp": timestamp,
                "message": message,
                "response": response
            }
            memory_data.append(memory_entry)
            
            # 保存记忆
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(memory_data, f, ensure_ascii=False, indent=2)
                
            logger.debug(f"为用户 {user_id} 添加短期记忆")
        except Exception as e:
            logger.error(f"添加短期记忆时出错: {e}")
    
    def get_short_term_memory(self, user_id: str, hours: int = 24) -> List[Dict[str, str]]:
        """获取用户的短期记忆"""
        self._check_and_refresh_short_term_memory()
        
        try:
            file_path = self._get_user_short_term_file(user_id)
            
            if not os.path.exists(file_path):
                return []
            
            with open(file_path, 'r', encoding='utf-8') as f:
                memory_data = json.load(f)
            
            # 过滤时间范围内的记忆
            cutoff_time = datetime.now() - timedelta(hours=hours)
            filtered_memories = []
            
            for entry in memory_data:
                try:
                    entry_time = datetime.fromisoformat(entry["timestamp"])
                    if entry_time >= cutoff_time:
                        filtered_memories.append(entry)
                except ValueError:
                    # 时间格式错误，跳过该条目
                    continue
            
            return filtered_memories
        except Exception as e:
            logger.error(f"获取短期记忆时出错: {e}")
            return []
    
    def summarize_and_save_long_term_memory(self, user_id: str):
        """总结并保存长期记忆"""
        try:
            # 获取今天的短期记忆
            today_memories = self.get_short_term_memory(user_id, hours=24)
            
            if not today_memories:
                return
            
            # 构造用于总结的提示
            memory_text = "\n".join([
                f"用户消息: {entry['message']}\nAI回复: {entry.get('response', '')}"
                for entry in today_memories
            ])
            
            # 这里应该调用AI进行总结，暂时存储原始内容
            long_term_file = self._get_long_term_file(user_id)
            
            # 读取现有长期记忆
            long_term_data = {"memories": []}
            if os.path.exists(long_term_file):
                with open(long_term_file, 'r', encoding='utf-8') as f:
                    long_term_data = json.load(f)
            
            # 添加新的总结（此处简化处理，实际应由AI总结）
            summary_entry = {
                "date": datetime.now().strftime("%Y-%m-%d"),
                "summary": f"当天共有{len(today_memories)}条交互记录",
                "details": memory_text
            }
            
            # 保留最近30天的长期记忆
            long_term_data["memories"].append(summary_entry)
            long_term_data["memories"] = long_term_data["memories"][-30:]
            
            # 保存长期记忆
            with open(long_term_file, 'w', encoding='utf-8') as f:
                json.dump(long_term_data, f, ensure_ascii=False, indent=2)
                
            logger.info(f"为用户 {user_id} 保存长期记忆")
        except Exception as e:
            logger.error(f"保存长期记忆时出错: {e}")
    
    def get_long_term_memory(self, user_id: str, days: int = 7) -> List[Dict[str, str]]:
        """获取用户的长期记忆"""
        try:
            long_term_file = self._get_long_term_file(user_id)
            
            if not os.path.exists(long_term_file):
                return []
            
            with open(long_term_file, 'r', encoding='utf-8') as f:
                long_term_data = json.load(f)
            
            # 返回最近几天的记忆
            memories = long_term_data.get("memories", [])
            if days < len(memories):
                return memories[-days:]
            return memories
            
        except Exception as e:
            logger.error(f"获取长期记忆时出错: {e}")
            return []


# 全局内存管理器实例
memory_manager = MemoryManager()


def add_user_memory(user_id: str, message: str, response: str = None):
    """添加用户记忆"""
    memory_manager.add_short_term_memory(user_id, message, response)


def get_user_memories(user_id: str) -> Dict[str, List[Dict[str, str]]]:
    """获取用户的所有相关记忆"""
    short_term = memory_manager.get_short_term_memory(user_id, hours=24)
    long_term = memory_manager.get_long_term_memory(user_id, days=7)
    
    return {
        "short_term": short_term,
        "long_term": long_term
    }


def format_memories_for_ai(user_id: str) -> str:
    """格式化记忆供AI使用"""
    memories = get_user_memories(user_id)
    
    memory_context = []
    
    # 添加短期记忆上下文
    if memories["short_term"]:
        memory_context.append("以下是今天与用户的对话历史:")
        for memory in memories["short_term"]:
            memory_context.append(f"用户: {memory['message']}")
            if memory.get('response'):
                memory_context.append(f"AI: {memory['response']}")
    
    # 添加长期记忆上下文
    if memories["long_term"]:
        memory_context.append("\n以下是最近几天的对话总结:")
        for memory in memories["long_term"]:
            memory_context.append(f"{memory['date']}: {memory['summary']}")
    
    return "\n".join(memory_context) if memory_context else ""


def refresh_user_memory(user_id: str):
    """刷新用户记忆，将短期记忆总结为长期记忆"""
    memory_manager.summarize_and_save_long_term_memory(user_id)