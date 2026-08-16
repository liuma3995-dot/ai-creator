"""
MiniMax 视频生成（2026 新平台协议）

支持模型：
- MiniMax-Hailuo-2.3 / MiniMax-Hailuo-2.3-Fast / MiniMax-Hailuo-02（文生视频）
- I2V-01 / I2V-01-live / I2V-01-Director（图生视频）

协议（Base URL 取自用户模型配置，如 https://api.minimaxi.com/v1）：
1. POST {base}/video_generation        提交任务，返回 task_id
2. GET  {base}/query/video_generation  轮询状态，Success 时返回 file_id
3. GET  {base}/files/retrieve          凭 file_id 获取临时下载地址
"""

import asyncio
import logging
from typing import List, Optional, Tuple, Any

import httpx

from ..base import VideoGeneratorBase, VideoGenerationResult, VideoGenerationMode

logger = logging.getLogger(__name__)


class MiniMaxVideoGenerator(VideoGeneratorBase):
    """
    MiniMax 视频生成器（新版开放平台）

    - 无需 group_id，使用 Bearer API Key
    - 异步任务模式：提交 -> 轮询 -> 取文件下载地址
    - 支持文生视频和图生视频
    """

    provider_name = "minimax"

    supported_modes = [
        VideoGenerationMode.TEXT_TO_VIDEO,
        VideoGenerationMode.IMAGE_TO_VIDEO,
    ]

    # 官方支持的分辨率与时长
    SUPPORTED_RESOLUTIONS = ["512P", "720P", "768P", "1080P"]
    SUPPORTED_DURATIONS = [6, 10]

    def __init__(
        self,
        api_key: str,
        api_base: Optional[str] = None,
        default_model: Optional[str] = "MiniMax-Hailuo-2.3",
        **kwargs
    ):
        super().__init__(api_key, api_base, default_model, **kwargs)
        self.base_url = (api_base or "https://api.minimaxi.com/v1").rstrip("/")

    async def generate(
        self,
        prompt: str,
        image_url: Optional[str] = None,
        size: str = "1280x720",
        duration: float = 6.0,
        fps: int = 24,
        style: Optional[str] = None,
        model: Optional[str] = None,
        **kwargs
    ) -> VideoGenerationResult:
        """生成视频（异步任务模式，内部轮询到完成）"""
        model = model or self.default_model
        resolution = kwargs.get("resolution") or "768P"

        # 时长/分辨率按官方约束收敛
        duration_sec = self._normalize_duration(duration)
        resolution = self._normalize_resolution(resolution)

        try:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            }

            payload = {
                "model": model,
                "prompt": prompt,
                "duration": duration_sec,
                "resolution": resolution,
            }

            if image_url:
                payload["first_frame_image"] = image_url

            async with httpx.AsyncClient(timeout=60.0) as client:
                # 1. 提交任务
                response = await client.post(
                    f"{self.base_url}/video_generation",
                    headers=headers,
                    json=payload,
                )

                if response.status_code != 200:
                    return self._error_from_response(
                        response, default_msg=f"HTTP {response.status_code}"
                    )

                data = response.json()
                base_resp = data.get("base_resp") or {}
                if base_resp.get("status_code") not in (0, None):
                    return VideoGenerationResult.fail(
                        base_resp.get("status_msg", "未知错误"),
                        self.provider_name,
                    )

                task_id = data.get("task_id")
                if not task_id:
                    return VideoGenerationResult.fail(
                        "未获取到任务ID", self.provider_name
                    )

                # 2. 轮询到完成（简单版：后台任务内自行轮询）
                return await self._poll_task_result(
                    task_id,
                    self._check_task_status,
                    max_attempts=120,
                    interval=5.0,
                )

        except httpx.TimeoutException:
            return VideoGenerationResult.fail("请求超时", self.provider_name)
        except Exception as e:
            logger.error(f"MiniMax video generation error: {e}", exc_info=True)
            return VideoGenerationResult.fail(str(e), self.provider_name)

    async def _check_task_status(
        self, task_id: str
    ) -> Tuple[bool, Optional[VideoGenerationResult], Optional[str]]:
        """查询任务状态；Success 时再取文件下载地址"""
        headers = {"Authorization": f"Bearer {self.api_key}"}

        async with httpx.AsyncClient(timeout=30.0) as client:
            # 2. 查询任务状态
            response = await client.get(
                f"{self.base_url}/query/video_generation",
                params={"task_id": task_id},
                headers=headers,
            )

            if response.status_code != 200:
                return False, None, None

            data = response.json()
            base_resp = data.get("base_resp") or {}
            if base_resp.get("status_code") not in (0, None):
                return True, None, base_resp.get("status_msg", "未知错误")

            status = (data.get("status") or "").lower()

            if status == "success":
                file_id = data.get("file_id")
                if not file_id:
                    return True, None, "任务成功但未返回 file_id"

                # 3. 获取视频下载地址
                download_url = await self._retrieve_file_url(file_id)
                if not download_url:
                    return True, None, "获取视频下载地址失败"

                result = VideoGenerationResult.ok(
                    videos=[download_url],
                    model=self.default_model,
                    provider=self.provider_name,
                    task_id=task_id,
                    file_id=file_id,
                )
                return True, result, None

            if status == "fail":
                return True, None, "视频生成失败"

            # Preparing / Queueing / Processing / 未知状态 -> 继续轮询
            return False, None, None

    async def _retrieve_file_url(self, file_id: str) -> Optional[str]:
        """凭 file_id 获取临时下载地址"""
        headers = {"Authorization": f"Bearer {self.api_key}"}

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    f"{self.base_url}/files/retrieve",
                    params={"file_id": file_id},
                    headers=headers,
                )
                if response.status_code != 200:
                    logger.warning(
                        f"MiniMax files/retrieve failed: HTTP {response.status_code}: {response.text[:200]}"
                    )
                    return None

                data = response.json()
                # 兼容多种响应形态
                for key in ("download_url", "file_url", "url"):
                    if data.get(key):
                        return data[key]
                file_obj = data.get("file") or {}
                for key in ("download_url", "file_url", "url"):
                    if file_obj.get(key):
                        return file_obj[key]
                return None
        except Exception as e:
            logger.error(f"MiniMax files/retrieve error: {e}", exc_info=True)
            return None

    async def check_task_status(self, task_id: str) -> VideoGenerationResult:
        """检查任务状态（公开方法）"""
        try:
            is_done, result, error = await self._check_task_status(task_id)
            if error:
                return VideoGenerationResult.fail(error, self.provider_name)
            if is_done and result:
                return result
            return VideoGenerationResult.pending(task_id, self.provider_name)
        except Exception as e:
            return VideoGenerationResult.fail(str(e), self.provider_name)

    def get_supported_sizes(self) -> List[str]:
        return self.SUPPORTED_RESOLUTIONS

    def get_supported_models(self) -> List[str]:
        return [
            "MiniMax-Hailuo-2.3",
            "MiniMax-Hailuo-2.3-Fast",
            "MiniMax-Hailuo-02",
            "T2V-01",
            "I2V-01",
            "I2V-01-live",
            "I2V-01-Director",
        ]

    @staticmethod
    def _normalize_duration(duration: float) -> int:
        """时长收敛到官方允许值 {6, 10}"""
        value = int(round(float(duration)))
        return 10 if value >= 10 else 6

    @staticmethod
    def _normalize_resolution(resolution: str) -> str:
        """分辨率收敛到官方允许值"""
        value = (resolution or "").upper()
        if value not in MiniMaxVideoGenerator.SUPPORTED_RESOLUTIONS:
            return "768P"
        return value

    @staticmethod
    def _error_from_response(
        response: httpx.Response, default_msg: str = "MiniMax API 错误"
    ) -> VideoGenerationResult:
        """从非 200 响应中提取错误信息"""
        try:
            data = response.json()
            error_msg = (
                data.get("base_resp", {}).get("status_msg")
                or data.get("error", {}).get("message")
                or data.get("message")
                or response.text
                or default_msg
            )
        except Exception:
            error_msg = response.text or default_msg
        return VideoGenerationResult.fail(f"MiniMax API 错误: {error_msg}", "minimax")
