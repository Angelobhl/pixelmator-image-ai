# Gemini Vision Bridge for Pixelmator Pro - 需求规格说明书

## 1. 项目定位

开发一个轻量级的 macOS 悬浮窗应用，通过 AppleScript 桥接 Pixelmator Pro 与 Gemini API（通过 OpenRouter SDK），实现**语义化图层编辑**。

---

## 2. 核心功能模块

### A. 交互层 (GUI - Python/PySide6)

| 功能 | 描述 |
|------|------|
| 悬浮控制台 | 始终置顶（Always on Top）的半透明窗口 |
| 指令输入框 | 用户输入自然语言指令（如 "将背景改为赛博朋克风格"） |
| 参数控制 | `Temperature` 滑块、`Focus Mode` 切换（全图/选中图层） |
| 状态反馈 | 多阶段进度显示、错误分级提示、完成通知、实时日志窗口 |

### B. 桥接层 (AppleScript)

| 功能 | 描述 |
|------|------|
| 上下文抓取 | 自动识别 Pixelmator Pro 当前活动文档及选中的图层 |
| 无损导出 | 将选中图层以透明 PNG 格式导出至系统缓存文件夹 |
| 结果写回 | 将处理后的图像作为新图层插入原文档，对齐坐标 |

### C. 逻辑层 (Python / OpenRouter SDK)

| 功能 | 描述 |
|------|------|
| API 集成 | 调用 OpenRouter SDK 处理 Image-to-Image 任务 |
| 图像预处理 | 检查图片尺寸，必要时进行等比例缩放 |
| 错误处理 | 网络中断、API 配额不足、Pixelmator 未启动等情况报错 |

---

## 3. 状态反馈系统（优化）

### 3.1 多阶段进度显示

```
[准备中] → [上传图像] → [AI处理中] → [下载结果] → [写入Pixelmator]
```

每个阶段显示：
- 当前阶段名称
- 阶段进度百分比（如适用）
- 预计剩余时间（可选）

### 3.2 错误分级与提示

| 错误级别 | 类型 | 示例 | 恢复建议 |
|----------|------|------|----------|
| **Critical** | 系统级 | Pixelmator 未启动、权限被拒绝 | 引导用户打开应用或授权 |
| **Error** | API 级 | API Key 无效、配额耗尽 | 引导用户检查配置或升级套餐 |
| **Warning** | 网络级 | 连接超时、响应缓慢 | 建议重试或检查网络 |
| **Info** | 业务级 | 图层为空、尺寸过大 | 自动处理或提示用户确认 |

### 3.3 完成通知

- 系统通知（macOS Notification Center）
- 可选声音提示
- 悬浮窗状态变化（颜色/图标）

### 3.4 实时日志窗口

- 可展开/收起的日志面板
- 显示时间戳 + 日志级别 + 消息
- 支持复制日志内容
- 自动滚动到最新条目

---

## 4. 数据结构设计

### 4.1 API 交互数据结构

#### 请求结构

```python
@dataclass
class APIRequest:
    """API 请求结构"""
    model: str                    # 模型标识，如 "google/gemini-3-pro-image-preview"
    messages: List[Message]       # 消息列表
    temperature: float = 0.7      # 生成随机性
    max_tokens: int = 4096        # 最大输出 token

@dataclass
class Message:
    """消息结构"""
    role: str                     # "system" | "user" | "assistant"
    content: List[ContentPart]    # 多模态内容

@dataclass
class ContentPart:
    """内容部分"""
    type: str                     # "text" | "image_url"
    text: Optional[str] = None
    image_url: Optional[dict] = None  # {"url": "data:image/png;base64,..."}
```

#### 响应结构

```python
@dataclass
class APIResponse:
    """API 响应结构"""
    success: bool
    data: Optional[ResponseData] = None
    error: Optional[ErrorInfo] = None
    usage: Optional[UsageInfo] = None

@dataclass
class ResponseData:
    """响应数据"""
    text: Optional[str] = None           # 文本描述
    image_base64: Optional[str] = None   # 返回的图像（Base64）
    image_format: str = "png"            # 图像格式

@dataclass
class UsageInfo:
    """Token 使用信息"""
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
```

#### 错误处理结构

```python
@dataclass
class ErrorInfo:
    """错误信息结构"""
    code: str              # 错误码，如 "E001", "E002"
    level: ErrorLevel      # 错误级别
    message: str           # 错误消息
    suggestion: str        # 恢复建议
    retryable: bool        # 是否可重试

class ErrorLevel(Enum):
    CRITICAL = "critical"
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"

# 错误码定义
ERROR_CODES = {
    "E001": {"level": ErrorLevel.CRITICAL, "message": "Pixelmator Pro 未运行", "suggestion": "请先启动 Pixelmator Pro"},
    "E002": {"level": ErrorLevel.CRITICAL, "message": "无访问权限", "suggestion": "请在系统偏好设置中授权"},
    "E003": {"level": ErrorLevel.ERROR, "message": "API Key 无效", "suggestion": "请检查 API Key 配置"},
    "E004": {"level": ErrorLevel.ERROR, "message": "API 配额已耗尽", "suggestion": "请升级套餐或等待配额重置"},
    "E005": {"level": ErrorLevel.WARNING, "message": "网络连接超时", "suggestion": "请检查网络连接后重试"},
    "E006": {"level": ErrorLevel.WARNING, "message": "图像尺寸过大", "suggestion": "已自动缩放处理"},
    "E007": {"level": ErrorLevel.INFO, "message": "未选中图层", "suggestion": "请在 Pixelmator 中选择要处理的图层"},
}
```

### 4.2 配置与状态管理

#### 基础配置项

```python
@dataclass
class AppConfig:
    """应用配置"""
    # API 配置
    api_key: str = ""                    # OpenRouter API Key
    default_model: str = "google/gemini-3-pro-image-preview"
    temperature: float = 0.7
    max_tokens: int = 4096

    # 图像处理配置
    max_image_size: int = 2048           # 最大图像尺寸（像素）
    image_quality: int = 95              # 导出质量

    # UI 配置
    window_opacity: float = 0.9          # 窗口透明度
    auto_hide: bool = True               # 鼠标离开后自动隐藏
    show_notification: bool = True       # 显示完成通知
    play_sound: bool = False             # 播放完成声音

    # 路径配置（相对于项目根目录）
    temp_dir: str = "./temp"            # 临时文件目录
```

#### 配置持久化

```python
# 配置文件路径: ./config/user_config.json（相对于项目根目录）
# 使用 JSON 格式存储

class ConfigManager:
    """配置管理器"""
    config_path: Path
    config: AppConfig

    def load(self) -> AppConfig: ...
    def save(self) -> None: ...
    def reset(self) -> None: ...
```

### 4.3 图像处理数据流

#### 预处理流程

```python
@dataclass
class ImagePreprocessResult:
    """预处理结果"""
    original_path: Path          # 原始图像路径
    processed_path: Path         # 处理后图像路径
    original_size: tuple         # 原始尺寸 (w, h)
    processed_size: tuple        # 处理后尺寸 (w, h)
    was_resized: bool            # 是否进行了缩放
    format: str                  # 图像格式

class ImagePreprocessor:
    """图像预处理器"""

    def check_size(self, image_path: Path) -> bool:
        """检查图像尺寸是否符合 API 限制"""

    def resize(self, image_path: Path, max_size: int) -> ImagePreprocessResult:
        """等比例缩放图像"""

    def convert_format(self, image_path: Path, format: str) -> Path:
        """转换图像格式"""

    def to_base64(self, image_path: Path) -> str:
        """转换为 Base64 编码"""
```

#### 缓存管理策略

```python
@dataclass
class CacheEntry:
    """缓存条目"""
    id: str                      # 缓存 ID（基于内容 hash）
    original_path: Path          # 原始图像路径
    processed_path: Path         # 处理后图像路径
    prompt: str                  # 使用的 Prompt
    model: str                   # 使用的模型
    created_at: datetime         # 创建时间
    expires_at: datetime         # 过期时间

class CacheManager:
    """缓存管理器"""
    cache_dir: Path              # 缓存目录
    max_cache_size: int          # 最大缓存大小（MB）
    max_cache_age: int           # 最大缓存时间（小时）

    def get(self, image_hash: str) -> Optional[CacheEntry]: ...
    def set(self, entry: CacheEntry) -> None: ...
    def clear_expired(self) -> None: ...
    def clear_all(self) -> None: ...
```

#### 临时文件管理

```python
class TempFileManager:
    """临时文件管理器"""
    temp_dir: Path               # 临时目录

    def create_temp_file(self, prefix: str, suffix: str) -> Path:
        """创建临时文件"""

    def cleanup(self) -> None:
        """清理所有临时文件"""

    def get_export_path(self) -> Path:
        """获取导出路径（用于 AppleScript）"""
```

#### 回写机制

```python
@dataclass
class WriteBackResult:
    """回写结果"""
    success: bool
    layer_name: Optional[str]    # 新图层名称
    error: Optional[ErrorInfo]   # 错误信息

class PixelmatorBridge:
    """Pixelmator 桥接器"""

    def export_layer(self, layer_name: Optional[str] = None) -> Path:
        """导出选中图层"""

    def import_layer(self, image_path: Path, position: tuple = (0, 0)) -> WriteBackResult:
        """导入图像为新图层"""

    def get_document_info(self) -> dict:
        """获取当前文档信息"""

    def get_selected_layer_info(self) -> Optional[dict]:
        """获取选中图层信息"""
```

---

## 5. 技术架构

```
┌─────────────────────────────────────────────────────────────┐
│                      GUI Layer (PySide6)                     │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
│  │ 悬浮控制台  │  │ 参数控制    │  │ 状态反馈 + 日志     │  │
│  └─────────────┘  └─────────────┘  └─────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    Logic Layer (Python)                      │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
│  │ API Client  │  │ 图像处理    │  │ 配置管理            │  │
│  │ (OpenRouter)│  │ 预处理/缓存 │  │ 状态管理            │  │
│  └─────────────┘  └─────────────┘  └─────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                  Bridge Layer (AppleScript)                  │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
│  │ 图层导出    │  │ 图层导入    │  │ 文档/图层信息获取   │  │
│  └─────────────┘  └─────────────┘  └─────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    Pixelmator Pro                            │
└─────────────────────────────────────────────────────────────┘
```

---

## 6. 项目路线图

### 第一阶段：MVP (最小可行性产品)

- [ ] 创建 Python 虚拟环境
- [ ] 建立 Python 环境与 OpenRouter API 连通性测试
- [ ] 编写基础 AppleScript，实现"一键导出选中图层至 /tmp/"
- [ ] 实现基础 GUI：一个按钮 + 一个文本框
- [ ] 实现基础状态反馈（Loading 动画）

### 第二阶段：核心功能完善

- [ ] 实现完整的图像预处理流程
- [ ] 实现回写机制（自动导入到 Pixelmator）
- [ ] 实现配置管理（API Key、Temperature 等）
- [ ] 实现错误分级与提示

### 第三阶段：用户体验优化

- [ ] 多阶段进度显示
- [ ] 实时日志窗口
- [ ] 完成通知
- [ ] 窗口置顶与透明度控制
- [ ] 预览功能

### 第四阶段：高级功能

- [ ] 多模型切换（Gemini Flash / Pro）
- [ ] Prompt 历史记录
- [ ] 缓存管理
- [ ] 蒙版支持

---

## 7. 文件结构规划

```
pixelmator-ai/
├── src/
│   ├── main.py                 # 应用入口
│   ├── gui/
│   │   ├── __init__.py
│   │   ├── main_window.py      # 主窗口
│   │   ├── widgets/            # UI 组件
│   │   └── styles/             # QSS 样式
│   ├── core/
│   │   ├── __init__.py
│   │   ├── api_client.py       # OpenRouter API 客户端
│   │   ├── image_processor.py  # 图像处理
│   │   └── config.py           # 配置管理
│   ├── bridge/
│   │   ├── __init__.py
│   │   ├── applescript.py      # AppleScript 桥接
│   │   └── pixelmator.py       # Pixelmator 操作封装
│   └── utils/
│       ├── __init__.py
│       ├── logger.py           # 日志工具
│       ├── cache.py            # 缓存管理
│       └── temp_files.py       # 临时文件管理
├── scripts/
│   └── pixelmator.as           # AppleScript 脚本
├── config/
│   ├── default_config.json     # 默认配置
│   └── user_config.json        # 用户配置（运行时生成）
├── temp/                       # 临时文件目录（运行时生成）
├── cache/                      # 缓存目录（运行时生成）
├── tests/
│   └── ...                     # 测试文件
├── .gitignore                  # Git 忽略文件（包含 temp/、cache/、config/user_config.json）
├── requirements.txt
└── README.md
```