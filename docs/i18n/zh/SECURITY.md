[English](../../../SECURITY.md) | [中文](SECURITY.md)

# 安全政策

## 报告漏洞

**请勿为安全漏洞创建公开 Issue。**

如果你发现 JARVIS 中的安全漏洞，请通过以下方式负责任地报告：

1. **GitHub 私密漏洞报告（推荐）**
   前往本仓库的 [Security 标签页](https://github.com/hyhmrright/JARVIS/security/advisories/new)，点击 "Report a vulnerability"。

2. **邮件**
   发送详情至 **hyhmrright@gmail.com**。

请包含以下信息：
- 漏洞描述
- 复现步骤
- 潜在影响
- 建议的修复方案（如有）

## 响应时间

| 动作 | 时间 |
|------|------|
| 确认收到 | 72 小时内 |
| 初步评估 | 1 周内 |
| 修复发布 | 取决于严重程度 |

## 支持的版本

| 版本 | 是否支持 |
|------|---------|
| `main` 最新版 | 是 |
| `dev` 分支 | 尽力而为 |
| 旧版本 | 否 |

## 适用范围

本政策适用于：

- JARVIS 后端（FastAPI、Python）
- JARVIS 前端（Vue 3、TypeScript）
- Docker 配置和部署
- 认证和加密（JWT、bcrypt、Fernet）
- 数据库访问和 API 端点
