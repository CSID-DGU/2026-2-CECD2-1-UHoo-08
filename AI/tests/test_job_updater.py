"""job_updater 단위 테스트. Supabase 호출은 모킹."""
from unittest.mock import MagicMock, patch

import pytest

from services.job_updater import update


class TestJobUpdater:
    @pytest.mark.asyncio
    @patch("services.job_updater.get_supabase")
    async def test_partial_update_step_progress(self, mock_get_sb):
        sb = MagicMock()
        mock_get_sb.return_value = sb

        await update("job_001", step="후보 탐색", progress=25)

        # sb.table("recommendation_jobs").update(payload).eq("id", job_id).execute()
        payload = sb.table.return_value.update.call_args.args[0]
        assert payload["step"] == "후보 탐색"
        assert payload["progress"] == 25
        assert "updated_at" in payload
        # None 필드는 포함 안 됨
        assert "status" not in payload
        assert "error_msg" not in payload

    @pytest.mark.asyncio
    @patch("services.job_updater.get_supabase")
    async def test_steps(self, mock_get_sb):
        sb = MagicMock()
        mock_get_sb.return_value = sb
        steps = [{"key": "normalize", "label": "요청 이해", "state": "NOW"}]

        await update("job_001", step="요청 이해", progress=0, steps=steps)

        payload = sb.table.return_value.update.call_args.args[0]
        assert payload["steps"] == steps

    @pytest.mark.asyncio
    @patch("services.job_updater.get_supabase")
    async def test_completed_status(self, mock_get_sb):
        sb = MagicMock()
        mock_get_sb.return_value = sb

        await update("job_001", progress=100, status="COMPLETED")

        payload = sb.table.return_value.update.call_args.args[0]
        assert payload["progress"] == 100
        assert payload["status"] == "COMPLETED"

    @pytest.mark.asyncio
    @patch("services.job_updater.get_supabase")
    async def test_failed_with_error(self, mock_get_sb):
        sb = MagicMock()
        mock_get_sb.return_value = sb

        await update("job_001", status="FAILED", error_msg="ConnectionError: ...")

        payload = sb.table.return_value.update.call_args.args[0]
        assert payload["status"] == "FAILED"
        assert payload["error_msg"] == "ConnectionError: ..."

    @pytest.mark.asyncio
    @patch("services.job_updater.get_supabase")
    async def test_job_id_used_in_filter(self, mock_get_sb):
        sb = MagicMock()
        mock_get_sb.return_value = sb

        await update("job_001", step="AI 분석")

        sb.table.return_value.update.return_value.eq.assert_called_with("id", "job_001")