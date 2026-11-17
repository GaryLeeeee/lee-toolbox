# 小红书 Live 无水印动态源研究

验证日期：2026-11-17。目标笔记：`6abd291e000000001c01d302`，分享链接 `https://xhslink.cn/o/AEWulOMuFzc`。

产品范围更新：工具现仅提供图片和 MP4 视频导出，Live 内容拆为两项资源并标明视频的水印状态；暂不支持直接导出 Live Photo。下文保留动态源与配对实验结果，配对组件未接入当前导出流程。

## 当前结论

无平台水印的 App Live 播放流确实存在：已从公开接口文档中的精确 CDN 地址下载另一条笔记的 `stream_type=16` / `livephoto_r256_1080p_16_andr` 视频，完整解码成功，抽取的画面未见平台水印。但尚未取得目标笔记的这类地址，不能把另一条笔记的成功当作目标笔记已支持。

JPG + MOV 配对实验已通过本机 Apple 框架读取验证，当前不作为产品导出能力；无水印 Live 的缺口是动态资源获取。目标笔记公开分享页提供的 10 段 `WEB_LIVEPHOTO_19` 是带水印视频，不能靠改扩展名、封装格式或配对元数据去除水印。

用户随后在应用内浏览器正常登录，本轮继续刷新目标笔记并核验：**登录后的网页仍没有提供不同的动态源**。10 张图片各只有一个非空 `EF4` 候选，均为 `/stream/1/10/19/..._19.mp4`；`EF5`、`EF6`、`EF7` 全为空。逐项对比，10 个媒体路径与匿名移动分享页一致。没有读取或导出账号 Cookie。

第一段已从登录页面实际观察到的精确地址重新下载，HTTP 200、495256 字节，SHA256 为 `2ecd94b8ed9e36f7bb46f06f7f80a699fadcf4e00c266c6ba8edf23d569a104a`，与先前确认带水印的文件逐字节相同；完整解码和第 1 秒抽帧均通过。因此目标笔记的网页登录路线本轮未取得无水印动态源。该结果不代表 App 响应或所有其他接口都没有干净资源。

桌面页面的官方 `index.6d635126.js` 模块 99843 只选择 `h264[0].masterUrl`，缺失时回退 `EF4[0].masterUrl`；它不读取 H.265。仅看默认播放地址不足以排除其他候选，因此本轮还检查了刷新后页面内这篇笔记的全部候选列表。全屏、自动播放及网页下载复用同一个选源逻辑，没有可切换至其他编码的 UI。

## 本轮实际请求与检查

| 路线 | 结果 | 可以得出的结论 |
| --- | --- | --- |
| Android Chrome / iPhone 小红书 UA 读取分享页 | 都返回 10 张 Live，仅 H.264 `WEB_LIVEPHOTO_19`，其他编码数组为空 | 本次切换 UA 没有取得额外动态源 |
| 下载首段无签名备用 CDN 视频 | HTTP 200；495256 字节，SHA256 与原带水印主源一致 | 此备用地址仅是同文件的副本 |
| 检查静态原图容器 | JPEG 在 EOI 结束，无尾随 MP4 或 MotionPhoto/MicroVideo 元数据 | 此原图不含可提取的隐藏动态 |
| 官方 H5 preload，匿名签名及正确请求结构 | HTTP 200、code 0，仅返回首张静态图、标题、正文 | 签名可以生效，但该响应没有 Live 资源 |
| 官方 Web 完整 feed，匿名签名 | HTTP 200、success=false、code=-101，提示无登录信息 | 当前完整 feed 请求需要登录；不等于登录后一定有干净 Live 流 |
| 另一条公开 App 响应的精确 type 16 地址 | HTTP 200；852893 字节；HEVC 1080×1440、30 fps、2.87 秒，无音轨；完整解码及抽帧检查通过 | 已观察到与网页流不同的可下载 App Live 源，不能推广为所有 type 16 都无水印 |
| 目标笔记首段按上述已观察的 type 16 路径格式替换 type 19 | HTTP 404 | 不支持直接将此 WEB19 文件名推导为 type 16；没有加入生产解析器 |

没有读取用户浏览器 Cookie，没有使用第三方账号或调用第三方解析服务。第三方接口文档仅用于读取其公开示例地址；媒体直接从小红书 CDN 下载。实验依赖只安装到被 Git 忽略的 `work/` 研究目录，没有增加生产依赖。

## 官方 H5 入口

分享页引用的官方 `main.8f5d99f.js` 模块 26642 声明预加载调用，模块 48607 选择 `edith.xiaohongshu.com` 作为 API 域。业务层的 camelCase 参数经客户端转为 snake_case，实际请求为：

```text
POST https://edith.xiaohongshu.com/api/sns/h5/v1/detailfeed/preload
JSON: note_id, xsec_token, xsec_source
```

签名使用全新匿名标识，按官方脚本的 `ranchi` 客户端信息生成 `XYS_` 请求头。直接无签名请求返回 406；签名后错误的 camelCase 请求体返回参数缺失；改正后返回静态预览。成功响应没有 `note_id`、`live_photo` 或视频流，不能用于完整 Live 导出。

完整 Web feed 路径为 `POST /api/sns/web/v1/feed`。使用一手客户端源码中的参数结构和 `xhs-pc-web` 签名后，本轮匿名调用返回明确的登录错误。

官方脚本仅作静态分析，未执行其中的代码。REA 记录：`ev_4f90ab6ba8415024a1c255437f6198255742d82f1c4ffe7ced243d0f3882f007`；语法解析成功，语义图有范围限制，不据此声称覆盖全部平台接口。

## 待优化：Live 动态视频的声音导出

- [ ] 补齐小红书 Live 动态视频的原声导出（记录日期：2026-11-17；状态：待优化，尚未实现）。

复现笔记：[Spider-Man🕸️(别问了，不发图)](https://xhslink.cn/o/5quExjFgAjT)，笔记 ID `6a68f521000000000e0347b7`。用户确认在小红书 App 播放 Live 时可以听到音乐；当前工具导出的 4 段 MP4 均无声音。

已验证：4 条网页候选均为 `h264/WEB_LIVEPHOTO_19`，`audioChannels`、`audioBitrate`、`audioDuration` 均为 0，实际文件检查也没有音轨。首段导出文件与重新下载的网页源逐字节一致，说明该样本不是导出过程移除了音频。完整公开笔记数据未提供其他编码候选或独立音频地址；这不代表 App 原 Live 没有声音，也不能据此认定音乐一定是独立配乐。此问题记录针对已验证的 Live 网页源，不泛指所有普通视频导出。

后续工作：

1. 验证 App 实际使用的有声视频或配套音频来源，并按笔记和每张 Live 的身份匹配资源。用户提供过“只提交链接、后台异步采集后可导出有声视频”的工具线索，但具体工具和接口尚未确认。
2. 若真实采集器需要异步等待，再接入任务中心的等待、查询、取消、超时和重启恢复流程；等待采集时不阻塞其他导出任务。不能仅增加等待时间就认为声音可以恢复。
3. 页面明确提示无音轨或声音尚未获取的状态；取得对应音频后再下载完整有声视频或合并音画，不用无关配乐替代原声。

验收要求：以上示例的各段导出视频具有可解码音轨，实际播放能听到与 App 对应的声音，音画同步且时长合理；异步超时或采集失败时给出明确结果，不能将无声文件标成有声导出成功。图片及已有普通视频导出保持可用。

本地核查记录位于 `work/xhs-live-audio-research/data/summary.json`、`candidate-inventory.json` 和 `work/xhs-live-audio-research/js/findings.json`（研究文件不入 Git）。网页播放器的静音设置与文件是否包含音轨是两回事，不能靠取消网页静音恢复文件中不存在的声音。

## 可继续验证的方向

1. 已完成正常登录后的网页核验，目标笔记依旧只有 WEB19。未取得原生 App 响应，不将网页数据冒充 App 数据。
2. 下一步需要目标笔记的 App 预览响应。已核对的开源实现在 App `images_list[].live_photo.media.stream.h265[]` 中取得播放地址；不是从网页 URL 还原原片。
3. 取得真实候选后，按图片身份匹配原图，实际下载并检查水印、音轨、时长与方向，再接入下载器并生成 Apple 配对文件。播放流不直接称为作者上传母版。

## 可复核来源与本地证据

- [官方页面主脚本](https://fe-static.xhscdn.com/formula-static/ranchi/public/js/main.8f5d99f.js)；SHA256 `4e841e49fb87624066582d891b8aff7406ec3e8093a7b89d6e22a73d4031c565`。
- [fmz200 的 App Live 保存实现](https://github.com/fmz200/wool_scripts/blob/main/Scripts/xiaohongshu/xiaohongshu.js)：缓存 App feed，再读取 H.265 播放地址。
- [公开 App 返回示例](https://docs.yddm.com/486370226e0)：提供本轮 type 16 精确测试地址；与用户笔记不同。
- [xhshow 源码](https://github.com/Cloxl/xhshow)：匿名签名研究；不是免登录访问所有接口的保证。
- [MediaCrawler](https://github.com/NanmiCoder/MediaCrawler)：完整 Web feed 的请求参数参考。
- `work/xhs-live-research/probe/findings.json`：UA、备用 CDN、图像容器及官方脚本记录。
- `work/xhs-live-research/signature/findings.md`：签名脚本及真实响应记录，签名/分享参数不写入本文件。
- `work/xhs-live-research/upstream/findings.md`：开源实现对比及另一条 App 视频的检查结果。
- `work/xhs-live-research/logged-web/logged-verification.json`：登录并刷新后的 10 个候选媒体路径、与匿名页面的逐项对比及首段文件校验，不含账号 Cookie 或签名查询参数。
- `work/xhs-live-research/logged-web/live-source-findings.json`：桌面播放器选源实现的源文件摘要及字节范围；提取模块的 REA 记录为 `ev_dd728061c2042375176dd872c2e3560829bd4886190fb63dd097a7e077c6042e`。

本轮没有将尚未成功的接口或猜测地址加入生产解析流程。
