# H5 Games

手机游戏 App，技术栈：Vue 3 + Vite + Tauri 2 + Tailwind CSS 4

## 功能

- 游戏列表：iOS App Store 风格界面，支持分类筛选和搜索
- 游戏模块：每个游戏独立运行，完全隔离
- 已包含游戏：2048

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

## 添加新游戏

1. 在 `src/games/` 下创建新目录
2. 创建 `index.vue` 作为游戏入口组件
3. 在 `src/data/games.json` 中添加游戏元数据
4. 在 `src/views/GameView.vue` 的 `gameComponents` 中注册组件映射

## 项目结构

```
src/
├── main.ts              # 应用入口
├── App.vue              # 根组件
├── components/          # 公共组件
├── views/               # 页面视图
├── games/               # 游戏模块（独立）
├── data/                # 游戏列表数据
├── router/              # 路由配置
├── stores/              # Pinia 状态管理
├── types/               # TypeScript 类型
src-tauri/               # Tauri 后端（Rust）
```

## 许可证

MIT