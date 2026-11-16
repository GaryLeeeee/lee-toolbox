# Lee Toolbox

可持续扩展的本地工具箱。首版包含工具工作台、抖音视频下载和任务中心。

> 本项目仅供个人学习与技术交流，不用于商业用途。

采用单仓库结构：Vue 3 + TypeScript 前端与 Python FastAPI 后端分别管理依赖。开发时各自运行，构建后由 FastAPI 同域提供网页和 API。

## 快速开始

需要 Python 3.11+ 和 Node.js 22.12+。在项目根目录运行：

```bash
./scripts/setup.sh
./scripts/build.sh
./scripts/start.sh
```

打开 <http://127.0.0.1:8000>。按 `Ctrl+C` 关闭服务与下载 worker。

首次安装后，日常使用只需运行 `./scripts/start.sh`。代码更新后如依赖变化，重新运行 setup；前端变化则重新 build。前端使用 `package-lock.json`，后端使用 `requirements.lock.txt` 固定已验证的依赖版本。

FFmpeg 优先使用系统安装版本，未安装时使用 Python 依赖 `imageio-ffmpeg` 提供的二进制程序。健康检查会显示其可用性。

## 开发

```bash
./scripts/dev.sh
```

前端地址为 <http://127.0.0.1:5173>，API 地址为 <http://127.0.0.1:8000/api/health>。Vite 将 `/api` 转发给后端；前后端代码均支持开发重载。

端口冲突时可以指定：

```bash
LEE_TOOLBOX_API_PORT=8010 LEE_TOOLBOX_WEB_PORT=5180 ./scripts/dev.sh
```

正式运行可用 `LEE_TOOLBOX_API_PORT=8010 ./scripts/start.sh`。默认仅监听本机回环地址，适合个人使用。

```bash
./scripts/test.sh
```

该命令执行后端自动化测试、前端组件交互测试、TypeScript 检查与生产构建。测试使用隔离的数据库、受控媒体和虚拟 DOM，不依赖抖音在线服务，也不会打开真实浏览器。

## 使用流程

1. 在首页进入「视频下载」。
2. 粘贴抖音分享文案或作品链接，点击解析。
3. 确认标题、作者、时长与可选画质，再创建下载任务。
4. 在任务中心查看进度、取消任务、重试失败任务或下载结果。

下载使用平台提供的播放文件，不承诺取得作者上传前的母版。画面内已有的作者标记会保留；页面显示的画质来自实际可下载的视频流。

平台接口、匿名会话和签名会变化。解析失败时会显示可读原因；遇到平台验证或作品不可访问时，不会无限重试。抖音解析器集中在 `backend/app/providers/douyin.py`，便于单独更新。

## 目录

```text
frontend/src/app/         布局和路由
frontend/src/registry/    工具注册表
frontend/src/shared/      公共状态、API 客户端、组件与格式化
frontend/src/tools/       各工具的页面和交互
backend/app/providers/   平台解析适配器
backend/app/core/        配置、错误与网络访问约束
backend/app/storage/     SQLite 任务持久化
backend/app/jobs/        后台 worker 和任务执行
backend/app/services/    下载、媒体验证等服务
backend/tests/           后端自动化测试
scripts/                统一安装、开发、构建、测试和运行
docs/                   接口约定和扩展说明
data/                   本机数据库、结果文件和临时文件（不入 Git）
```

## 数据与任务

默认数据目录为项目下的 `data/`，可通过 `LEE_TOOLBOX_DATA_DIR` 指定绝对路径。前端收藏及最近使用保存在当前浏览器的本地存储中；任务和下载文件保存在服务端本机。

任务状态包括排队、解析、下载、校验、完成、失败、取消和中断。取消/失败会清理未完成的临时文件；服务重启后，之前正在执行的任务会标记中断，可手动重试。重试会创建新任务，保留原任务历史。已完成文件手工移除后，页面不再提供有效下载。

多个服务实例不应同时使用同一个数据目录。任务历史、下载文件和安装依赖均已加入 `.gitignore`。

## 新增工具

参见 [新增工具指南](docs/adding-tools.md) 和 [API 契约](docs/api-contract.md)。首页入口、搜索、分类和工具路由由注册表驱动。JSON 格式化等工具可完全在浏览器执行；下载、音视频处理类工具复用后端任务与文件服务。

## 解析实现参考

抖音解析流程参考 [yt-dlp 抖音提取修复 PR #17826](https://github.com/yt-dlp/yt-dlp/pull/17826)，通过匿名会话取得作品详情，再选择可用的播放资源。该适配器并非抖音官方 API SDK，需要随平台变化维护。

