# 巡检模板配置指南

## 概述

巡检模板配置文件位于项目根目录下的 `storage/inspection_templates.json`，您可以通过修改此文件来自定义巡检模板。

## 模板结构

```json
{
  "templates": [
    {
      "template_id": "模板唯一标识",
      "name": "模板名称",
      "description": "模板描述",
      "device_role": "设备角色（如：核心交换机、接入交换机、防火墙）",
      "items": [
        {
          "item_id": "巡检项唯一标识",
          "name": "巡检项名称",
          "category": "巡检类别",
          "description": "巡检项描述",
          "commands": ["命令1", "命令2"],
          "severity": "严重级别",
          "threshold": {"max": 80},
          "device_types": ["支持的设备类型"],
          "enabled": true
        }
      ]
    }
  ]
}
```

## 巡检类别 (category)

- `device_status` - 设备状态
- `port_status` - 端口状态
- `link_status` - 链路状态
- `route_status` - 路由状态
- `security_status` - 安全状态

## 严重级别 (severity)

- `info` - 信息
- `warning` - 警告
- `error` - 错误
- `critical` - 严重

## 设备类型 (device_types)

- `huawei` - 华为设备
- `h3c` - H3C 设备
- `cisco` - 思科设备

## 阈值配置 (threshold)

```json
"threshold": {
  "max": 80,           // 最大值（警告阈值）
  "critical": 90       // 严重阈值
}
```

## 常用命令示例

### 华为设备

```json
{
  "commands": [
    "display cpu-usage",
    "display memory-usage",
    "display interface brief",
    "display ip routing-table",
    "display bgp peer",
    "display vlan",
    "display stp",
    "display device",
    "display environment"
  ]
}
```

### H3C 设备

```json
{
  "commands": [
    "display cpu",
    "display memory",
    "display interface brief",
    "display ip routing-table",
    "display bgp peer",
    "display vlan",
    "display stp"
  ]
}
```

### 思科设备

```json
{
  "commands": [
    "show processes cpu",
    "show memory statistics",
    "show interface brief",
    "show ip route",
    "show ip bgp summary",
    "show vlan brief",
    "show spanning-tree"
  ]
}
```

## 修改模板步骤

1. 编辑配置文件：
   ```bash
   vi storage/inspection_templates.json
   ```

2. 修改模板内容（添加、删除或修改巡检项）

3. 保存文件

4. 重启后端服务（或等待自动重载）：
   ```bash
   # 后端服务会自动检测文件变化并重新加载
   ```

## 创建新模板

在 `templates` 数组中添加新的模板对象：

```json
{
  "template_id": "my_custom_template",
  "name": "自定义巡检模板",
  "description": "我的自定义巡检模板",
  "device_role": "自定义角色",
  "items": [
    {
      "item_id": "custom_check",
      "name": "自定义检查",
      "category": "device_status",
      "description": "自定义巡检项",
      "commands": ["display custom-command"],
      "severity": "warning",
      "threshold": {"max": 100},
      "device_types": ["huawei"],
      "enabled": true
    }
  ]
}
```

## 禁用某个巡检项

将 `"enabled": true` 改为 `"enabled": false"`

## 注意事项

1. 修改配置文件后，后端服务会自动重新加载模板
2. `template_id` 必须唯一
3. `item_id` 在同一模板内必须唯一
4. 命令必须与设备型号匹配
5. 阈值配置会影响巡检结果的判断

## 备份

修改前建议备份原配置文件：
```bash
cp storage/inspection_templates.json storage/inspection_templates.json.backup
```
