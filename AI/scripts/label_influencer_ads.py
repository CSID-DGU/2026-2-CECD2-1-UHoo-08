"""
아직 판별하지 않은 인스타 게시물(is_ad IS NULL)의 광고 여부를 지금 판정해 저장한다.

서버에서는 인스타 수집 스케줄이 수집 뒤에 돌리므로, 이 스크립트는 첫 적재나
판별 결과를 확인할 때 쓴다. 1차 규칙이 못 정한 글만 2차 LLM(LLMRole.AD)을 부른다.

사용법 (AI 디렉터리에서):
    python -m scripts.label_influencer_ads
"""
import json
import logging

from services.ad_label_job import run


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    print(json.dumps(run(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
