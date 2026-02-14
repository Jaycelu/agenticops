# 数据库结构修复

## 问题描述
automation_task 表缺少 audit_trail 列，导致API调用失败。

## 修复内容
添加 audit_trail 列到 automation_task 表

## 执行SQL
```sql
ALTER TABLE automation_task ADD COLUMN audit_trail JSON;
UPDATE automation_task SET audit_trail = '[]'::jsonb WHERE audit_trail IS NULL;
```

## 影响
- 修复了自动化任务相关的API错误
- 确保前端能够正常显示采样数据
- 修复了数据库结构与代码模型的同步问题

## 修复时间
2026-02-14