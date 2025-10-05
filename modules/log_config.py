import os
import logging
from logging.handlers import RotatingFileHandler


def setup_logging():
    """
    配置日志系统
    """
    # 获取根日志记录器
    logger = logging.getLogger()
    
    # 检查是否已经配置过处理器，避免重复添加
    if logger.handlers:
        # 如果已经有处理器，先清除它们
        logger.handlers.clear()
    
    # 配置日志
    log_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    log_file = os.path.join(os.path.dirname(__file__), '..', 'bot.log')
    log_handler = RotatingFileHandler(log_file, maxBytes=100*1024*1024, backupCount=5)  # 最大1MB，保留5个备份
    log_handler.setFormatter(log_formatter)

    # 添加控制台处理器
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(log_formatter)

    logger.setLevel(logging.INFO)
    logger.addHandler(log_handler)
    logger.addHandler(console_handler)