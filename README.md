# Pixelmator Image AI Bridge

一个连接 Pixelmator Pro 与 Google Gemini AI 的图像处理桥接工具。通过自然语言指令，让 AI 帮你处理图像，并将结果无缝导回 Pixelmator。

## 功能特性

- **图层导出**：一键导出 Pixelmator Pro 中选中的图层，自动裁剪透明区域
- **AI 图像处理**：通过自然语言指令让 Gemini AI 修改、生成图像
- **自动压缩**：发送前自动压缩图像，避免文件大小超限
- **图层导入**：将 AI 生成的图像导回 Pixelmator，保持原有位置
- **响应日志**：每次 API 响应自动保存为 JSON 文件，便于调试

## 系统要求

- macOS（需要 Pixelmator Pro）
- Python 3.10+
- Pixelmator Pro

## 安装

1. 克隆仓库：
```bash
git clone https://github.com/Angelobhl/pixelmator-image-ai.git
cd pixelmator-image-ai
```

2. 创建虚拟环境并安装依赖：
```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

3. 配置 API Key：

编辑 `config/default_config.json`，填入你的 OpenRouter API Key：
```json
{
    "api_key": "your-openrouter-api-key",
    ...
}
```

## 使用方法

1. 启动 Pixelmator Pro 并打开一个文档

2. 运行应用：
```bash
python src/main.py
```

3. 在 Pixelmator 中选择要处理的图层

4. 在应用界面中：
   - 点击 **导出图层** 导出当前选中图层
   - 在 **指令输入** 中输入自然语言指令，例如：
     - "将背景改为赛博朋克风格"
     - "添加日落光效"
     - "生成一个梦幻森林场景"
   - 点击 **开始处理** 发送给 AI
   - 处理完成后点击 **导入图层** 将结果导回 Pixelmator

## 项目结构

```
pixelmatorImageAI/
├── config/
│   └── default_config.json    # 默认配置文件
├── logs/                      # 日志和 API 响应存储
├── src/
│   ├── main.py               # 应用入口
│   ├── bridge/
│   │   ├── pixelmator.py     # Pixelmator Pro AppleScript 桥接
│   │   └── applescript.py    # AppleScript 执行器
│   ├── core/
│   │   ├── api_client.py     # OpenRouter API 客户端
│   │   ├── config.py         # 配置管理
│   │   └── image_processor.py # 图像预处理
│   ├── gui/
│   │   └── main_window.py    # 主窗口 GUI
│   └── utils/
│       └── logger.py         # 日志工具
└── temp/                     # 临时文件存储
```

## 配置说明

`config/default_config.json` 配置项：

| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| `api_key` | OpenRouter API Key | - |
| `default_model` | 使用的 AI 模型 | `google/gemini-3-pro-image-preview` |
| `temperature` | 生成温度 | `0.7` |
| `max_tokens` | 最大 token 数 | `4096` |
| `max_image_size` | 最大图像尺寸（像素） | `2048` |
| `image_quality` | JPEG 压缩质量 | `85` |

## API 响应日志

每次 API 调用后，完整的响应数据会保存到 `logs/` 目录下，文件名格式为 `<毫秒时间戳>.json`。这有助于：

- 调试 API 调用问题
- 分析 AI 响应内容
- 记录使用历史

## 技术栈

- **GUI**: PySide6 (Qt)
- **API**: OpenAI SDK (OpenRouter 兼容)
- **图像处理**: Pillow (PIL)
- **自动化**: AppleScript

## 工作流程

```
┌─────────────────┐
│  Pixelmator Pro │
└────────┬────────┘
         │ 导出图层
         ▼
┌─────────────────┐
│   图像压缩      │
│   (JPEG 85%)    │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│   Gemini AI     │
│  (OpenRouter)   │
└────────┬────────┘
         │ 返回图像
         ▼
┌─────────────────┐
│   导入图层      │
│  (保持位置)     │
└─────────────────┘
```

## 许可证

MIT License

## 致谢

- [Pixelmator Pro](https://www.pixelmator.com/pro/)
- [Google Gemini](https://ai.google.dev/)
- [OpenRouter](https://openrouter.ai/)