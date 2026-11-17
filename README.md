# Lee Toolbox

可持续扩展的本地工具箱，包含工具工作台、抖音视频下载、小红书资源导出、浏览器开发工具和任务中心。

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

小红书支持图片和 MP4 视频导出，无需 macOS 或 Xcode。暂不支持直接导出 Live Photo；Live 笔记可以分别选择静态原图和动态视频。

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

### 小红书图片与视频

1. 进入「小红书导出」，粘贴笔记分享文案或链接，点击解析。
2. 查看预览及水印状态，勾选需要导出的图片或视频，创建导出任务。Live 笔记的静态原图和动态视频分别列出，可独立选择。
3. 在任务中心下载结果：单张图片为图片文件、单个视频为 MP4，多项资源为 ZIP，内含资源清单 `manifest.json`。

图片使用公开页面提供的原图标识；视频优先使用原始地址或明确标注无平台水印的流，没有时使用可获取的播放流。页面会区分无平台水印、含平台水印和水印状态未确认，ZIP 清单也记录该状态。导出保留源文件画面，不会裁剪、修补或去除水印；作者自行加入的文字/标记也会保留。只匿名访问公开分享页，不读取浏览器 Cookie；要求登录或验证的笔记会显示原因。

图片支持 JPEG、PNG、WebP、GIF 和 HEIC/HEIF，按实际格式保存原始文件。HEIC/HEIF 仅在网页预览时转换为 JPEG，下载仍保留原图；相册兼容性取决于接收端是否支持该格式。HEIC 解码依赖 `pillow-heif`，更新旧版本后需运行 `./scripts/setup.sh` 并重启服务。分享文案中的 `https\://` 转义写法也可识别。

**暂不支持直接导出 Live Photo。** Live 内容仅分别导出静态图片和普通 MP4 视频，不生成可导入苹果相册的 Live Photo 配对文件。网页常见的 `WEB_LIVEPHOTO_19` 动态视频带有平台水印，改为 MP4 导出仍会保留该水印。示例「又  到  九  月  底」可分别选择 10 张静态原图和 10 段带平台水印的动态视频；没有有效地址的资源会标为不可用。

**待优化：小红书 Live 动态视频的声音导出。** 部分 Live 在 App 中播放有声音，但当前获取的网页视频没有音轨，导出 MP4 也无声，尚不能完整还原 App 播放效果。有声资源获取及可能的异步采集流程仍待验证，详见下方研究文档中的待优化记录。

关于动态源的实测结果、登录限制和后续验证方向，见 [Live 无水印动态源研究](docs/xiaohongshu-live-research.md)。

### 开发工具

在首页或侧栏进入「开发工具」。输入和结果在浏览器内处理，无需连接下载服务。

- **JSON 格式化**在输入时自动校验并更新结果，可选缩进 2 或 4 个空格，也可压缩。结果支持语法高亮和折叠对象、数组，复制时保留完整内容、字段顺序与数字原文。
- **时间戳转换**支持整数秒、毫秒及北京时间（UTC+08:00）、UTC 互转，日期显示到秒。打开时默认填入当前日期和时间戳，两侧可分别更新。顶部显示每秒更新的 Unix 时间戳，支持复制。
- **Base64 互转**支持 UTF-8 文本编码及 Base64／Base64URL 解码。
- **文本差异对比**逐行标出新增、删除和行号，可只看差异或显示空白字符。

### 生活工具

- **日期计算器**计算两个公历日期相差的自然日天数，或按自然日、工作日向前或向后推算，显示星期和农历。工作日按周一至周五计算。
- **星座与四象**按公历生日查询星座和四象，旁边列出十二星座的日期范围和火、土、风、水四象分组。日期范围采用 [Farmers’ Almanac 的固定公历日期表](https://www.farmersalmanac.com/what-is-your-zodiac-sign)。

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
backend/app/native/      保留的 Live Photo 配对实验源码（未接入导出）
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

参见 [新增工具指南](docs/adding-tools.md)、[API 契约](docs/api-contract.md) 和 [小红书接口约定](docs/xiaohongshu-api.md)。首页入口、搜索、分类和工具路由由注册表驱动。JSON 格式化等工具可完全在浏览器执行；下载、音视频处理类工具复用后端任务与文件服务。

## 解析实现参考

抖音解析流程参考 [yt-dlp 抖音提取修复 PR #17826](https://github.com/yt-dlp/yt-dlp/pull/17826)，通过匿名会话取得作品详情，再选择可用的播放资源。该适配器并非抖音官方 API SDK，需要随平台变化维护。

小红书资源字段参考 [XHS-Downloader 的图片/视频适配器](https://github.com/JoeanAmier/XHS-Downloader/tree/master/source/application)，适配器位于 `backend/app/providers/xiaohongshu.py`。平台页面及 CDN 规则变化可能影响资源获取。

