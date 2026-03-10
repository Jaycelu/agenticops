# AgenticOps 部署说明

## 环境要求

- Python `3.11+`
- Node.js `18+`
- PostgreSQL `14+`
- 可访问的 `NetBox / ELK / Zabbix / LLM API`

## 1. 配置环境变量

复制示例文件：

```bash
cp deploy/env.example backend/.env
```

至少需要确认以下配置：

- `APP_SECRET_KEY`
- `DATABASE_URL`
- `NETBOX_URL` / `NETBOX_API_TOKEN`
- `ELK_URL` / `ELK_USERNAME` / `ELK_PASSWORD`
- `ZABBIX_URL` / `ZABBIX_API_URL` / `ZABBIX_USERNAME` / `ZABBIX_PASSWORD`
- `LLM_API_URL` / `LLM_API_KEY` / `LLM_MODEL_NAME`
- `FRONTEND_URL`

## 2. 启动后端

```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python3 main.py
```

启动后可访问：

- API：`http://localhost:8000`
- Docs：`http://localhost:8000/docs`
- Health：`http://localhost:8000/health`

## 3. 启动前端

```bash
cd frontend
npm install
npm run dev
```

启动后可访问：

- Web UI：`http://localhost:5173`

## 4. 健康检查

```bash
curl http://localhost:8000/health
```

数据库连接不可用时，服务会返回 `503`。

## 5. 常见排查

### 后端无法启动

- 检查 Python 版本：`python3 --version`
- 检查依赖是否安装成功：`pip list`
- 检查数据库连接串是否正确
- 查看日志目录：`logs/`

### 前端无法启动

- 检查 Node.js 版本：`node -v`
- 重新安装依赖：`npm install`
- 检查 `5173` 端口是否已被占用

### 数据源接入失败

- 检查 NetBox / ELK / Zabbix 地址与凭据
- 确认目标系统对当前部署机器可达
- 优先使用测试账号和只读权限验证接入

## 6. 生产部署建议

- 使用 `systemd`、容器编排或其他进程管理工具托管前后端
- 在反向代理层启用 HTTPS
- 把敏感配置放入环境变量或密钥管理系统
- 将日志、缓存、运行数据目录加入忽略规则，避免提交到仓库
