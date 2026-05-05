# 刷题助手

题库练习与模拟考试 App，技术栈：Vue 3 + Vite + Tauri 2 + Tailwind CSS 4

## 功能

- PDF 导入：将 PDF 题库文档解析为结构化题目数据
- 题库管理：本地存储和管理题目数据（JSON 文件）
- 自动组卷：根据条件（分类、难度、数量）自动组合题目生成试卷
- 答题模式：在线答题与模拟考试

## 开发

```bash
# 安装依赖
npm install

# 前端开发
npm run dev

# Tauri 完整应用开发
npm run tauri:dev

# 类型检查
npm run type-check

# 代码检查
npm run lint

# 格式化
npm run format
```

## 构建

```bash
# 构建前端
npm run build

# 构建完整应用（生成安装包）
npm run tauri:build
```

## 添加新题库

1. 准备 PDF 题库文件
2. 使用 PDF 导入功能解析题目
3. 在 App 中按条件组卷、答题

## 项目结构

```
src/
├── main.ts              # 应用入口
├── App.vue              # 根组件
├── views/               # 页面视图
├── types/               # TypeScript 类型定义（题目、试卷）
├── router/              # Vue Router 配置
├── style.css            # 全局样式
src-tauri/               # Tauri 后端（Rust）
```

## 许可证

MIT