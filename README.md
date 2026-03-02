# 飞书邮箱同步助手

将邮箱中的邮件信息同步到飞书多维表格的边栏插件。

## 功能特性

- 支持国内主流邮箱（QQ、网易163/126、飞书）
- 同步完整邮件字段（标题、内容、发件人、收件人、附件等）
- 手动同步 + 自动定时同步
- 安全的授权码加密存储

## 项目结构

```
feishu-mail-sync/
├── frontend/     # React 前端插件
└── backend/      # Python FastAPI 后端
```

## 快速开始

### 后端

```bash
cd backend
cp .env.example .env
pip install -r requirements.txt
python run.py
```

### 前端

```bash
cd frontend
npm install
npm run dev
```

### 在飞书中使用

1. 打开飞书多维表格
2. 点击「插件」→「自定义插件」→「+新增插件」
3. 输入前端服务地址（如 http://localhost:3000）

## 部署

### 后端部署

1. 修改 `.env` 中的 `ENCRYPTION_KEY` 为安全的随机值
2. 使用 gunicorn 或 uvicorn 部署：
   ```bash
   uvicorn app.main:app --host 0.0.0.0 --port 8000
   ```

### 前端部署

1. 修改 API 地址为后端服务地址
2. 构建并部署：
   ```bash
   npm run build
   # 将 dist 目录部署到静态服务器
   ```

## License

MIT
