"""
阿里百炼（通义）图片生成

支持：
- qwen-image 系列：OpenAI 兼容同步接口（compatible-mode/v1/images/generations）
- wanx 万相系列：DashScope 异步任务接口（旧版协议，官方仍维护）
"""

import asyncio
import logging
from typing import List, Optional

import httpx

from ..base import ImageGeneratorBase, ImageGenerationResult

logger = logging.getLogger(__name__)


class QwenImageGenerator(ImageGeneratorBase):
    """
    阿里百炼图片生成器

    支持模型：
    - qwen-image-3.0-pro / qwen-image-3.0（OpenAI 兼容）
    - wanx2.1-t2i-turbo / wanx2.1-t2i-plus（DashScope 异步任务）
    """

    provider_name = "qwen"

    SUPPORTED_SIZES = ["1024x1024", "720x1280", "1280x720"]

    # DashScope 旧版异步接口域名
    LEGACY_BASE_URL = "https://dashscope.aliyuncs.com/api/v1"

    def __init__(
        self,
        api_key: str,
        api_base: Optional[str] = None,
        default_model: Optional[str] = "qwen-image-3.0",
        **kwargs
    ):
        super().__init__(api_key, api_base, default_model, **kwargs)
        self.base_url = api_base or "https://dashscope.aliyuncs.com/compatible-mode/v1"

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
        """生成图片"""
        model = model or self.default_model

        # wanx 系列走 DashScope 旧版异步任务接口
        if model.startswith("wanx"):
            return await self._generate_wanx_async(
                prompt=prompt,
                negative_prompt=negative_prompt,
                size=size,
                style=style,
                n=n,
                model=model,
            )
        # qwen-image 等走 OpenAI 兼容同步接口
        return await self._generate_openai_compatible(
            prompt=prompt, size=size, n=n, model=model
        )

    async def _generate_openai_compatible(
        self,
        prompt: str,
        size: str,
        n: int,
        model: str,
    ) -> ImageGenerationResult:
        """OpenAI 兼容同步文生图：POST /images/generations"""
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
                for item in data.get("data", []):
                    if item.get("url"):
                        images.append(item["url"])
                    elif item.get("b64_json"):
                        images.append(item["b64_json"])

                if not images:
                    return ImageGenerationResult.fail(
                        "未获取到图片", self.provider_name
                    )
                return ImageGenerationResult.ok(
                    images=images,
                    model=model,
                    provider=self.provider_name,
                    is_base64=("b64_json" in str(data.get("data", [{}])[0]) if data.get("data") else False),
                )
        except httpx.TimeoutException:
            return ImageGenerationResult.fail("请求超时", self.provider_name)
        except Exception as e:
            logger.error(f"Qwen image generation error: {e}", exc_info=True)
            return ImageGenerationResult.fail(str(e), self.provider_name)

    async def _generate_wanx_async(
        self,
        prompt: str,
        negative_prompt: Optional[str],
        size: str,
        style: Optional[str],
        n: int,
        model: str,
    ) -> ImageGenerationResult:
        """DashScope 旧版异步任务模式（wanx 系列）"""
        width, height = self.parse_size(size)
        try:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "X-DashScope-Async": "enable",
            }
            payload = {
                "model": model,
                "input": {"prompt": prompt},
                "parameters": {"size": f"{width}*{height}", "n": min(n, 4)},
            }
            if negative_prompt:
                payload["input"]["negative_prompt"] = negative_prompt
            if style:
                payload["parameters"]["style"] = style

            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.LEGACY_BASE_URL}/services/aigc/text2image/image-synthesis",
                    headers=headers,
                    json=payload,
                )
                if response.status_code != 200:
                    return self._error_from_response(response)

                data = response.json()
                task_id = data.get("output", {}).get("task_id")
                if not task_id:
                    return ImageGenerationResult.fail(
                        "未获取到任务ID", self.provider_name
                    )
                return await self._poll_wanx_task(task_id, model)
        except httpx.TimeoutException:
            return ImageGenerationResult.fail("请求超时", self.provider_name)
        except Exception as e:
            logger.error(f"Qwen wanx image generation error: {e}", exc_info=True)
            return ImageGenerationResult.fail(str(e), self.provider_name)

    async def _poll_wanx_task(
        self,
        task_id: str,
        model: str,
        max_attempts: int = 60,
        interval: float = 2.0,
    ) -> ImageGenerationResult:
        """轮询 DashScope 异步任务"""
        headers = {"Authorization": f"Bearer {self.api_key}"}
        async with httpx.AsyncClient(timeout=30.0) as client:
            for _ in range(max_attempts):
                response = await client.get(
                    f"{self.LEGACY_BASE_URL}/tasks/{task_id}", headers=headers
                )
                if response.status_code == 200:
                    data = response.json()
                    status = data.get("output", {}).get("task_status")
                    if status == "SUCCEEDED":
                        images = [
                            r.get("url")
                            for r in data.get("output", {}).get("results", [])
                            if r.get("url")
                        ]
                        return ImageGenerationResult.ok(
                            images=images, model=model, provider=self.provider_name
                        )
                    if status == "FAILED":
                        return ImageGenerationResult.fail(
                            data.get("output", {}).get("message", "任务失败"),
                            self.provider_name,
                        )
                await asyncio.sleep(interval)
        return ImageGenerationResult.fail("任务超时", self.provider_name)

    def get_supported_sizes(self) -> List[str]:
        return self.SUPPORTED_SIZES

    def get_supported_models(self) -> List[str]:
        return [
            "qwen-image-3.0-pro",
            "qwen-image-3.0",
            "wanx2.1-t2i-turbo",
            "wanx2.1-t2i-plus",
        ]

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
            f"通义 API 错误: {error_msg}", "qwen"
        )
