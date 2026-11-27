"""
지역별 환경의 지난 며칠을 채운다. 매시 수집을 켜기 전 4주를 만들 때 한 번 쓴다.

기본은 만들 줄 수만 보여 주고 저장하지 않는다. 이미 있는 시간은 덮어쓰지 않으므로
--write 를 여러 번 돌려도 괜찮다.

사용법 (AI 디렉터리에서):
    python -m scripts.backfill_env                       # 28일, 저장 안 함
    python -m scripts.backfill_env --write               # 저장
    python -m scripts.backfill_env --region 서울 --write  # 한 지역만
"""
import argparse
import json
import logging

from services.env_backfill import backfill


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=28, help="오늘 포함 이만큼의 날을 채운다 (최대 30)")
    parser.add_argument("--region", action="append", help="이 지역만. 여러 번 줄 수 있다")
    parser.add_argument("--write", action="store_true", help="env_observations 에 저장하고 하루 집계를 다시 만든다")
    args = parser.parse_args()
    if not 1 <= args.days <= 30:
        # 에어코리아 측정소 조회(dataTerm=MONTH)가 한 달까지만 준다
        parser.error("--days 는 1~30")

    logging.basicConfig(level=logging.INFO)
    print(json.dumps(backfill(args.days, write=args.write, regions=args.region),
                     ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
