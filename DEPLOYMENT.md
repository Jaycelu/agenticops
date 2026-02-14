# NetOps AI Platform 部署文档

## 环境要求

- Python 3.10+
- Node.js 16+ (用于前端开发)
- NetBox (已配置)
- 本地大模型 API (已配置)

## 端口配置（固定，不可修改）

**重要：以下端口配置为系统标准配置，后续不得随意修改**

- **后端服务端口**: `8000` - FastAPI 服务
- **前端服务端口**: `5173` - Vite 开发服务器

### 端口使用说明

- 后端服务监听地址：`http://0.0.0.0:8000`
- 前端服务监听地址：`http://0.0.0.0:5173`
- 前端代理配置：`/api` 请求代理到后端 `http://localhost:8000`

### 端口配置文件

- 后端端口配置：`backend/main.py` (uvicorn.run port=8000)
- 前端端口配置：`frontend/vite.config.ts` (server.port=5173)
- 前端代理配置：`frontend/vite.config.ts` (proxy target=http://localhost:8000)

## 快速启动

### 1. 配置环境变量

复制环境变量模板：
```bash
cp deploy/env.example backend/.env
```

编辑 `backend/.env`，配置以下参数：
- `NETBOX_URL`: NetBox 地址
- `NETBOX_API_TOKEN`: NetBox API Token
- `ZABBIX_URL`: Zabbix 地址
- `ZABBIX_API_URL`: Zabbix API URL
- `ZABBIX_USERNAME`: Zabbix 用户名
- `ZABBIX_PASSWORD`: Zabbix 密码
- `LLM_API_URL`: 本地大模型 API 地址
- `LLM_MODEL_NAME`: 模型名称

### 2. 启动后端服务

使用启动脚本：
```bash
cd deploy
./start.sh
```

或手动启动：
```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python3 main.py
```

后端服务将在 `http://localhost:8000` 启动

### 3. 启动前端服务（开发模式）

```bash
cd frontend
npm install
npm run dev
```

前端服务将在 `http://localhost:5173` 启动

## API 文档

启动后端服务后，访问 `http://localhost:8000/docs` 查看交互式 API 文档

## 健康检查

```bash
curl http://localhost:8000/health
```

## 测试 Chat API

```bash
curl -X POST http://localhost:8000/api/chat/ \
  -H "Content-Type: application/json" \
  -d '{"message": "查询所有设备"}'
```

## 项目结构

```
netops-ai-platform/
├── backend/              # 后端服务
│   ├── api/             # REST API
│   ├── agent/           # AI Agent
│   ├── mcp/             # MCP 工具封装
│   ├── models/          # LLM 接口
│   └── config/          # 配置
├── frontend/            # 前端应用
│   └── src/
│       ├── api/         # API 封装
│       ├── pages/       # 页面组件
│       └── store/       # 状态管理
└── deploy/              # 部署文件
    └── start.sh         # 启动脚本
```

## 当前功能

### ✅ 已实现

- NetBox 集成（设备查询、IP查询、站点查询）
- AI 对话调度（意图识别、执行计划、结果总结）
- 运维工作台（三栏布局：会话列表、对话区、执行轨迹）
- 执行轨迹可视化

### 🚧 待实现

- Zabbix 集成（告警查询、指标查询）
- ELK 集成（日志查询）
- 审计日志（Trace ID 存储）
- 用户认证（RBAC）

## 故障排查

### 后端无法启动

1. 检查 Python 版本：`python3 --version`
2. 检查依赖安装：`pip list`
3. 检查环境变量：`cat backend/.env`
4. 查看日志：`tail -f backend/logs/app.log`

### NetBox 连接失败

1. 检查 NetBox 地址和 API Token
2. 测试 NetBox 连接：`curl -H "Authorization: Token YOUR_TOKEN" NETBOX_URL/api/dcim/devices/`

### LLM 调用失败

1. 检查 LLM API 地址是否可访问
2. 查看后端日志中的错误信息

## 性能优化建议

1. 使用生产级 ASGI 服务器（如 Gunicorn + Uvicorn）
2. 启用 Redis 缓存
3. 使用数据库存储会话历史
4. 配置 Nginx 反向代理

## 安全建议

1. 不要在代码中硬编码敏感信息
2. 使用环境变量管理配置
3. 启用 HTTPS
4. 实施访问控制和审计日志
5. 定期更新依赖包