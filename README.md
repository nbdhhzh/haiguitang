# 海龟汤 AI (Turtle Soup AI)

这是一个基于 AI 的海龟汤（情境推理游戏）网页应用。玩家通过向 AI 主持人提问“是/否”问题，逐步还原故事真相。

## ✨ 功能特点

*   **AI 主持人**：利用大语言模型（如 Gemini via OpenRouter）扮演主持人，智能回答玩家提问。
*   **游戏规则**：严格遵守海龟汤规则，仅回答“是”、“不是”、“没有关系”或“不重要”。
*   **智能判定**：AI 自动判断玩家是否已经推导出核心真相（汤底），并判定游戏胜利。
*   **提示与放弃**：
    *   **提示**：玩家卡关时可请求微小线索。
    *   **放弃**：可选择放弃并直接查看真相。
*   **双维评分系统**：
    *   **趣味性**：故事是否有趣、吸引人。
    *   **合理性**：逻辑是否严密、解答是否合理。
*   **现代化 UI**：暗色模式、玻璃拟态设计、流畅动画，提供沉浸式体验。

## 🛠️ 技术栈

*   **后端**：Python, FastAPI
*   **数据库**：SQLite, SQLAlchemy
*   **AI 接口**：OpenAI Compatible API (默认配置为 OpenRouter)
*   **前端**：HTML5, JavaScript, Tailwind CSS (CDN), Marked.js

## 🚀 快速开始

### 1. 环境准备

确保已安装 Python 3.8+。

### 2. 安装依赖

```bash
pip install -r server/requirements.txt
```

### 3. 配置环境

在项目根目录创建 `.env` 文件，并填入你的 API Key：

```env
OPENROUTER_API_KEY=sk-or-your-api-key-here
```

### 4. 运行服务

```bash
# 开发模式
uvicorn server.main:app --reload
```

或者直接运行入口文件（如果有）：
```bash
python server/main.py
```

访问浏览器：`http://127.0.0.1:8000`

## 📦 服务器部署指南

推荐使用 Nginx 作为反向代理服务器。

### 1. 使用 PM2 运行后端

```bash
# 安装 PM2
npm install -g pm2

# 启动服务
pm2 start ecosystem.config.js
```

### 2. 配置 Nginx

编辑 Nginx 配置文件（通常位于 `/etc/nginx/sites-available/default` 或 `/etc/nginx/conf.d/haiguitang.conf`）：

```nginx
server {
    listen 80;
    server_name your_domain.com;  # 替换为你的域名或 IP

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # 可选：静态文件缓存
    location /static {
        alias /path/to/haiguitang/server/static; # 替换为实际路径
        expires 30d;
    }
}
```

重启 Nginx：
```bash
sudo nginx -t
sudo systemctl restart nginx
```

## 📂 项目结构

```
D:\haiguitang
├── server/
│   ├── main.py             # 主程序入口 (API & 逻辑)
│   ├── models.py           # 数据库模型 (User, Puzzle, GameSession)
│   ├── database.py         # 数据库连接
│   ├── templates/          # HTML 模板
│   │   ├── index.html      # 首页
│   │   └── game.html       # 游戏页
│   └── static/             # 静态资源
├── haiguitang.db           # SQLite 数据库文件
├── ecosystem.config.js     # PM2 配置文件
└── requirements.txt        # Python 依赖
```

## 📝 贡献与开发

*   **添加题目**：可以直接操作数据库 `puzzles` 表添加新的海龟汤题目。
*   **修改提示词**：在 `server/main.py` 中的 `system_prompt` 变量中修改 AI 的行为指令。

## 📄 许可证

MIT License
