"""
OpenRouter API client module.
Handles communication with OpenRouter API for Gemini models.
"""

import base64
import json
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, List
from pathlib import Path

from openai import OpenAI


class ErrorLevel(Enum):
    """Error severity levels."""
    CRITICAL = "critical"
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


@dataclass
class ErrorInfo:
    """Error information structure."""
    code: str
    level: ErrorLevel
    message: str
    suggestion: str
    retryable: bool = False


# Error code definitions
ERROR_CODES = {
    "E001": ErrorInfo("E001", ErrorLevel.CRITICAL, "Pixelmator Pro 未运行", "请先启动 Pixelmator Pro", False),
    "E002": ErrorInfo("E002", ErrorLevel.CRITICAL, "无访问权限", "请在系统偏好设置中授权", False),
    "E003": ErrorInfo("E003", ErrorLevel.ERROR, "API Key 无效", "请检查 API Key 配置", False),
    "E004": ErrorInfo("E004", ErrorLevel.ERROR, "API 配额已耗尽", "请升级套餐或等待配额重置", True),
    "E005": ErrorInfo("E005", ErrorLevel.WARNING, "网络连接超时", "请检查网络连接后重试", True),
    "E006": ErrorInfo("E006", ErrorLevel.WARNING, "图像尺寸过大", "已自动缩放处理", False),
    "E007": ErrorInfo("E007", ErrorLevel.INFO, "未选中图层", "请在 Pixelmator 中选择要处理的图层", False),
}


@dataclass
class ContentPart:
    """Content part for multimodal messages."""
    type: str  # "text" or "image_url"
    text: Optional[str] = None
    image_url: Optional[dict] = None


@dataclass
class Message:
    """Chat message structure."""
    role: str  # "system", "user", "assistant"
    content: List[ContentPart]


@dataclass
class APIRequest:
    """API request structure."""
    model: str
    messages: List[Message]
    temperature: float = 0.7
    max_tokens: int = 4096


@dataclass
class ResponseData:
    """Response data from API."""
    text: Optional[str] = None
    image_base64: Optional[str] = None
    image_format: str = "png"


@dataclass
class UsageInfo:
    """Token usage information."""
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


@dataclass
class APIResponse:
    """API response structure."""
    success: bool
    data: Optional[ResponseData] = None
    error: Optional[ErrorInfo] = None
    usage: Optional[UsageInfo] = None


class OpenRouterClient:
    """OpenRouter API client for Gemini models."""

    BASE_URL = "https://openrouter.ai/api/v1"

    def __init__(self, api_key: str, log_dir: Optional[Path] = None):
        self.client = OpenAI(
            base_url=self.BASE_URL,
            api_key=api_key,
        )
        self.log_dir = log_dir or Path(__file__).parent.parent.parent / "logs"

    def _save_response(self, response_data: dict) -> None:
        """Save API response to a JSON file with millisecond timestamp."""
        timestamp = int(time.time() * 1000)
        filename = f"{timestamp}.json"
        filepath = self.log_dir / filename

        self.log_dir.mkdir(parents=True, exist_ok=True)

        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(response_data, f, ensure_ascii=False, indent=2)

    def _build_messages(self, prompt: str, image_base64: Optional[str] = None) -> list:
        """Build message list for API request."""
        content = []

        # Add text prompt
        content.append({
            "type": "text",
            "text": prompt
        })

        # Add image if provided
        if image_base64:
            content.append({
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/png;base64,{image_base64}"
                }
            })

        return [{"role": "user", "content": content}]

    def process_image(
        self,
        prompt: str,
        image_base64: Optional[str] = None,
        model: str = "google/gemini-3-pro-image-preview",
        temperature: float = 0.7,
        max_tokens: int = 4096
    ) -> APIResponse:
        """Process image with AI model."""
        try:
            messages = self._build_messages(prompt, image_base64)

            response = self.client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                extra_body={"modalities": ["image", "text"]}
            )

            # Save raw response to JSON file
            response_dict = response.model_dump()
            self._save_response(response_dict)

            # Extract response text
            message = response.choices[0].message
            text = message.content if response.choices else None

            # Extract generated image if present
            image_base64_result = None
            if hasattr(message, 'images') and message.images:
                # Image URL format: data:image/png;base64,<base64_data>
                image_url = message.images[0]['image_url']['url']
                if image_url.startswith('data:image/'):
                    # Extract base64 part after the comma
                    image_base64_result = image_url.split(',', 1)[1]

            # Build usage info
            usage = None
            if response.usage:
                usage = UsageInfo(
                    prompt_tokens=response.usage.prompt_tokens,
                    completion_tokens=response.usage.completion_tokens,
                    total_tokens=response.usage.total_tokens
                )

            return APIResponse(
                success=True,
                data=ResponseData(text=text, image_base64=image_base64_result),
                usage=usage
            )

        except Exception as e:
            error_msg = str(e).lower()

            # Map errors to error codes
            if "api key" in error_msg or "unauthorized" in error_msg:
                error = ERROR_CODES["E003"]
            elif "quota" in error_msg or "rate limit" in error_msg:
                error = ERROR_CODES["E004"]
            elif "timeout" in error_msg or "connection" in error_msg:
                error = ERROR_CODES["E005"]
            else:
                error = ErrorInfo(
                    code="E999",
                    level=ErrorLevel.ERROR,
                    message=str(e),
                    suggestion="请检查错误信息并重试",
                    retryable=False
                )

            return APIResponse(success=False, error=error)

    @staticmethod
    def image_to_base64(image_path: Path) -> str:
        """Convert image file to base64 string."""
        with open(image_path, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")

    @staticmethod
    def base64_to_image(base64_data: str, output_path: Path) -> None:
        """Save base64 image data to file."""
        image_data = base64.b64decode(base64_data)
        with open(output_path, "wb") as f:
            f.write(image_data)