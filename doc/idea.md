这份需求文档旨在为你构建一个名为 **"Gemini Vision Bridge for Pixelmator Pro"** 的桌面辅助工具。它将作为 Pixelmator Pro 的“非官方 AI 插件面板”，利用 Gemini 3 Pro (Nano Banana Pro) 的多模态能力实现局部图像编辑。

---

## 🛠 需求规格说明书 (PRD)

### 1. 项目定位

开发一个轻量级的 macOS 悬浮窗应用，通过 AppleScript 桥接 Pixelmator Pro 与 Gemini 3 Pro API，实现**语义化图层编辑**（例如：通过文字描述修改、重绘或增强选中的图层内容）。

### 2. 核心功能模块

#### A. 交互层 (GUI - Python/PySide6)

* **悬浮控制台：** 一个始终置顶（Always on Top）的半透明窗口。
* **指令输入框：** 用户输入自然语言指令（如 "将背景改为赛博朋克风格"）。
* **参数控制：**
* `Temperature` 滑块：控制 AI 生成的随机性。
* `Focus Mode` 切换：选择是处理“全图”还是“选中的图层”。


* **状态反馈：** 显示 API 调用进度条或 Loading 动画。

#### B. 桥接层 (AppleScript)

* **上下文抓取：** 自动识别 Pixelmator Pro 当前活动文档及选中的图层。
* **无损导出：** 将选中图层以透明 PNG 格式导出至系统缓存文件夹。
* **结果写回：** 将 Gemini 处理后的图像作为新图层插入原文档，并对齐坐标。

#### C. 逻辑层 (Python / Gemini)

* **API 集成：** 调用 `google-generativeai` 处理 Image-to-Image 任务。
* **图像预处理：** 自动检查图片尺寸，必要时进行等比例缩放以符合 API 限制。
* **错误处理：** 针对网络中断、API 配额不足或 Pixelmator 未启动等情况报错。

---

### 3. 技术架构

---

### 4. 任务分配 (Language Breakdown)

| 语言 | 负责任务 | 关键点 |
| --- | --- | --- |
| **Python (Logic)** | API 调度、图像 Base64 编码、多线程处理防止界面卡死 | 需使用 `threading` 模块 |
| **Python (GUI)** | PySide6 窗口渲染、置顶逻辑、样式表 (QSS) 美化 | 需处理 `Qt.WindowStaysOnTopHint` |
| **AppleScript** | 操控 Pixelmator 的 `export` 和 `make new layer` 指令 | 需处理沙盒路径权限问题 |
| **JSON** | 与 Gemini 交换数据，定义 Prompt 模板 | 结构化 Prompt 优化 |

---

## 🚀 项目路线图 (Roadmap)

### 第一阶段：MVP (最小可行性产品) - **当前阶段**

* [ ] 当前项目下创建一个Python虚拟环境
* [ ] 建立 Python 环境与 API 连通性测试。
* [ ] 编写基础 AppleScript，实现“一键导出选中图层至 /tmp/”。
* [ ] 实现基础 GUI：一个按钮 + 一个文本框。

### 第二阶段：交互优化 (User Experience)

* [ ] **反向写回：** 处理完成后，图片自动导回 Pixelmator 而非手动拖入。
* [ ] **置顶与透明度：** 实现窗口自动贴附在 Pixelmator 侧边，支持鼠标离开后淡化。
* [ ] **预览功能：** 在发送 API 之前，在 GUI 窗口内显示即将处理的缩略图。

### 第三阶段：高级功能 (Advanced AI)

* [ ] **多模型切换：** 支持在 Gemini 3 Flash (快) 和 Pro (精) 之间切换。
* [ ] **历史记录：** 记录最近 5 次的 Prompt，方便快速复用。
* [ ] **蒙版支持：** 利用 Pixelmator 的选区（Selection）作为 Mask 发送给 Gemini 提升精准度。

---

## 关于SDK调用

不直接调用Gemini SDK，调用第三方OpenRouter SDK(@openrouter/sdk)实现。OpenRouter提供了Gemini的多种模型的支持。
