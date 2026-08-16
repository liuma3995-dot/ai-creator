"""
ModelScope 图片生成（OpenAI 兼容 + 异步任务）

官方流程：POST /v1/images/generations 加 X-ModelScope-Async-Mode: true
→ 返回 task_id → GET /v1/tasks/{task_id} 轮询 → SUCCEED 取图。
"""

import asyncio
import base64
import logging
from typing import List, Optional

import httpx

from ..base import ImageGeneratorBase, ImageGenerationResult

logger = logging.getLogger(__name__)


class ModelScopeImageGenerator(ImageGeneratorBase):
    """
    ModelScope 图片生成器（OpenAI 兼容异步）
    """

    provider_name = "modelscope"

    SUPPORTED_MODELS = [
        "Tongyi-MAI/Z-Image-Turbo",
        "stabilityai/stable-diffusion-xl-base-1.0",
    ]

    def __init__(
        self,
        api_key: str,
        api_base: Optional[str] = None,
        default_model: Optional[str] = "Tongyi-MAI/Z-Image-Turbo",
        **kwargs
    ):
        super().__init__(api_key, api_base, default_model, **kwargs)
        self.base_url = api_base or "https://api-inference.modelscope.cn/v1"

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
        """生成图片（异步任务模式）"""
        model = model or self.default_model
        full_prompt = f"{prompt}, {style} style" if style else prompt

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "X-ModelScope-Async-Mode": "true",
        }
        payload = {
            "model": model,
            "prompt": full_prompt,
            "size": size,
            "n": min(n, 4),
        }

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    f"{self.base_url}/images/generations",
                    headers=headers,
                    json=payload,
                )
                if response.status_code == 503:
                    logger.info(f"ModelScope 模型 {model} 加载中，等待重试...")
                    await asyncio.sleep(15)
                    response = await client.post(
                        f"{self.base_url}/images/generations",
                        headers=headers,
                        json=payload,
                    )
                if response.status_code != 200:
                    return self._error_from_response(response)

                data = response.json()
                task_id = data.get("output", {}).get("task_id")
                if not task_id:
                    # 某些模型可能同步返回图片
                    images = self._extract_images(data)
                    if images:
                        return ImageGenerationResult.ok(
                            images=images,
                            model=model,
                            provider=self.provider_name,
                            is_base64=True,
                        )
                    return ImageGenerationResult.fail(
                        "未获取到任务ID", self.provider_name
                    )

                return await self._poll_task(task_id, model)
        except httpx.TimeoutException:
            return ImageGenerationResult.fail("请求超时", self.provider_name)
        except Exception as e:
            logger.error(f"ModelScope image generation error: {e}", exc_info=True)
            return ImageGenerationResult.fail(str(e), self.provider_name)

    async def _poll_task(
        self, task_id: str, model: str, max_attempts: int = 90, interval: float = 2.0
    ) -> ImageGenerationResult:
        """轮询异步任务"""
        headers = {"Authorization": f"Bearer {self.api_key}"}
        async with httpx.AsyncClient(timeout=30.0) as client:
            for _ in range(max_attempts):
                response = await client.get(
                    f"{self.base_url}/tasks/{task_id}", headers=headers
                )
                if response.status_code == 200:
                    data = response.json()
                    status = data.get("output", {}).get("task_status")
                    if status in ("SUCCEED", "SUCCEEDED"):
                        images = self._extract_images(data)
                        if images:
                            return ImageGenerationResult.ok(
                                images=images,
                                model=model,
                                provider=self.provider_name,
                                is_base64=True,
                            )
                        return ImageGenerationResult.fail(
                            "任务成功但未获取到图片", self.provider_name
                        )
                    if status in ("FAILED", "FAIL"):
                        return ImageGenerationResult.fail(
                            data.get("output", {}).get("message", "任务失败"),
                            self.provider_name,
                        )
                await asyncio.sleep(interval)
        return ImageGenerationResult.fail("任务超时", self.provider_name)

    @staticmethod
    def _extract_images(data: dict) -> List[str]:
        """从任务结果中提取图片（url 或 base64）"""
        output = data.get("output", data)
        images = []
        if isinstance(output, dict):
            results = output.get("results") or output.get("images") or []
            for r in results:
                if isinstance(r, dict):
                    if r.get("url"):
                        images.append(r["url"])
                    elif r.get("b64_json"):
                        images.append(r["b64_json"])
                    elif r.get("image"):
                        images.append(r["image"])
                elif isinstance(r, str):
                    images.append(r)
            for key in ("image_url", "generated_image"):
                if output.get(key):
                    images.append(output[key])
        elif isinstance(output, list):
            images = [i for i in output if isinstance(i, str)]
        return images

    def get_supported_sizes(self) -> List[str]:
        return ["512x512", "768x768", "1024x1024", "1024x768", "768x1024"]

    def get_supported_models(self) -> List[str]:
        return self.SUPPORTED_MODELS

    @staticmethod
    def _error_from_response(response: httpx.Response) -> ImageGenerationResult:
        try:
            data = response.json()
            error_msg = (
                data.get("error", {}).get("message")
                or data.get("message")
                or str(response.status_code)
            )
        except Exception:
            error_msg = response.text or str(response.status_code)
        return ImageGenerationResult.fail(
            f"ModelScope API 错误: {error_msg}", "modelscope"
        )
