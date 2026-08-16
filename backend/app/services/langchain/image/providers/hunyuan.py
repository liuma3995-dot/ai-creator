"""
腾讯混元图片生成（OpenAI 兼容协议）

2026 混元生图 API 兼容 OpenAI 接口规范，单 API Key（TokenHub/混元控制台 Key），
旧腾讯云 Action 协议（SecretId/SecretKey + TC3 签名）已废弃。
"""

import logging
from typing import List, Optional

import httpx

from ..base import ImageGeneratorBase, ImageGenerationResult

logger = logging.getLogger(__name__)


class HunyuanImageGenerator(ImageGeneratorBase):
    """
    腾讯混元图片生成器（OpenAI 兼容）
    """

    provider_name = "hunyuan"

    SUPPORTED_SIZES = ["1024x1024", "768x1024", "1024x768"]

    def __init__(
        self,
        api_key: str,
        api_base: Optional[str] = None,
        default_model: Optional[str] = "hunyuan-image-latest",
        **kwargs
    ):
        super().__init__(api_key, api_base, default_model, **kwargs)
        self.base_url = api_base or "https://api.hunyuan.cloud.tencent.com/v1"

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
        """生成图片（OpenAI 兼容）"""
        model = model or self.default_model

        try:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            }
            payload = {
                "model": model,
                "prompt": prompt,
                "size": size,
                "n": min(n, 4),
            }

            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(
                    f"{self.base_url}/images/generations",
                    headers=headers,
                    json=payload,
                )

                if response.status_code != 200:
                    return self._error_from_response(response)

                data = response.json()
                images = []
                is_base64 = False
                for item in data.get("data", []):
                    if item.get("url"):
                        images.append(item["url"])
                    elif item.get("b64_json"):
                        images.append(item["b64_json"])
                        is_base64 = True

                if not images:
                    return ImageGenerationResult.fail(
                        "未获取到图片", self.provider_name
                    )
                return ImageGenerationResult.ok(
                    images=images,
                    model=model,
                    provider=self.provider_name,
                    is_base64=is_base64,
                )

        except httpx.TimeoutException:
            return ImageGenerationResult.fail("请求超时", self.provider_name)
        except Exception as e:
            logger.error(f"Hunyuan image generation error: {e}", exc_info=True)
            return ImageGenerationResult.fail(str(e), self.provider_name)

    def get_supported_sizes(self) -> List[str]:
        return self.SUPPORTED_SIZES

    def get_supported_models(self) -> List[str]:
        return ["hunyuan-image-latest", "hunyuan-image"]

    @staticmethod
    def _error_from_response(response: httpx.Response) -> ImageGenerationResult:
        try:
            data = response.json()
            error_msg = (
                data.get("error", {}).get("message")
                or data.get("message")
                or data.get("code", str(response.status_code))
            )
        except Exception:
            error_msg = response.text or str(response.status_code)
        return ImageGenerationResult.fail(
            f"混元 API 错误: {error_msg}", "hunyuan"
        )
