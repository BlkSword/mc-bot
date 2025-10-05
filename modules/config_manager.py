import os
import json
import logging

logger = logging.getLogger(__name__)


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
            },
            "file_api": {
                "base_url": "http://x.x.x.x/api/files",
                "api_key": "your-api-key-here",
                "default_daemon_id": "default-daemon-id",
                "default_uuid": "default-instance-uuid"
            }
        }
        
        # 写入示例配置
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(sample_config, f, ensure_ascii=False, indent=4)
        
        logger.info(f"已创建示例配置文件: {config_path}")
        logger.info("请修改配置文件中的参数以匹配您的实际环境")


def load_config(config_path: str):
    """
    加载配置文件
    
    Args:
        config_path: 配置文件路径
        
    Returns:
        dict: 配置信息
    """
    with open(config_path, 'r', encoding='utf-8') as f:
        return json.load(f)