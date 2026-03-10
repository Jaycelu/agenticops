# AgenticOps 端口说明

更新时间：2026-03-10

## 默认端口

| 服务 | 端口 | 说明 |
| --- | --- | --- |
| FastAPI 后端 | `8000` | REST API、Swagger 文档、健康检查 |
| Vite 前端 | `5173` | Vue 3 开发服务器 |

## 本地访问地址

- 前端页面：`http://localhost:5173`
- API 文档：`http://localhost:8000/docs`
- 健康检查：`http://localhost:8000/health`

## 代码中的端口位置

- 后端入口：`backend/main.py`
- 前端开发配置：`frontend/vite.config.ts`

## 前端代理

开发模式下，Vite 会把 `/api` 请求代理到：

```text
http://localhost:8000
```

## 检查端口占用

```bash
ss -tlnp | grep -E ":(8000|5173)"
```

或：

```bash
netstat -tlnp | grep -E ":(8000|5173)"
```

## 服务无法启动时

1. 检查端口是否已被占用
2. 检查 `backend/.env` 是否存在且数据库可连接
3. 检查 Node.js / Python 版本是否满足要求
4. 查看项目根目录下的 `logs/` 输出

## 生产环境建议

- 使用反向代理统一入口
- 将前后端端口仅暴露给可信网络或本机
- 不在文档和脚本中硬编码服务器 IP
- 通过环境变量或部署系统注入运行参数
