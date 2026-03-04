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

## ☁️ 云端部署（Ubuntu + systemd + Nginx）

以下步骤适用于 Ubuntu 22.04/24.04 云主机（阿里云/腾讯云/AWS/GCP 等）。

### 0) 准备

- 已有一台可 SSH 登录的 Linux 云主机
- 已开放安全组端口：`22`, `80`, `443`
- （可选）已解析域名到该主机公网 IP

### 1) 安装系统依赖

```bash
sudo apt-get update
sudo apt-get install -y python3 python3-pip python3-venv nginx
```

### 2) 拉取代码并安装 Python 依赖

```bash
sudo mkdir -p /opt/haiguitang
sudo chown -R $USER:$USER /opt/haiguitang
git clone <your-repo-url> /opt/haiguitang
cd /opt/haiguitang

python3 -m venv .venv
source .venv/bin/activate
pip install -r server/requirements.txt
```

### 3) 配置环境变量

项目已提供 `.env.example`，直接复制：

```bash
cd /opt/haiguitang
cp .env.example .env
```

编辑 `.env`，至少设置：

```env
OPENROUTER_API_KEY=sk-or-your-real-key
DATABASE_URL=sqlite:///./haiguitang.db
```

> `DATABASE_URL` 不填时默认仍使用 `sqlite:///./haiguitang.db`。  
> 应用启动时会自动建表，并提供健康检查接口：`/health`。

### 4) 配置 systemd（推荐）

仓库提供模板：`deploy/systemd/haiguitang.service`

```bash
sudo cp /opt/haiguitang/deploy/systemd/haiguitang.service /etc/systemd/system/haiguitang.service
sudo systemctl daemon-reload
sudo systemctl enable haiguitang
sudo systemctl start haiguitang
sudo systemctl status haiguitang --no-pager
```

本机健康检查：

```bash
curl -i http://127.0.0.1:8000/health
```

### 5) 配置 Nginx 反向代理

仓库提供模板：`deploy/nginx/haiguitang.conf`

```bash
sudo cp /opt/haiguitang/deploy/nginx/haiguitang.conf /etc/nginx/sites-available/haiguitang
```

编辑该文件，把 `server_name your_domain_or_ip;` 改成你的域名或公网 IP，然后启用站点：

```bash
sudo ln -sf /etc/nginx/sites-available/haiguitang /etc/nginx/sites-enabled/haiguitang
sudo nginx -t
sudo systemctl restart nginx
```

### 6) 配置 HTTPS（Certbot）

如果已绑定域名，建议立即启用 HTTPS：

```bash
sudo apt-get install -y certbot python3-certbot-nginx
sudo certbot --nginx -d your_domain.com
```

验证自动续期：

```bash
sudo certbot renew --dry-run
```

### 7) 常用排障命令

```bash
# 查看应用日志
sudo journalctl -u haiguitang -f

# 查看 Nginx 日志
sudo tail -f /var/log/nginx/access.log
sudo tail -f /var/log/nginx/error.log

# 重启服务
sudo systemctl restart haiguitang
sudo systemctl restart nginx
```

### 8) （可选）使用 PM2

项目仍保留 `ecosystem.config.js`，如你偏好 PM2 可继续使用：

```bash
npm install -g pm2
pm2 start ecosystem.config.js
pm2 save
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
