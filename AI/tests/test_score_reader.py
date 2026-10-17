"""score_reader 단위 테스트. Supabase 호출 모킹."""
from unittest.mock import MagicMock, patch


class TestScoreReader:
    @patch("db.score_reader.get_supabase")
    def test_get_insights(self, mock_sb):
        from db.score_reader import get_insights

        sb = MagicMock()
        sb.table.return_value.select.return_value.in_.return_value.execute.return_value.data = [
            {
                "product_id": "p1",
                "lowest_price": 25000,
                "products": {"original_price": 30000},
            }
        ]
        mock_sb.return_value = sb
        out = get_insights(["p1"])
        assert out["p1"]["lowest_price"] == 25000
        assert out["p1"]["original_price"] == 30000

    @patch("db.score_reader.get_supabase")
    def test_get_features(self, mock_sb):
        from db.score_reader import get_features

        sb = MagicMock()
        sb.table.return_value.select.return_value.in_.return_value.execute.return_value.data = [
            {"product_id": "p1", "feature_json": {"skin_type": "지성"}}
        ]
        mock_sb.return_value = sb
        out = get_features(["p1"])
        assert out["p1"]["skin_type"] == "지성"

    def test_get_insights_empty(self):
        from db.score_reader import get_insights
        assert get_insights([]) == {}

    def test_get_features_empty(self):
        from db.score_reader import get_features
        assert get_features([]) == {}

class TestGetUserProductsByUsers:
    """Supabase 는 한 번에 1,000행까지만 준다. 넘으면 나눠 읽어야 최근 평점이 빠지지 않는다."""

    @staticmethod
    def _rows(n, start=0):
        return [
            {"id": f"r{start + i:05d}", "user_id": "u2", "product_id": f"p{start + i}",
             "usage_type": "USING", "rating": 4, "created_at": "2026-09-01T10:00:00"}
            for i in range(n)
        ]

    def _mock_pages(self, mock_sb, pages):
        sb = MagicMock()
        query = sb.table.return_value.select.return_value.in_.return_value.order.return_value
        query.range.return_value.execute.side_effect = [MagicMock(data=p) for p in pages]
        mock_sb.return_value = sb
        return sb, query

    @patch("db.score_reader.get_supabase")
    def test_1000행을_넘으면_다음_페이지까지_읽는다(self, mock_sb):
        from db.score_reader import get_user_products_by_users

        sb, query = self._mock_pages(mock_sb, [self._rows(1000), self._rows(1, start=1000)])

        rows = get_user_products_by_users(["u2"])

        assert len(rows) == 1001
        assert rows[-1]["id"] == "r01000"
        # 페이지마다 같은 순서를 보장하도록 id 로 정렬한다
        sb.table.return_value.select.return_value.in_.return_value.order.assert_called_with("id")
        assert [c.args for c in query.range.call_args_list] == [(0, 999), (1000, 1999)]

    @patch("db.score_reader.get_supabase")
    def test_딱_1000행이면_빈_페이지를_보고_멈춘다(self, mock_sb):
        from db.score_reader import get_user_products_by_users

        _, query = self._mock_pages(mock_sb, [self._rows(1000), []])

        assert len(get_user_products_by_users(["u2"])) == 1000
        assert query.range.call_count == 2

    @patch("db.score_reader.get_supabase")
    def test_1000행보다_적으면_한_번만_읽는다(self, mock_sb):
        from db.score_reader import get_user_products_by_users

        _, query = self._mock_pages(mock_sb, [self._rows(3)])

        assert len(get_user_products_by_users(["u2"])) == 3
        assert query.range.call_count == 1

    @patch("db.score_reader.get_supabase")
    def test_사용자가_없으면_조회하지_않는다(self, mock_sb):
        from db.score_reader import get_user_products_by_users

        assert get_user_products_by_users([]) == []
        mock_sb.assert_not_called()
