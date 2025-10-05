import logging
try:
    from openai import OpenAI
    AI_AVAILABLE = True
except ImportError:
    AI_AVAILABLE = False
    logging.warning("openai库未安装，AI功能不可用")

# 导入记忆管理模块
from modules.memory_manager import add_user_memory, format_memories_for_ai

logger = logging.getLogger(__name__)

# 全局变量用于存储AI配置和客户端
ai_client = None
AI_CONFIG = {}
AI_ENABLED = False

# 存储用户消息上下文
user_contexts = {}


def init_ai(config):
    """
    初始化AI客户端
    
    Args:
        config: AI配置
    """
    global ai_client, AI_CONFIG, AI_ENABLED
    
    AI_CONFIG = config
    AI_ENABLED = bool(AI_CONFIG.get('api_key')) and AI_AVAILABLE

    # 初始化AI客户端
    if AI_ENABLED:
        ai_client = OpenAI(
            api_key=AI_CONFIG['api_key'],
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1"
        )
    else:
        ai_client = None


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
        return f"[CQ:at,qq={self_id}]" in message
    
    return False


def get_teleport_tool():
    """
    获取传送工具定义
    
    Returns:
        dict: 传送工具定义
    """
    return {
        "type": "function",
        "function": {
            "name": "teleport_player",
            "description": "当有人说'把xxx传送到xxx'时调用此工具，用于传送玩家到指定位置或其他玩家身边",
            "parameters": {
                "type": "object",
                "properties": {
                    "player_from": {
                        "type": "string",
                        "description": "需要被传送的玩家名称"
                    },
                    "player_to": {
                        "type": "string",
                        "description": "目标玩家名称或位置坐标"
                    }
                },
                "required": ["player_from", "player_to"]
            }
        }
    }


async def get_ai_response(message: str, config=None, execute_command_func=None, user_id: str = None) -> str:
    """
    获取AI回复
    
    Args:
        message: 用户消息
        config: 主配置对象，用于获取file_api配置
        execute_command_func: 执行命令的函数
        user_id: 用户ID，用于记忆功能
        
    Returns:
        str: AI回复内容
    """
    if not ai_client:
        return ""
        
    try:
        system_prompt = AI_CONFIG.get("system_prompt", "")
        model = AI_CONFIG.get("model", "")
        
        # 检查是否是传送命令
        tools = []
        tool_choice = "auto"
        
        # 如果消息包含传送关键词，则提供传送工具
        if "传送" in message and ("把" in message or "将" in message):
            tools = [get_teleport_tool()]
            tool_choice = {"type": "function", "function": {"name": "teleport_player"}}
        
        # 准备参数
        messages = [
            {"role": "system", "content": system_prompt}
        ]
        
        # 添加记忆上下文
        if user_id:
            memory_context = format_memories_for_ai(user_id)
            if memory_context:
                messages.append({"role": "system", "content": f"记忆上下文:\n{memory_context}"})
        
        # 添加当前用户消息
        messages.append({"role": "user", "content": message})
        
        params = {
            "model": model,
            "messages": messages,
            "extra_body": {"enable_search": True},
            "stream": False
        }
        
        # 检查是否是传送命令
        tools = []
        
        # 如果消息包含传送关键词，则提供传送工具
        if "传送" in message and ("把" in message or "将" in message):
            tools = [get_teleport_tool()]
            params["tool_choice"] = {"type": "function", "function": {"name": "teleport_player"}}
        
        # 只有在有工具时才添加tools参数
        if tools:
            params["tools"] = tools
        
        completion = ai_client.chat.completions.create(**params)
        
        # 获取AI回复
        ai_response = completion.choices[0].message.content
        
        # 保存到记忆中
        if user_id and ai_response:
            add_user_memory(user_id, message, ai_response)
        
        # 检查是否有工具调用
        choice = completion.choices[0]
        if choice.message.tool_calls:
            # 处理工具调用
            for tool_call in choice.message.tool_calls:
                if tool_call.function.name == "teleport_player":
                    # 解析参数
                    import json
                    try:
                        args = json.loads(tool_call.function.arguments)
                        player_from = args.get("player_from")
                        player_to = args.get("player_to")

                        if not player_from or not player_to:
                            return "传送指令参数不完整，请指定正确的玩家和目标。"

                        # 执行传送命令
                        if execute_command_func and config:
                            file_api_config = config.get('file_api', {})
                            daemon_id = file_api_config.get('default_daemon_id', '')
                            uuid = file_api_config.get('default_uuid', '')

                            command = f"tp {player_from} {player_to}"
                            result = await execute_command_func(daemon_id, uuid, command)

                            if result.get("status") == "success":
                                return f"已将玩家 {player_from} 传送到 {player_to}"
                            else:
                                return f"传送失败: {result.get('message', '未知错误')}"
                    except json.JSONDecodeError:
                        return "无法解析传送指令参数。"
        
        return ai_response
    except Exception as e:
        logger.error(f"获取AI回复时发生错误: {e}")
        return ""