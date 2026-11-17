# 小红书导出接口约定

工具 ID：`xiaohongshu-export`，页面路由 `/tools/xiaohongshu-export`。
已有抖音接口与任务默认行为保持兼容。下载执行时重新解析分享链接。

## 解析

`POST /api/xhs/resolve`，请求 `{ "text": "分享文案或链接" }`。

```json
{
  "platform": "xiaohongshu",
  "id": "note-id",
  "title": "笔记标题",
  "author": "作者",
  "source_url": "https://www.xiaohongshu.com/explore/note-id",
  "warnings": [],
  "assets": [
    {
      "id": "stable-asset-id",
      "kind": "video",
      "label": "Live 图 1 · 动态视频",
      "width": 1080,
      "height": 1440,
      "duration": 3.0,
      "available": true,
      "unavailable_reason": null,
      "watermark_status": "present",
      "preview_url": "/api/xhs/previews/temporary-random-token"
    }
  ]
}
```

kind 仅为 `image` / `video`。暂不支持直接导出 Live Photo；每张 Live 内容分别列出静态原图（image）和动态视频（video），可独立选择，静态图和视频的缺失不会影响另一项的可用性。缺少有效地址的资源标为 available=false 并说明原因。duration 秒，可为 null。preview_url 可为 null；仅为预览的短期本地代理地址，不暴露原媒体签名 URL。

watermark_status 为 `none`（原图/原始视频或源数据明确标记无平台水印）、`present`（已知含平台水印，如 WEB_LIVEPHOTO_19）或 `unknown`（未确认）。视频优先选原始或明确无平台水印的源，没有时可使用带水印或状态未知的播放源，并在页面显示实际状态；编码类型本身不代表无水印。原图和视频中的作者自加标记仍会保留。

预览代理应有短期缓存、数量上限、图片体积上限、固定允许域名和每跳 DNS 公网校验。仅接受解析阶段服务器生成的 token，不接受客户端传入 URL。

图片原文件支持 JPEG、PNG、WebP、GIF、HEIC/HEIF。HEIC/HEIF 原图使用 `pillow-heif` 完整解码校验，导出保留原始字节和相应图片类型；网页预览单独转为 JPEG 并处理照片方向，不把预览转码结果用于导出。HEIC/HEIF 预览仍受图片尺寸、帧数、8 MB 下载体积与超时限制。

## 导出任务

`POST /api/tasks`：

```json
{
  "tool_id": "xiaohongshu-export",
  "source_text": "分享文案或链接",
  "asset_ids": ["stable-asset-id"]
}
```

asset_ids 省略表示导出全部可用资源；显式空数组无效。最多选择100项，不允许重复/不存在/不可用资源。抖音请求省略tool_id时仍为 video-download。任务返回原有字段，新增可选 `asset_ids`、`asset_count`、`finished_assets`；旧任务无选择清单时为null。重试必须保留工具类型与选择清单。任务列表、取消、重试和文件接口共用。

单张图片直接返回图片文件，单个视频返回 MP4；多项资源返回 ZIP。ZIP 内 manifest.json 描述每个资源的文件名及 watermark_status，不包含媒体签名地址。导出保留源文件水印，不生成 JPG + MOV 配对文件，不调用 Apple 框架或 Swift 编译器。旧的 Live 资源 ID 需重新解析后选择；不将旧 Live 选择静默替换为静态图或视频。

在本地解码验证图片和视频后才发布文件；任一已选资源失败，整体任务失败并清理临时目录。总大小使用现有任务大小上限；取消/超时/重启恢复均清理本任务文件。ZIP文件名与成员名由服务端生成，不能使用第三方路径。

## Python provider 契约

`backend/app/providers/xiaohongshu.py`：

```python
@dataclass
class XhsAsset:
    id: str
    kind: str
    label: str
    width: int
    height: int
    duration: float | None
    image_urls: list[str]
    video_urls: list[str]
    available: bool = True
    unavailable_reason: str | None = None
    watermark_status: str = "unknown"

@dataclass
class ResolvedNote:
    platform: str
    id: str
    title: str
    author: str
    source_url: str
    assets: list[XhsAsset]
    warnings: list[str]
    headers: dict[str, str]

def resolve(text: str) -> ResolvedNote: ...
def public_note(note: ResolvedNote) -> dict: ...
```

定义本模块 `ProviderError(code, message)` 与抖音同样属性。public_note剔除image_urls/video_urls/headers，并为各asset给preview_url=null（API层注册预览后填入）。图片资源优先平台无水印版本，不做画面修补。稳定ID不得依赖短期签名地址。用户未授权登录时仅匿名访问公开分享页，不访问浏览器账户Cookie。
