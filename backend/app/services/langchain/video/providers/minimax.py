"""
MiniMax 视频生成（2026 新平台协议）

支持模型：
- MiniMax-Hailuo-2.3 / MiniMax-Hailuo-2.3-Fast / MiniMax-Hailuo-02（v1 协议，文生视频）
- I2V-01 / I2V-01-live / I2V-01-Director（图生视频）
- MiniMax-H3（v2 协议：content 多模态数组，支持文生视频/图生视频/多模态参考）

v1 协议（Hailuo 系列，Base URL 如 https://api.minimaxi.com）：
1. POST {host}/v1/video_generation        提交任务，返回 task_id
2. GET  {host}/v1/query/video_generation  轮询状态，Success 时返回 file_id
3. GET  {host}/v1/files/retrieve          凭 file_id 获取临时下载地址

v2 协议（MiniMax-H3，2026 新接口）：
1. POST {host}/v2/video_generation
   body: {"model": "MiniMax-H3", "content": [{"type": "text", "text": ...}],
          "resolution": "768P|2K", "duration": 4~15, "ratio": "16:9|...|adaptive"}
   返回 {"task_id": "..."}
2. GET  {host}/v2/query/video_generation/{task_id}  轮询状态
   succeeded 时 task.content.url 即最终视频地址（无需 files/retrieve）
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

    # v1（Hailuo）官方支持的分辨率与时长
    SUPPORTED_RESOLUTIONS = ["512P", "720P", "768P", "1080P"]
    SUPPORTED_DURATIONS = [6, 10]
    # v2（MiniMax-H3）官方支持的分辨率与时长
    V2_SUPPORTED_RESOLUTIONS = ["768P", "2K"]
    V2_DURATION_RANGE = (4, 15)
    # 走 v2 协议的模型前缀
    V2_MODEL_PREFIXES = ("MiniMax-H3",)

    def __init__(
        self,
        api_key: str,
        api_base: Optional[str] = None,
        default_model: Optional[str] = "MiniMax-Hailuo-2.3",
        **kwargs
    ):
        super().__init__(api_key, api_base, default_model, **kwargs)
        # 容错：用户模型配置里可能把完整接口路径误存为 base_url
        # （如 https://api.minimaxi.com/v2/video_generation），统一归一化到 协议+主机。
        self.base_url = self._normalize_api_base(api_base or "https://api.minimaxi.com")

    @staticmethod
    def _normalize_api_base(api_base: str) -> str:
        """提取协议+主机（忽略误存的路径后缀）"""
        base = str(api_base or "").strip().rstrip("/")
        if not base:
            return "https://api.minimaxi.com"
        lowered = base.lower()
        for suffix in (
            "/v2/video_generation",
            "/v1/video_generation",
            "/video_generation",
            "/v2",
            "/v1",
        ):
            if lowered.endswith(suffix):
                base = base[: -len(suffix)].rstrip("/")
                break
        return base

    def _uses_v2_protocol(self, model: Optional[str]) -> bool:
        """MiniMax-H3 系列走 v2 协议"""
        return bool(model) and str(model).startswith(self.V2_MODEL_PREFIXES)

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
        is_v2 = self._uses_v2_protocol(model)
        resolution = kwargs.get("resolution") or "768P"

        # 时长/分辨率按官方约束收敛
        duration_sec = (
            self._normalize_duration_v2(duration) if is_v2
            else self._normalize_duration(duration)
        )
        resolution = (
            self._normalize_resolution_v2(resolution) if is_v2
            else self._normalize_resolution(resolution)
        )

        try:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            }

            if is_v2:
                # v2：多模态 content 数组，文生视频必须带非空 text，ratio 不可为 adaptive
                content = [{"type": "text", "text": prompt}]
                if image_url:
                    content.append(
                        {
                            "type": "image_url",
                            "image_url": {"url": image_url},
                            "role": "first_frame",
                        }
                    )
                payload = {
                    "model": model,
                    "content": content,
                    "resolution": resolution,
                    "duration": duration_sec,
                    "ratio": "adaptive" if image_url else "16:9",
                }
            else:
                # v1：平铺字段
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
                submit_url = (
                    f"{self.base_url}/v2/video_generation"
                    if is_v2
                    else f"{self.base_url}/v1/video_generation"
                )
                response = await client.post(
                    submit_url,
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

                task_id = data.get("task_id") or (data.get("task") or {}).get("id")
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
            is_v2 = self._uses_v2_protocol(self.default_model)
            if is_v2:
                # v2：task_id 作为路径参数
                query_url = f"{self.base_url}/v2/query/video_generation/{task_id}"
            else:
                query_url = f"{self.base_url}/v1/query/video_generation"
            response = await client.get(
                query_url,
                params={} if is_v2 else {"task_id": task_id},
                headers=headers,
            )

            if response.status_code != 200:
                error_msg = self._extract_error_message(response, f"HTTP {response.status_code}")
                return True, None, error_msg or "查询任务失败"

            data = response.json()
            base_resp = data.get("base_resp") or {}
            if base_resp.get("status_code") not in (0, None):
                return True, None, base_resp.get("status_msg", "未知错误")

            task = data.get("task") or {}
            status = ((task.get("status") or data.get("status") or "")).lower()

            if status in ("success", "succeeded"):
                file_id = task.get("id") or data.get("file_id") or task_id
                # v2：task.content.url 直接返回最终视频地址
                content = task.get("content") or {}
                video_url = content.get("url")
                if video_url:
                    result = VideoGenerationResult.ok(
                        videos=[video_url],
                        model=self.default_model,
                        provider=self.provider_name,
                        task_id=task_id,
                        file_id=file_id,
                    )
                    return True, result, None

                # v1：需要凭 file_id 获取临时下载地址
                if not file_id:
                    return True, None, "任务成功但未返回 file_id"

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

            if status in ("fail", "failed", "cancelled"):
                return True, None, "视频生成失败"

            # Preparing / Queueing / Processing / queued / running / 未知状态 -> 继续轮询
            return False, None, None

    async def _retrieve_file_url(self, file_id: str) -> Optional[str]:
        """凭 file_id 获取临时下载地址"""
        headers = {"Authorization": f"Bearer {self.api_key}"}

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    f"{self.base_url}/v1/files/retrieve",
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
    def _normalize_duration_v2(duration: float) -> int:
        """v2 时长收敛到官方允许值 4~15"""
        value = int(round(float(duration)))
        lo, hi = MiniMaxVideoGenerator.V2_DURATION_RANGE
        return max(lo, min(hi, value))

    @staticmethod
    def _normalize_resolution_v2(resolution: str) -> str:
        """v2 分辨率收敛到官方允许值 {768P, 2K}"""
        value = (resolution or "").upper()
        if value == "2K":
            return "2K"
        # 1080P 官方 v2 不提供，取最接近的 2K；其余一律回落到 768P
        if value in ("1080P", "1080"):
            return "2K"
        return "768P"

    @staticmethod
    def _extract_error_message(
        response: httpx.Response, default_msg: str = "MiniMax API 错误"
    ) -> str:
        """从 v1/v2 两种响应形态中提取错误信息"""
        try:
            data = response.json()
        except Exception:
            return response.text or default_msg
        if isinstance(data, dict):
            # v2: {"type":"error","error":{"type":..,"message":".."}}
            err = data.get("error")
            if isinstance(err, dict) and err.get("message"):
                return err["message"]
            # v1: {"base_resp":{"status_msg":..}}
            base_resp = data.get("base_resp") or {}
            if base_resp.get("status_msg"):
                return base_resp["status_msg"]
            for key in ("message", "msg"):
                if data.get(key):
                    return data[key]
        return response.text or default_msg

    @staticmethod
    def _error_from_response(
        response: httpx.Response, default_msg: str = "MiniMax API 错误"
    ) -> VideoGenerationResult:
        """从非 200 响应中提取错误信息"""
        error_msg = MiniMaxVideoGenerator._extract_error_message(response, default_msg)
        return VideoGenerationResult.fail(f"MiniMax API 错误: {error_msg}", "minimax")
