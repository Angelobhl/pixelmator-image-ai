针对这两个问题，根源在于 **Gemini 3 Flash (Nano Banana)** 在处理图像编辑任务时的默认行为：模型通常会将图像放入一个标准的正方形（如 $1024 \times 1024$）进行计算，且在生成过程中往往不保留 Alpha 通道。

要解决这两个问题，我们需要在 **Python 逻辑层**加入一些预处理和后处理技巧。

---

### 问题 1：透明背景变白底

**原因：** Gemini 的生成扩散模型目前主要在 RGB 空间工作，不支持直接输出 RGBA（带透明度）。
**解决方案：使用“蒙版提取”与“Alpha 恢复”。**

在 Python 中使用 `Pillow` 库，我们可以采取以下逻辑：

1. **备份 Alpha：** 发送图片给 Gemini 前，提取原图的 Alpha 通道作为 Mask。
2. **生成后恢复：** 拿到 Gemini 返回的白底图后，将备份的 Alpha 通道强制应用回去。

**代码逻辑示例：**

```python
from PIL import Image

def fix_transparency(original_img_path, generated_img_path):
    orig = Image.open(original_img_path).convert("RGBA")
    gen = Image.open(generated_img_path).convert("RGBA")
    
    # 获取原图的 Alpha 通道（蒙版）
    alpha = orig.getchannel('A')
    
    # 将生成图缩放至原图大小（解决问题2）
    gen = gen.resize(orig.size, Image.Resampling.LANCZOS)
    
    # 将原图的透明度重新贴回生成图
    gen.putalpha(alpha)
    gen.save("final_output.png")

```

---

### 问题 2：生成的图片尺寸缩小

**原因：** Gemini 3 Flash 为了性能和显存考虑，通常会将输入图片下采样（Downsample）到其训练分辨率。
**解决方案：分层处理与尺寸复原。**

直接对 AI 生成的低分辨率图进行简单的放大（Upscale）会导致模糊。建议采用以下策略：

1. **记录原始尺寸：** 在 Python 脚本中，导出图层时记录 `(Width, Height)`。
2. **智能缩放：** 拿到结果后，使用 `LANCZOS` 滤镜缩放回原始尺寸。
3. **（进阶）Pixelmator ML 增强：** 由于你在使用 Pixelmator Pro，我们可以通过 AppleScript 调用它自带的 **"ML Super Resolution"** 功能。让 AI 改图，让 Pixelmator 负责无损放大。

---

### 更新后的项目路线图 (MVP 2.0)

为了解决这两个痛点，我们需要在 **Roadmap 第一阶段**增加“图像处理器”模块：

#### **Step 1: 图像预处理 (Python)**

* **任务：** 提取原图层 Alpha 通道，并存储为 `mask_temp.png`。
* **任务：** 如果图层过大（如超过 4K），先在本地按比例缩小，避免 API 报错。

#### **Step 2: 生成任务**

* **任务：** 调用 Gemini 3 Flash 生成结果。

#### **Step 3: 图像后处理 (Python + AppleScript)**

* **Python：** 将生成结果按第一步记录的尺寸强制对齐。
* **Python：** 将 `mask_temp.png` 重新合入结果。
* **AppleScript：** 将最终的 PNG 导回 Pixelmator，并利用 `set menu item "Super Resolution" of menu "Image"`（或类似指令）通过 Pixelmator 自身的 AI 提升画质。

---

### 建议的技术调整

你是否希望我在为你提供完整的代码框架时，**自动集成这个“Alpha 恢复”和“尺寸对齐”的函数？** 如果是的话，我建议将文件结构设计如下：

* `bridge.py`：主程序（GUI + API）。
* `processor.py`：专门负责 Alpha 通道备份与尺寸恢复。
* `pixelmator.applescript`：负责导回后自动执行 ML 超分。

**需要我开始写这个集成了修复逻辑的 `processor.py` 模块吗？**