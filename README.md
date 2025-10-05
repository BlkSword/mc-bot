# Minecraft Bot

一个支持NapCat的MC机器人框架，专为 Minecraft 服务器设计，通过和主流启动器MCSM协同，使其能够完成各项任务。

## 功能特性

- **Minecraft 日志监控**: 实时监控 Minecraft 服务器日志，检测玩家加入/离开事件
- **OneBot 协议支持**: 通过 WebSocket 连接与 OneBot 协议兼容的平台通信
- **AI 助手集成**: 集成阿里云 DashScope 平台的 Qwen 系列模型，提供智能对话功能
- **记忆管理**: 具备短期和长期记忆功能，能够记住用户交互历史


## 项目结构

```
mc-bot/
├── main.py                 # 主程序入口
├── requirements.txt        # 项目依赖
├── config/                 # 配置文件目录
│   └── config.json         # 配置文件
├── modules/                # 功能模块
│   ├── ai_handler.py       # AI 处理模块
│   ├── config_manager.py   # 配置管理模块
│   ├── file_api_handler.py # 文件 API 处理模块
│   ├── log_config.py       # 日志配置模块
│   ├── memory_manager.py   # 记忆管理模块
│   ├── message_handler.py  # 消息处理模块
│   ├── minecraft_log_parser.py # Minecraft 日志解析模块
│   └── websocket_manager.py # WebSocket 管理模块
├── memory/                 # 记忆存储目录
│   ├── short_term/         # 短期记忆
│   └── long_term/          # 长期记忆
└── README.md               # 项目说明文件
```

## 环境要求

- Python 3.7+
- MCSM
- NapCat

**详细参考各自的文档

## 安装步骤

1. 克隆项目到本地：
```bash
git clone <repository-url>
cd mc-bot
```

2. 安装依赖：
```bash
pip install -r requirements.txt
```

3. 首次运行以生成配置文件：
```bash
python main.py
```

4. 修改 `config/config.json` 中的配置参数以匹配你的环境。

## 配置说明

首次运行程序会自动生成示例配置文件 `config/config.json`，包含以下主要配置项：

- `onebot.ws_url`: OneBot WebSocket 服务器地址
- `onebot.token`: OneBot 访问令牌
- `server.host`: 本地服务器监听地址
- `server.port`: 本地服务器监听端口
- `ai.api_key`: 阿里云 DashScope API 密钥（可选）
- `ai.model`: 使用的 AI 模型名称
- `ai.system_prompt`: AI 系统提示词
- `file_api.base_url`: 文件 API 基础地址
- `file_api.api_key`: 文件 API 访问密钥
- `file_api.default_daemon_id`: 默认守护进程 ID
- `file_api.default_uuid`: 默认实例 UUID

# 持续更新.....
