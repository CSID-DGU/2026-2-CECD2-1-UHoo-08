from unittest.mock import AsyncMock, patch

import pytest


class TestCollaborativeAgent:
    @pytest.mark.asyncio
    @patch("agents.collaborative_agent.run_fallback", new_callable=AsyncMock)
    @patch("agents.collaborative_agent.get_products_meta")
    @patch("agents.collaborative_agent.get_user_products_by_users")
    @patch("agents.collaborative_agent.get_similar_user_ids")
    async def test_aggregation_path(
        self, mock_sim, mock_ups, mock_metas, mock_fallback
    ):
        from agents.collaborative_agent import run_collaborative

        mock_sim.return_value = ["u2", "u3", "u4"]
        mock_ups.return_value = [
            {"user_id": "u2", "product_id": "p1", "usage_type": "USING", "rating": 5},
            {"user_id": "u3", "product_id": "p1", "usage_type": "USED", "rating": 4},
            {"user_id": "u4", "product_id": "p1", "usage_type": "USING", "rating": 5},
            {"user_id": "u2", "product_id": "p2", "usage_type": "INTERESTED", "rating": 3},
            {"user_id": "u3", "product_id": "p2", "usage_type": "USED", "rating": 4},
            {"user_id": "u4", "product_id": "p3", "usage_type": "USING", "rating": 4},
        ]
        mock_metas.return_value = {
            "p1": {"id": "p1", "name": "쿠션A", "brand": "B1", "category": "base", "image_url": None, "price": 30000},
            "p2": {"id": "p2", "name": "쿠션B", "brand": "B2", "category": "base", "image_url": None, "price": 25000},
            "p3": {"id": "p3", "name": "쿠션C", "brand": "B3", "category": "base", "image_url": None, "price": 35000},
        }

        results = await run_collaborative(
            user_id="u1",
            skin_type="OILY",
            personal_color="SPRING_WARM",
            top_k=3,
        )
        # 폴백 안 거침
        mock_fallback.assert_not_called()
        # p1 = 5 + 4×0.7 + 5, p3 = 4, p2 = 4×0.7 (u2 의 INTERESTED 는 좋아요라 빠진다)
        assert [r.id for r in results] == ["p1", "p3", "p2"]

    @pytest.mark.asyncio
    @patch("agents.collaborative_agent.run_fallback", new_callable=AsyncMock)
    @patch("agents.collaborative_agent.get_similar_user_ids")
    async def test_no_similar_users_goes_to_fallback(self, mock_sim, mock_fallback):
        from agents.collaborative_agent import run_collaborative

        mock_sim.return_value = []
        mock_fallback.return_value = []

        await run_collaborative(
            user_id="u1",
            skin_type="OILY",
            personal_color="SPRING_WARM",
        )
        mock_fallback.assert_called_once()

    @pytest.mark.asyncio
    @patch("agents.collaborative_agent.run_fallback", new_callable=AsyncMock)
    @patch("agents.collaborative_agent.get_user_products_by_users")
    @patch("agents.collaborative_agent.get_similar_user_ids")
    async def test_insufficient_results_goes_to_fallback(
        self, mock_sim, mock_ups, mock_fallback
    ):
        from agents.collaborative_agent import run_collaborative

        mock_sim.return_value = ["u2"]
        mock_ups.return_value = [
            {"user_id": "u2", "product_id": "p1", "usage_type": "USING", "rating": 5},
        ]  # MIN_VALID_RESULTS=3 미만
        mock_fallback.return_value = []

        await run_collaborative(user_id="u1", skin_type="OILY", personal_color=None)
        mock_fallback.assert_called_once()

    @pytest.mark.asyncio
    @patch("agents.collaborative_agent.get_products_meta")
    @patch("agents.collaborative_agent.get_user_products_by_users")
    @patch("agents.collaborative_agent.get_similar_user_ids")
    async def test_exclude_ids_filtered(self, mock_sim, mock_ups, mock_metas):
        from agents.collaborative_agent import run_collaborative

        mock_sim.return_value = ["u2", "u3", "u4"]
        mock_ups.return_value = [
            {"user_id": "u2", "product_id": "p1", "usage_type": "USING", "rating": 5},
            {"user_id": "u3", "product_id": "p2", "usage_type": "USING", "rating": 4},
            {"user_id": "u4", "product_id": "p3", "usage_type": "USING", "rating": 4},
        ]
        mock_metas.return_value = {
            "p2": {"id": "p2", "name": "쿠션B", "brand": "B2", "category": "base", "image_url": None, "price": 25000},
            "p3": {"id": "p3", "name": "쿠션C", "brand": "B3", "category": "base", "image_url": None, "price": 35000},
        }

        results = await run_collaborative(
            user_id="u1",
            skin_type="OILY",
            personal_color="SPRING_WARM",
            exclude_ids=["p1"],
            top_k=3,
        )
        assert all(r.id != "p1" for r in results)

class TestAggregate:
    """_aggregate: 실제로 써 본 기록만, 사람·상품마다 한 번만 센다."""

    def test_좋아요와_버림과_조회는_집계에서_빠진다(self):
        from agents.collaborative_agent import _aggregate

        rows = [
            {"user_id": "u2", "product_id": "p1", "usage_type": "INTERESTED", "rating": 5},
            {"user_id": "u3", "product_id": "p1", "usage_type": "DISCARDED", "rating": 5},
            {"user_id": "u4", "product_id": "p1", "usage_type": "VIEWED", "rating": 5},
            {"user_id": "u5", "product_id": "p1", "usage_type": "ONBOARDING", "rating": 5},
            {"user_id": "u6", "product_id": "p2", "usage_type": "USING", "rating": 4},
        ]

        assert _aggregate(rows, set()) == [("p2", 4.0, 1)]

    def test_같은_제품을_여러_번_산_사람은_한_번만_센다(self):
        from agents.collaborative_agent import _aggregate

        rows = [
            # u2 는 p1 을 두 번 샀다. 예전 통은 다 썼고(USED, 평점 2), 지금 통을 쓰는 중이다(USING, 평점 5)
            {"user_id": "u2", "product_id": "p1", "usage_type": "USED", "rating": 2,
             "created_at": "2026-03-01T10:00:00"},
            {"user_id": "u2", "product_id": "p1", "usage_type": "USING", "rating": 5,
             "created_at": "2026-09-01T10:00:00"},
        ]

        # 평점이 있는 가장 최근 행(USING, 평점 5) 하나만 센다. 평가한 사람 1명
        assert _aggregate(rows, set()) == [("p1", 5.0, 1)]

    def test_가장_최근_통에_평점이_없으면_그전_행의_가중치와_평점을_함께_쓴다(self):
        from agents.collaborative_agent import _aggregate

        rows = [
            {"user_id": "u2", "product_id": "p1", "usage_type": "USED", "rating": 4,
             "created_at": "2026-03-01T10:00:00"},
            {"user_id": "u2", "product_id": "p1", "usage_type": "USING", "rating": None,
             "created_at": "2026-09-01T10:00:00"},
        ]

        # 평점 4는 다 써 보고 준 것이므로 USED 가중치(0.7)와 함께 쓴다. USING(1.0)을 곱하지 않는다
        [(pid, score, n)] = _aggregate(rows, set())
        assert (pid, n) == ("p1", 1)
        assert score == pytest.approx(4 * 0.7)

    def test_평점이_하나도_없는_사람은_세지_않는다(self):
        from agents.collaborative_agent import _aggregate

        rows = [{"user_id": "u2", "product_id": "p1", "usage_type": "USING", "rating": None}]

        assert _aggregate(rows, set()) == []

    def test_제외한_제품은_세지_않는다(self):
        from agents.collaborative_agent import _aggregate

        rows = [
            {"user_id": "u2", "product_id": "p1", "usage_type": "USING", "rating": 5},
            {"user_id": "u3", "product_id": "p2", "usage_type": "USING", "rating": 3},
        ]

        assert _aggregate(rows, {"p1"}) == [("p2", 3.0, 1)]
