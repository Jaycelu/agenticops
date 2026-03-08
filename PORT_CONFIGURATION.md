# NetOps AI 智能运维工作台 - 端口配置

**更新时间**: 2026-01-27
**版本**: v1.1

---

## 📊 端口分配

| 服务 | 端口 | 协议 | 状态 | 用途 |
|------|------|------|------|------|
| **FastAPI 后端** | **8000** | HTTP | ✅ 运行中 | REST API 服务 |
| **Streamlit 前端** | **5173** | HTTP | ✅ 运行中 | AI 对话式运维界面（已替换 Vue 3）|

---

## 🔄 前端替换说明

**原前端**: Vue 3 运行在端口 5173（已替换）  
**新前端**: Streamlit AI 运行在端口 5173

访问地址保持不变，但界面已升级为新的 AI 对话式运维工作台。

---

## 🌐 访问地址

### 本地访问

- **AI 运维界面**: http://localhost:5173
- **API 文档**: http://localhost:8000/docs
- **API 端点**: http://localhost:8000/api

### 远程访问

假设服务器 IP 为 `10.128.206.214`：

- **AI 运维界面**: http://10.128.206.214:5173
- **API 文档**: http://10.128.206.214:8000/docs
- **API 端点**: http://10.128.206.214:8000/api

---

## 🚀 服务管理

### 方式 1：使用 systemd 服务

**查看服务状态**:
```bash
systemctl status netops-frontend.service
systemctl status netops-backend.service
```

**启动服务**:
```bash
systemctl start netops-frontend.service
systemctl start netops-backend.service
```

**停止服务**:
```bash
systemctl stop netops-frontend.service
systemctl stop netops-backend.service
```

**重启服务**:
```bash
systemctl restart netops-frontend.service
systemctl restart netops-backend.service
```

### 方式 2：使用管理脚本

```bash
cd /opt/netops
./manage_services.sh
```

### 方式 3：手动管理

**启动后端**:
```bash
cd /opt/netops/backend
nohup python3 main.py > ../logs/backend.log 2>&1 &
```

**启动前端**:
```bash
cd /opt/netops/frontend
nohup npm run dev -- --host 0.0.0.0 --port 5173 > ../logs/frontend.log 2>&1 &
```

---

## 📝 配置说明

### 后端配置

**文件**: `/opt/netops/backend/.env`

```env
BACKEND_HOST=0.0.0.0
BACKEND_PORT=8000
```

### 前端配置

**目录**: `/opt/netops/frontend`

Vue 前端通过 Vite 启动参数配置端口：
```bash
npm run dev -- --host 0.0.0.0 --port 5173
```

### systemd 服务配置

**文件**: `/etc/systemd/system/netops-frontend.service`

```ini
[Service]
Type=simple
User=root
WorkingDirectory=/opt/netops/frontend
Environment="PATH=/usr/local/bin:/usr/bin:/bin"
ExecStart=/usr/bin/env npm run preview -- --host 0.0.0.0 --port 5173
Restart=always
```

---

## 🔍 端口检查

### 检查所有相关端口

```bash
netstat -tlnp | grep -E ":(8000|5173)"
# 或
ss -tlnp | grep -E ":(8000|5173)"
```

### 检查特定端口

```bash
# 检查后端端口
netstat -tlnp | grep 8000

# 检查前端端口
netstat -tlnp | grep 5173
```

### 测试服务响应

```bash
# 测试后端 API
curl http://localhost:8000/docs

# 测试前端页面
curl http://localhost:5173
```

---

## 🛠️ 故障排查

### 端口被占用

**问题**: 启动服务时提示端口已被占用

**解决方案**:
```bash
# 查找占用端口的进程
lsof -i :5173  # 或 8000

# 停止占用端口的进程
kill <PID>

# 或强制停止
kill -9 <PID>
```

### 服务无法启动

**问题**: 服务启动失败

**解决方案**:
```bash
# 查看后端日志
tail -f /opt/netops/logs/backend.log

# 查看前端日志
tail -f /opt/netops/logs/streamlit.log

# 查看 systemd 日志
journalctl -u netops-frontend.service -f
```

### 无法访问服务

**问题**: 浏览器无法访问

**检查清单**:
1. ✅ 确认服务已启动：`netstat -tlnp | grep 5173`
2. ✅ 确认防火墙允许端口：`sudo ufw allow 5173` 和 `sudo ufw allow 8000`
3. ✅ 确认服务器 IP 正确：`hostname -I`
4. ✅ 确认网络连接正常：`ping <服务器IP>`

---

## 🔒 安全建议

1. **生产环境建议**:
   - 使用反向代理（Nginx）统一入口
   - 启用 HTTPS
   - 限制 IP 访问
   - 配置防火墙规则

2. **防火墙配置示例**:
```bash
# 只允许特定 IP 访问
sudo ufw allow from 10.128.0.0/16 to any port 8000
sudo ufw allow from 10.128.0.0/16 to any port 5173
```

---

## 📚 相关文档

- [部署文档](./DEPLOYMENT.md)
- [实施总结](./IMPLEMENTATION_SUMMARY.md)
- [产品需求](./PRD.md)

---

**文档结束**
