"""
Main window GUI module.
Provides the floating control panel interface.
"""

from pathlib import Path
from typing import Optional

from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QTextEdit,
    QPushButton,
    QLabel,
    QSlider,
    QComboBox,
    QGroupBox,
    QProgressBar,
    QTextBrowser,
    QScrollArea,
)
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QFont, QPixmap, QImage
from PIL import Image

import sys

# Add project root to path for imports
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.core.config import ConfigManager, AppConfig
from src.core.api_client import OpenRouterClient, APIResponse, ResponseData, ErrorInfo, ErrorLevel
from src.core.image_processor import ImagePreprocessor
from src.bridge.pixelmator import PixelmatorBridge, WriteBackResult, ExportResult
from src.utils.logger import get_logger, init_logger


class ProcessingThread(QThread):
    """Background thread for API processing."""

    progress = Signal(str)  # Progress message
    finished = Signal(bool, str, object)  # Success status, message, result image path

    def __init__(
        self,
        client: OpenRouterClient,
        prompt: str,
        image_path: Path,
        output_path: Path,
        model: str,
        temperature: float,
        compression_quality: int = 85,
        debug_mode: bool = False
    ):
        super().__init__()
        self.client = client
        self.prompt = prompt
        self.image_path = image_path
        self.output_path = output_path
        self.model = model
        self.temperature = temperature
        self.compression_quality = compression_quality
        self.debug_mode = debug_mode

    def _compress_image(self) -> tuple[Path, bool]:
        """Compress image while preserving transparency.

        Returns:
            Tuple of (path to the compressed image file, has_transparency).
        """
        img = Image.open(self.image_path)

        # Detect if image has transparency
        has_transparency = img.mode in ('RGBA', 'LA') or (
            img.mode == 'P' and 'transparency' in img.info
        )

        if has_transparency:
            # Keep PNG format (supports transparency)
            if img.mode == 'P':
                img = img.convert('RGBA')
            elif img.mode == 'LA':
                img = img.convert('RGBA')
            compressed_path = self.output_path.parent / "compressed_input.png"
            img.save(compressed_path, 'PNG', optimize=True)
        else:
            # Use JPEG format (better compression for non-transparent images)
            if img.mode != 'RGB':
                img = img.convert('RGB')
            compressed_path = self.output_path.parent / "compressed_input.jpg"
            img.save(compressed_path, 'JPEG', quality=self.compression_quality)

        return compressed_path, has_transparency

    def _extract_alpha_mask(self) -> Optional[Image.Image]:
        """Extract alpha channel from the original image.

        Returns:
            Alpha channel as a grayscale image, or None if no transparency.
        """
        img = Image.open(self.image_path)

        # Handle different image modes
        if img.mode == 'RGBA':
            return img.split()[3]  # Alpha channel
        elif img.mode == 'LA':
            return img.split()[1]  # Alpha channel
        elif img.mode == 'P' and 'transparency' in img.info:
            img = img.convert('RGBA')
            return img.split()[3]
        else:
            return None

    def _restore_image(
        self,
        generated_path: Path,
        original_size: tuple[int, int],
        alpha_mask: Optional[Image.Image]
    ) -> None:
        """Restore transparency and size of generated image.

        Args:
            generated_path: Path to the AI-generated image
            original_size: Original (width, height) to restore
            alpha_mask: Original alpha channel to restore, or None
        """
        gen = Image.open(generated_path).convert('RGBA')

        # 1. Resize to original dimensions if needed
        if gen.size != original_size:
            gen = gen.resize(original_size, Image.Resampling.LANCZOS)

        # 2. Restore alpha channel if original had transparency
        if alpha_mask is not None:
            gen.putalpha(alpha_mask)

        gen.save(generated_path, 'PNG')

    def _load_mock_response(self) -> APIResponse:
        """Load mock API response from log file for debug mode."""
        import json

        log_path = project_root / "logs" / "1772969294337.json"
        if not log_path.exists():
            return APIResponse(
                success=False,
                error=ErrorInfo(
                    code="E999",
                    level=ErrorLevel.ERROR,
                    message=f"Mock file not found: {log_path}",
                    suggestion="Please ensure the mock log file exists"
                )
            )

        with open(log_path, 'r') as f:
            data = json.load(f)

        # Extract image from response (format: message.images[0]['image_url']['url'])
        choices = data.get('choices', [])
        if choices:
            message = choices[0].get('message', {})
            images = message.get('images', [])
            if images:
                image_url = images[0].get('image_url', {}).get('url', '')
                # Remove data:image/png;base64, prefix
                if image_url.startswith('data:image/'):
                    image_base64 = image_url.split(',', 1)[1]
                    return APIResponse(
                        success=True,
                        data=ResponseData(image_base64=image_base64)
                    )

        return APIResponse(
            success=False,
            error=ErrorInfo(
                code="E999",
                level=ErrorLevel.ERROR,
                message="Mock data invalid: no image found",
                suggestion="Check mock file format"
            )
        )

    def run(self):
        """Run the processing task."""
        try:
            # Get original image dimensions and extract alpha mask
            original_img = Image.open(self.image_path)
            original_size = original_img.size
            alpha_mask = self._extract_alpha_mask()
            original_img.close()

            if alpha_mask is not None:
                self.progress.emit("检测到透明背景，已备份 Alpha 通道...")
            else:
                self.progress.emit("图像无透明背景...")

            self.progress.emit("正在压缩图像...")
            compressed_path, has_transparency = self._compress_image()

            # Log compression result
            original_file_size = self.image_path.stat().st_size
            compressed_file_size = compressed_path.stat().st_size
            reduction = (1 - compressed_file_size / original_file_size) * 100 if original_file_size > 0 else 0
            format_name = "PNG" if has_transparency else "JPEG"
            self.progress.emit(f"压缩完成 ({format_name}): {original_file_size/1024:.1f}KB -> {compressed_file_size/1024:.1f}KB (节省 {reduction:.0f}%)")

            self.progress.emit("正在读取图像...")
            image_base64 = self.client.image_to_base64(compressed_path)

            # Add size constraint to prompt to preserve dimensions
            size_hint = f"\n\n[IMPORTANT: The output image must be exactly {original_size[0]}x{original_size[1]} pixels. Do not change the image dimensions.]"
            enhanced_prompt = self.prompt + size_hint

            self.progress.emit("正在发送到 AI...")

            if self.debug_mode:
                self.progress.emit("[DEBUG] 使用模拟 API 响应...")
                response = self._load_mock_response()
            else:
                response = self.client.process_image(
                    prompt=enhanced_prompt,
                    image_base64=image_base64,
                    model=self.model,
                    temperature=self.temperature
                )

            if response.success and response.data:
                # Check if response contains generated image
                if response.data.image_base64:
                    self.progress.emit("正在保存生成的图像...")
                    self.client.base64_to_image(
                        response.data.image_base64,
                        self.output_path
                    )

                    # Restore transparency and size
                    self.progress.emit("正在恢复透明度和尺寸...")
                    self._restore_image(self.output_path, original_size, alpha_mask)

                    if alpha_mask is not None:
                        self.progress.emit("已恢复透明背景")
                    self.progress.emit(f"图像尺寸: {original_size[0]}x{original_size[1]}")

                    self.finished.emit(True, "图像生成完成", self.output_path)
                else:
                    # Text-only response
                    text = response.data.text or "处理完成（无图像返回）"
                    self.finished.emit(True, text, None)
            else:
                error_msg = response.error.message if response.error else "未知错误"
                self.finished.emit(False, error_msg, None)

        except Exception as e:
            self.finished.emit(False, str(e), None)


class MainWindow(QMainWindow):
    """Main floating control panel window."""

    def __init__(self, config_manager: ConfigManager):
        super().__init__()
        self.config_manager = config_manager
        self.config = config_manager.config
        self.logger = get_logger()

        # Initialize components
        self.bridge = PixelmatorBridge()
        self.preprocessor = ImagePreprocessor(
            max_size=self.config.max_image_size,
            quality=self.config.image_quality
        )
        self.client: Optional[OpenRouterClient] = None
        self.processing_thread: Optional[ProcessingThread] = None

        # Setup UI
        self._setup_ui()
        self._apply_styles()
        self._connect_signals()

    def _setup_ui(self):
        """Setup the user interface."""
        # Window properties
        self.setWindowTitle("Gemini Vision Bridge")
        self.setWindowFlags(Qt.WindowType.Window)
        self.setMinimumSize(900, 600)
        self.resize(1000, 700)

        # Central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # Main horizontal layout (left 2/3, right 1/3)
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)

        # === Left panel (2/3 width) ===
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(10)

        # Layer info group (fixed height with scroll)
        layer_info_group = QGroupBox("图层信息")
        layer_info_layout = QVBoxLayout(layer_info_group)

        layer_scroll = QScrollArea()
        layer_scroll.setWidgetResizable(True)
        layer_scroll.setFixedHeight(150)
        layer_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        layer_scroll.setStyleSheet("QScrollArea { background-color: #1e1e1e; border: none; }")

        self.layer_info_label = QLabel("未导出图层")
        self.layer_info_label.setWordWrap(True)
        self.layer_info_label.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self.layer_info_label.setStyleSheet("padding: 8px; background-color: #1e1e1e; color: #ffffff;")

        layer_scroll.setWidget(self.layer_info_label)
        layer_info_layout.addWidget(layer_scroll)
        left_layout.addWidget(layer_info_group)

        # Image preview group (flexible height)
        preview_group = QGroupBox("图片预览")
        preview_layout = QVBoxLayout(preview_group)

        self.preview_label = QLabel("暂无图片")
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_label.setStyleSheet("background-color: #1e1e1e; color: #888;")
        self.preview_label.setMinimumSize(200, 150)
        self.preview_label.setScaledContents(False)

        preview_layout.addWidget(self.preview_label, 1)  # stretch=1 to take remaining space
        left_layout.addWidget(preview_group, 1)  # stretch=1

        main_layout.addWidget(left_widget, 2)  # stretch=2 (2/3 width)

        # === Right panel (1/3 width) ===
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(10)

        # Status bar at top of right panel
        self.status_label = QLabel("就绪")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setStyleSheet("padding: 5px; background-color: #1e1e1e; border-radius: 3px;")
        right_layout.addWidget(self.status_label)

        # Prompt input
        prompt_group = QGroupBox("指令输入")
        prompt_layout = QVBoxLayout(prompt_group)

        self.prompt_input = QTextEdit()
        self.prompt_input.setPlaceholderText("输入自然语言指令，例如：\n将背景改为赛博朋克风格")
        prompt_layout.addWidget(self.prompt_input)

        right_layout.addWidget(prompt_group)

        # Parameters
        params_group = QGroupBox("参数设置")
        params_layout = QVBoxLayout(params_group)

        # Temperature slider
        temp_layout = QHBoxLayout()
        temp_layout.addWidget(QLabel("Temperature:"))
        self.temp_slider = QSlider(Qt.Orientation.Horizontal)
        self.temp_slider.setRange(0, 100)
        self.temp_slider.setValue(int(self.config.temperature * 100))
        self.temp_label = QLabel(f"{self.config.temperature:.2f}")
        self.temp_slider.valueChanged.connect(
            lambda v: self.temp_label.setText(f"{v/100:.2f}")
        )
        temp_layout.addWidget(self.temp_slider)
        temp_layout.addWidget(self.temp_label)
        params_layout.addLayout(temp_layout)

        # Model selector (from config)
        model_layout = QHBoxLayout()
        model_layout.addWidget(QLabel("模型:"))
        self.model_label = QLabel(self.config.default_model)
        self.model_label.setStyleSheet("color: #888; font-style: italic;")
        model_layout.addWidget(self.model_label)
        model_layout.addStretch()
        params_layout.addLayout(model_layout)

        right_layout.addWidget(params_group)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        right_layout.addWidget(self.progress_bar)

        # Action buttons
        button_layout = QHBoxLayout()

        self.export_btn = QPushButton("导出图层")
        self.process_btn = QPushButton("开始处理")
        self.process_btn.setEnabled(False)
        self.import_btn = QPushButton("导入图层")
        self.import_btn.setEnabled(False)

        button_layout.addWidget(self.export_btn)
        button_layout.addWidget(self.process_btn)
        button_layout.addWidget(self.import_btn)

        right_layout.addLayout(button_layout)

        # Add stretch to push everything up
        right_layout.addStretch()

        main_layout.addWidget(right_widget, 1)  # stretch=1 (1/3 width)

    def _apply_styles(self):
        """Apply QSS styles to the window."""
        self.setStyleSheet("""
            QMainWindow {
                background-color: #2d2d2d;
            }
            QWidget {
                color: #ffffff;
                font-size: 13px;
            }
            QGroupBox {
                border: 1px solid #555;
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 10px;
                font-weight: bold;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
            QTextEdit, QTextBrowser {
                background-color: #1e1e1e;
                border: 1px solid #555;
                border-radius: 5px;
                padding: 5px;
            }
            QPushButton {
                background-color: #0d47a1;
                border: none;
                border-radius: 5px;
                padding: 8px 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #1565c0;
            }
            QPushButton:pressed {
                background-color: #0a3d91;
            }
            QPushButton:disabled {
                background-color: #555;
                color: #888;
            }
            QSlider::groove:horizontal {
                height: 6px;
                background: #555;
                border-radius: 3px;
            }
            QSlider::handle:horizontal {
                background: #0d47a1;
                width: 16px;
                margin: -5px 0;
                border-radius: 8px;
            }
            QComboBox {
                background-color: #1e1e1e;
                border: 1px solid #555;
                border-radius: 5px;
                padding: 5px;
            }
            QComboBox::drop-down {
                border: none;
            }
            QComboBox QAbstractItemView {
                background-color: #2d2d2d;
                selection-background-color: #0d47a1;
            }
            QProgressBar {
                border: 1px solid #555;
                border-radius: 5px;
                text-align: center;
            }
            QProgressBar::chunk {
                background-color: #0d47a1;
                border-radius: 4px;
            }
        """)

    def _connect_signals(self):
        """Connect UI signals to handlers."""
        self.export_btn.clicked.connect(self._on_export)
        self.process_btn.clicked.connect(self._on_process)
        self.import_btn.clicked.connect(self._on_import)

    def _log(self, message: str):
        """Log message to file only (no UI log panel)."""
        self.logger.info(message)

    def _on_export(self):
        """Handle export button click."""
        if not self.bridge.is_running():
            self._log("错误: Pixelmator Pro 未运行")
            self.status_label.setText("错误: Pixelmator Pro 未运行")
            return

        # Get document and layer info first
        doc_info = self.bridge.get_document_info()
        layer_info = self.bridge.get_selected_layer_info()

        if not doc_info:
            self._log("错误: 没有打开的文档")
            self.status_label.setText("错误: 没有打开的文档")
            return

        # Get temp directory
        temp_dir = self.config_manager.get_temp_dir()
        export_path = temp_dir / "layer_export.png"

        self._log("正在导出图层（裁剪透明区域）...")

        # Use the new trimmed export method
        result = self.bridge.export_layer_trimmed(export_path)

        if result.success:
            # Save position info for later import
            self.exported_path = result.path
            self.layer_position = result.original_position
            self.layer_bounds = result.original_bounds

            # Update layer info display with position
            if layer_info:
                info_text = (
                    f"文档: {doc_info.name}\n"
                    f"文档尺寸: {doc_info.width} x {doc_info.height}\n"
                    f"图层名称: {layer_info.name}\n"
                    f"图层索引: {layer_info.index}\n"
                    f"位置: ({result.original_position[0]}, {result.original_position[1]})\n"
                    f"尺寸: {result.trimmed_size[0]} x {result.trimmed_size[1]}\n"
                    f"可见: {'是' if layer_info.visible else '否'}\n"
                    f"锁定: {'是' if layer_info.locked else '否'}"
                )
            else:
                info_text = (
                    f"文档: {doc_info.name}\n"
                    f"位置: ({result.original_position[0]}, {result.original_position[1]})\n"
                    f"尺寸: {result.trimmed_size[0]} x {result.trimmed_size[1]}"
                )

            self.layer_info_label.setText(info_text)
            self._log(f"图层已导出并裁剪: {export_path}")
            self._log(f"原始位置: ({result.original_position[0]}, {result.original_position[1]})")
            self._log(f"裁剪后尺寸: {result.trimmed_size[0]} x {result.trimmed_size[1]}")
            self.status_label.setText("图层已导出（已裁剪透明区域）")
            self.process_btn.setEnabled(True)

            # Show preview
            self._show_preview(export_path)
        else:
            self._log(f"导出失败: {result.error}")
            self.status_label.setText("导出失败")

    def _show_preview(self, image_path: Path):
        """Show image preview in the preview label with auto-scaling."""
        if not image_path.exists():
            self.preview_label.setText("图片加载失败")
            return

        # Load image
        self.original_pixmap = QPixmap(str(image_path))
        if self.original_pixmap.isNull():
            self.preview_label.setText("无法加载图片")
            self.original_pixmap = None
            return

        self._update_preview_scale()
        self._log(f"预览: {self.original_pixmap.width()}x{self.original_pixmap.height()} 像素")

    def _update_preview_scale(self):
        """Update preview image scale to fit available space."""
        if not hasattr(self, 'original_pixmap') or self.original_pixmap is None:
            return

        # Get available size from preview label
        available_size = self.preview_label.size()

        # Scale to fit while maintaining aspect ratio
        scaled_pixmap = self.original_pixmap.scaled(
            available_size,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        )

        self.preview_label.setPixmap(scaled_pixmap)

    def resizeEvent(self, event):
        """Handle window resize to update preview scale."""
        super().resizeEvent(event)
        if hasattr(self, 'original_pixmap') and self.original_pixmap:
            self._update_preview_scale()

    def _on_process(self):
        """Handle process button click."""
        prompt = self.prompt_input.toPlainText().strip()
        if not prompt:
            self._log("请输入指令")
            return

        if not hasattr(self, 'exported_path') or not self.exported_path.exists():
            self._log("请先导出图层")
            return

        if not self.config.api_key:
            self._log("错误: 未配置 API Key")
            return

        # Initialize client
        if not self.client:
            self.client = OpenRouterClient(self.config.api_key)

        # Get parameters
        temperature = self.temp_slider.value() / 100
        model = self.config.default_model

        # Prepare output path
        output_path = self.config_manager.get_temp_dir() / "result.png"

        # Update UI
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)  # Indeterminate
        self.process_btn.setEnabled(False)
        self.export_btn.setEnabled(False)
        self.status_label.setText("处理中...")

        # Start processing thread
        self.processing_thread = ProcessingThread(
            client=self.client,
            prompt=prompt,
            image_path=self.exported_path,
            output_path=output_path,
            model=model,
            temperature=temperature,
            compression_quality=self.config.image_quality,
            debug_mode=self.config.debug_mode
        )
        self.processing_thread.progress.connect(self._on_progress)
        self.processing_thread.finished.connect(self._on_finished)
        self.processing_thread.start()

    def _on_progress(self, message: str):
        """Handle progress update from processing thread."""
        self._log(message)
        self.status_label.setText(message)

    def _on_finished(self, success: bool, message: str, result_path: Optional[Path]):
        """Handle processing completion."""
        self.progress_bar.setVisible(False)
        self.process_btn.setEnabled(True)
        self.export_btn.setEnabled(True)

        if success:
            self._log(f"完成: {message}")
            self.status_label.setText("处理完成")

            # Show result image if available
            if result_path and result_path.exists():
                self.result_path = result_path
                self._show_preview(result_path)
                self.import_btn.setEnabled(True)
                self._log("图像已生成，点击'导入图层'写入 Pixelmator")
        else:
            self._log(f"错误: {message}")
            self.status_label.setText(f"错误: {message}")

    def _on_import(self):
        """Handle import button click - import result image back to Pixelmator."""
        if not hasattr(self, 'result_path') or not self.result_path.exists():
            self._log("错误: 没有可导入的图像")
            return

        if not hasattr(self, 'layer_position'):
            self._log("错误: 缺少图层位置信息")
            return

        if not self.bridge.is_running():
            self._log("错误: Pixelmator Pro 未运行")
            self.status_label.setText("错误: Pixelmator Pro 未运行")
            return

        self._log("正在导入图层到 Pixelmator...")
        result = self.bridge.import_layer(self.result_path, self.layer_position)

        if result.success:
            self._log(f"导入成功: {result.layer_name}")
            self.status_label.setText(f"已导入: {result.layer_name}")
            self.import_btn.setEnabled(False)
        else:
            self._log(f"导入失败: {result.error}")
            self.status_label.setText(f"导入失败")


def main():
    """Application entry point."""
    # Initialize logger
    log_dir = project_root / "logs"
    init_logger(log_dir)
    logger = get_logger()

    # Initialize config
    config_manager = ConfigManager(project_root)
    config_manager.load()

    # Create application
    app = QApplication(sys.argv)
    app.setApplicationName("Gemini Vision Bridge")
    app.setApplicationVersion("0.1.0")

    # Create and show window
    window = MainWindow(config_manager)
    window.show()

    logger.info("Application started")

    sys.exit(app.exec())


if __name__ == "__main__":
    main()