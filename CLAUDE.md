# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

PDF 题库导入与自动组卷 App，技术栈：Vue 3 + Vite + Tauri 2 + Tailwind CSS 4

### 核心功能

- **PDF 导入**: 将 PDF 题库文档解析为结构化题目数据
- **题库管理**: 本地存储和管理题目数据（JSON 文件）
- **自动组卷**: 根据条件（分类、难度、数量）自动组合题目生成试卷
- **答题模式**: 在线答题与模拟考试

## 常用命令

```bash
# 开发
npm run dev              # 启动前端开发服务器
npm run tauri:dev        # 启动 Tauri 开发模式（完整应用）

# 构建
npm run build            # 构建前端
npm run tauri:build      # 构建完整应用（生成安装包）

# 类型检查
npm run type-check       # TypeScript 类型检查

# 代码检查
npm run lint             # ESLint 检查
npm run lint:fix         # ESLint 自动修复

# 格式化
npm run format           # Prettier 格式化
```

## 项目结构

```
src/
├── main.ts              # 应用入口
├── App.vue              # 根组件
├── views/
│   └── Home.vue         # 主页
├── types/
│   └── question.ts      # TypeScript 类型定义（题目、试卷）
├── router/
│   └── index.ts         # Vue Router 配置
├── style.css            # 全局样式
src-tauri/               # Tauri 后端（Rust）
```

## PDF 导入流程（待实现）

1. 用户选择 PDF 文件
2. Python 脚本：PDF → 按页拆分 → RapidOCR 识别 → 本地 LLM（ollama）结构化 → 导出 JSON
3. App 读取 JSON 文件，导入题库
4. 用户在 App 中按条件组卷、答题
