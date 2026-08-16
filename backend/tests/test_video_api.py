# -*- coding: utf-8 -*-
"""
视频生成 API 回归测试
"""
import pytest

from app.models.creation import Creation, CreationStatus, CreationType


@pytest.fixture
def video_user(db_session, test_user):
    """给测试用户充足积分，避免 402 拦截"""
    test_user.credits = 5000
    db_session.commit()
    db_session.refresh(test_user)
    return test_user


class TestVideoAPI:
    """视频生成接口回归测试"""

    @staticmethod
    def _patch_background_tasks(monkeypatch):
        """把后台生成任务替换为空操作，保证测试快速且确定"""
        import app.api.v1.video as video_api

        async def _noop(*args, **kwargs):
            return None

        monkeypatch.setattr(video_api, "process_text_to_video", _noop)
        monkeypatch.setattr(video_api, "process_image_to_video", _noop)

    def test_text_to_video_creation_has_video_type(
        self, client, db_session, auth_headers, video_user, monkeypatch
    ):
        """文本转视频落库时 creation_type 必须为 video（回归：nullable=False 导致 1048）"""
        self._patch_background_tasks(monkeypatch)

        response = client.post(
            "/api/v1/video/text-to-video",
            headers=auth_headers,
            json={"text": "蓝天白云", "background_music": False, "subtitle": False},
        )

        assert response.status_code == 200
        data = response.json()["data"]
        assert data["status"] == "processing"
        assert data["task_id"].startswith("t2v_")

        creation = (
            db_session.query(Creation)
            .filter(Creation.task_id == data["task_id"])
            .first()
        )
        assert creation is not None
        assert creation.creation_type is not None
        assert creation.creation_type == CreationType.VIDEO
        assert creation.tool_type == "text_to_video"
        assert creation.status == CreationStatus.PROCESSING
        assert creation.user_id == video_user.id
        assert creation.title.startswith("文本转视频")

        # 积分按规则扣除：基础 150（未开背景音乐、未开字幕）
        db_session.refresh(video_user)
        assert video_user.credits == 5000 - 150

    def test_image_to_video_creation_has_video_type(
        self, client, db_session, auth_headers, video_user, monkeypatch
    ):
        """图片转视频落库时 creation_type 必须为 video（回归：与文生视频同类漏填）"""
        self._patch_background_tasks(monkeypatch)

        response = client.post(
            "/api/v1/video/image-to-video",
            headers=auth_headers,
            json={
                "images": ["data:image/png;base64,ZmFrZQ=="],
                "transition": "fade",
                "duration_per_image": 3,
            },
        )

        assert response.status_code == 200
        data = response.json()["data"]
        assert data["status"] == "processing"
        assert data["task_id"].startswith("i2v_")

        creation = (
            db_session.query(Creation)
            .filter(Creation.task_id == data["task_id"])
            .first()
        )
        assert creation is not None
        assert creation.creation_type is not None
        assert creation.creation_type == CreationType.VIDEO
        assert creation.tool_type == "image_to_video"
        assert creation.status == CreationStatus.PROCESSING
        assert creation.user_id == video_user.id
        assert creation.title.startswith("图片转视频")

        # 积分按规则扣除：基础 100 + 1 张图片 * 20
        db_session.refresh(video_user)
        assert video_user.credits == 5000 - 120


class TestVideoGenerationFlow:
    """视频生成真实链路（mock 供应商）接口级测试"""

    @staticmethod
    def _install_fake_generator(monkeypatch):
        """替换供应商工厂与本地下载，验证后端接线逻辑"""
        import app.api.v1.video as video_api
        from app.services.langchain.video.base import VideoGenerationResult
        from app.services.langchain.video.factory import VideoGeneratorFactory

        class FakeGenerator:
            async def generate(self, prompt, image_url=None, duration=6, resolution="768P", **kwargs):
                return VideoGenerationResult.ok(
                    videos=["https://example.com/generated.mp4"],
                    task_id="fake_provider_task",
                )

        monkeypatch.setattr(
            video_api,
            "save_video_from_url",
            lambda url, filename=None: "/uploads/videos/test_video.mp4",
        )
        monkeypatch.setattr(
            VideoGeneratorFactory,
            "create",
            classmethod(lambda cls, **kwargs: FakeGenerator()),
        )

    @staticmethod
    def _create_video_model(db_session, user):
        from app.models.ai_model import AIModel

        model = AIModel(
            user_id=user.id,
            name="MiniMax视频",
            provider="minimax",
            model_name="MiniMax-Hailuo-2.3",
            api_key="sk-test",
            base_url="https://api.minimaxi.com/v1",
            is_active=True,
            capabilities=["video"],
        )
        db_session.add(model)
        db_session.commit()
        db_session.refresh(model)
        return model

    @staticmethod
    def _wait_for_terminal_status(client, headers, task_id, timeout=5.0):
        """轮询任务接口直到 completed/failed（后台任务与 TestClient 生命周期一致，此处兜底）"""
        import time

        deadline = time.time() + timeout
        while time.time() < deadline:
            resp = client.get(f"/api/v1/video/task/{task_id}", headers=headers)
            assert resp.status_code == 200
            status = resp.json()["data"]["status"]
            if status in ("completed", "failed"):
                return resp.json()["data"]
            time.sleep(0.1)
        raise AssertionError(f"task {task_id} 未在 {timeout}s 内结束")

    def test_text_to_video_real_flow_completes(
        self, client, db_session, auth_headers, video_user, monkeypatch
    ):
        """文生视频真实链路：提交 -> mock 供应商 -> 下载 -> completed"""
        self._install_fake_generator(monkeypatch)
        self._create_video_model(db_session, video_user)

        response = client.post(
            "/api/v1/video/text-to-video",
            headers=auth_headers,
            json={
                "text": "蓝天白云",
                "duration": 6,
                "resolution": "768P",
                "background_music": False,
                "subtitle": False,
            },
        )
        assert response.status_code == 200
        task_id = response.json()["data"]["task_id"]

        task = self._wait_for_terminal_status(client, auth_headers, task_id)
        assert task["status"] == "completed"
        assert task["video_url"] == "/uploads/videos/test_video.mp4"

        creation = (
            db_session.query(Creation)
            .filter(Creation.task_id == task_id)
            .first()
        )
        assert creation is not None
        assert creation.status == CreationStatus.COMPLETED
        assert creation.creation_type == CreationType.VIDEO
        assert creation.output_data["video_url"] == "/uploads/videos/test_video.mp4"
        assert creation.error_message is None

    def test_image_to_video_real_flow_completes(
        self, client, db_session, auth_headers, video_user, monkeypatch
    ):
        """图生视频真实链路：提交 -> mock 供应商 -> 下载 -> completed"""
        self._install_fake_generator(monkeypatch)
        self._create_video_model(db_session, video_user)

        response = client.post(
            "/api/v1/video/image-to-video",
            headers=auth_headers,
            json={
                "images": ["data:image/png;base64,ZmFrZQ=="],
                "transition": "fade",
                "duration_per_image": 3,
                "motion_prompt": "画面中的云缓慢飘动",
                "duration": 6,
                "resolution": "768P",
            },
        )
        assert response.status_code == 200
        task_id = response.json()["data"]["task_id"]

        task = self._wait_for_terminal_status(client, auth_headers, task_id)
        assert task["status"] == "completed"
        assert task["video_url"] == "/uploads/videos/test_video.mp4"

        creation = (
            db_session.query(Creation)
            .filter(Creation.task_id == task_id)
            .first()
        )
        assert creation is not None
        assert creation.status == CreationStatus.COMPLETED
        assert creation.creation_type == CreationType.VIDEO
        assert creation.tool_type == "image_to_video"

    def test_generation_fails_without_video_model(
        self, client, db_session, auth_headers, video_user, monkeypatch
    ):
        """没有配置视频模型时，任务应标记为 failed 而不是抛 500"""
        self._install_fake_generator(monkeypatch)
        # 不创建任何视频模型

        response = client.post(
            "/api/v1/video/text-to-video",
            headers=auth_headers,
            json={"text": "蓝天白云", "background_music": False, "subtitle": False},
        )
        assert response.status_code == 200
        task_id = response.json()["data"]["task_id"]

        task = self._wait_for_terminal_status(client, auth_headers, task_id)
        assert task["status"] == "failed"
        assert "视频生成" in (task.get("error") or "")
