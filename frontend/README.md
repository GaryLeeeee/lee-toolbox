# Lee Toolbox 前端

Vue 3 + TypeScript + Vite。前端页面和 Python API 独立开发，生产构建由后端同域提供。

```sh
npm ci
npm run dev
npm run build
```

开发默认访问 `http://127.0.0.1:5173`，`/api` 转发至 `http://127.0.0.1:8000`。可通过 `LEE_TOOLBOX_WEB_PORT` 和 `LEE_TOOLBOX_API_PORT` 设置端口。完整项目推荐使用仓库根目录的启动脚本。

## 新增工具

1. 在 `src/tools/<tool-id>/` 新建 Vue 页面及工具自身逻辑。
2. 在 `src/registry/tools.ts` 增加工具记录，声明唯一 ID、名称、分类、关键词、路由、图标和懒加载组件。
3. 如需新分类，在同文件的 `categories` 中增加分类，包含名称、描述和图标。
4. 浏览器工具标记 `execution: 'browser'`；调用后端的工具标记 `execution: 'server'`，复用 `shared/api.ts` 处理请求和错误。

首页卡片、分类筛选、搜索和工具路由均由注册表派生。每个工具应只注册一个真实可用入口。收藏、最近使用保存在浏览器 localStorage；任务记录由后端管理。

## 页面与公共模块

- `app/App.vue`：导航、连接状态、全局消息与页面容器。
- `pages/HomePage.vue`：工作台、分类、搜索和最近任务。
- `tools/video-download/VideoDownload.vue`：视频解析和下载提交。
- `pages/TasksPage.vue`：任务筛选、检索和进度。
- `shared/components/TaskRow.vue`：任务状态、取消、重试、文件下载。
- `shared/state.ts`：共享任务状态、可见性相关轮询和提示。
- `shared/types.ts`：与 `docs/api-contract.md` 对应的接口类型。

`npm test -- --run` 运行 Vitest + Vue Test Utils 的虚拟 DOM 交互测试，不启动真实浏览器。

`npm run build` 包含严格 TypeScript 检查；路由页面按需加载。界面使用系统字体与本地打包 SVG 图标，无外部字体依赖。
