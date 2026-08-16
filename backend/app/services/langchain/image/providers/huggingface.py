"""
Hugging Face 图片生成（Inference API）

说明：HF Router 的 OpenAI 兼容端点（router.huggingface.co/v1）仅支持 chat，
图片生成需走专用 Inference API（api-inference.huggingface.co/models/{model}）。
"""

import asyncio
import base64
import logging
from typing import List, Optional

import httpx

from ..base import ImageGeneratorBase, ImageGenerationResult

logger = logging.getLogger(__name__)


class HuggingFaceImageGenerator(ImageGeneratorBase):
    """
    Hugging Face 图片生成器（Inference API）

    支持模型：
    - stabilityai/stable-diffusion-xl-base-1.0
    - stabilityai/sdxl-turbo
    - black-forest-labs/FLUX.1-schnell
    """

    provider_name = "huggingface"

    SUPPORTED_MODELS = [
        "stabilityai/stable-diffusion-xl-base-1.0",
        "stabilityai/sdxl-turbo",
        "black-forest-labs/FLUX.1-schnell",
    ]

    MODEL_SIZES = {
        "stabilityai/stable-diffusion-xl-base-1.0": ["1024x1024", "1024x768", "768x1024"],
        "stabilityai/sdxl-turbo": ["1024x1024", "512x512"],
        "black-forest-labs/FLUX.1-schnell": ["1024x1024", "768x768"],
    }

    # Inference API 端点（非 OpenAI 兼容 router）
    INFERENCE_BASE_URL = "https://api-inference.huggingface.co/models"

    def __init__(
        self,
        api_key: str,
        api_base: Optional[str] = None,
        default_model: Optional[str] = "stabilityai/stable-diffusion-xl-base-1.0",
        **kwargs
    ):
        super().__init__(api_key, api_base, default_model, **kwargs)
        self.base_url = api_base or self.INFERENCE_BASE_URL

    async def generate(
        self,
        prompt: str,
        negative_prompt: Optional[str] = None,
        size: str = "1024x1024",
        quality: str = "standard",
        style: Optional[str] = None,
        n: int = 1,
        model: Optional[str] = None,
        **kwargs
    ) -> ImageGenerationResult:
        """生成图片（Inference API 直调，返回二进制图）"""
        model = model or self.default_model
        full_prompt = f"{prompt}, {style} style" if style else prompt

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {"inputs": full_prompt}

        images = []
        try:
            async with httpx.AsyncClient(timeout=180.0) as client:
                for i in range(min(n, 4)):
                    response = await client.post(
                        f"{self.base_url}/{model}",
                        headers=headers,
                        json=payload,
                    )
                    if response.status_code == 503:
                        # 模型冷启动中，等待后重试一次
                        logger.info(f"HF 模型 {model} 加载中，等待重试...")
                        await asyncio.sleep(15)
                        response = await client.post(
                            f"{self.base_url}/{model}",
                            headers=headers,
                            json=payload,
                        )

                    if response.status_code != 200:
                        logger.warning(f"HF 第 {i+1} 次生成失败: HTTP {response.status_code}: {response.text[:200]}")
                        continue

                    content_type = response.headers.get("content-type", "")
                    if "image" in content_type:
                        img_b64 = base64.b64encode(response.content).decode("utf-8")
                        images.append(f"data:{content_type};base64,{img_b64}")
                    else:
                        # 部分模型返回 JSON（如 FLUX 输出 url/base64）
                        try:
                            data = response.json()
                            if isinstance(data, dict) and data.get("url"):
                                images.append(data["url"])
                            elif isinstance(data, dict) and data.get("b64_json"):
                                images.append(data["b64_json"])
                        except Exception:
                            img_b64 = base64.b64encode(response.content).decode("utf-8")
                            images.append(img_b64)

            if images:
                return ImageGenerationResult.ok(
                    images=images,
                    model=model,
                    provider=self.provider_name,
                    is_base64=True,
                )
            return ImageGenerationResult.fail(
                f"未能生成图片：模型 {model} 可能不支持图片生成或 API 调用失败",
                self.provider_name,
            )
        except httpx.TimeoutException:
            return ImageGenerationResult.fail("请求超时", self.provider_name)
        except Exception as e:
            logger.error(f"Hugging Face image generation error: {e}", exc_info=True)
            return ImageGenerationResult.fail(str(e), self.provider_name)

    def get_supported_sizes(self) -> List[str]:
        return ["512x512", "768x768", "1024x1024", "1024x768", "768x1024"]

    def get_supported_models(self) -> List[str]:
        return self.SUPPORTED_MODELS
