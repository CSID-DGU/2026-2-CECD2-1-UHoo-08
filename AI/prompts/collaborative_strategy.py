"""
collaborative_agent의 weighted_score 가중치 + 콜드스타트 임계치.

LLM 호출 없는 모듈이지만, 디렉토리 구조 일관성을 위해 prompts/ 하위에 둔다.
실제로 LLM 프롬프트가 필요해지면 본 모듈에 함께 추가.
"""

# 사용 상태별 신뢰도 가중치. 실제로 써 본 사람의 평점만 본다.
# USING: 현재 사용 중 → 가장 신뢰
# USED:  과거에 사용 → 보통 신뢰
# 좋아요(wishlists)는 써 보지 않은 관심이고 평점이 없어 넣지 않는다.
# 버림(DISCARDED)과 그 밖의 값은 0 으로 보고 집계에서 뺀다.
USAGE_WEIGHTS = {
    "USING": 1.0,
    "USED": 0.7,
}

# weighted_score 집계 결과가 이 값 미만이면 콜드스타트로 판단해 fallback 실행
MIN_VALID_RESULTS = 3

# fallback 시 최소 평점 컷
FALLBACK_MIN_RATING = 3.5