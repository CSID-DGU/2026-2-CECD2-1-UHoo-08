"""
인플루언서 게시물을 지금 바로 한 번 수집한다.

서버에서는 앱이 정해진 시각마다 돌리므로, 이 스크립트는 첫 적재나
수집 결과를 눈으로 확인할 때 쓴다.

사용법 (AI 디렉터리에서):
    python -m scripts.collect_influencer_posts            # 최근 14일
    python -m scripts.collect_influencer_posts --days 30  # 첫 적재
"""
import argparse
import json
import logging

from services.influencer_collector import DEFAULT_LOOKBACK_DAYS, collect


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=DEFAULT_LOOKBACK_DAYS, help="이만큼 지난 게시물까지 읽는다")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)
    print(json.dumps(collect(lookback_days=args.days), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
