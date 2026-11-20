# Normalize 모델 비교: qwen3.8-flash

- 조건: A2. LLM + 구조 규칙
- 날짜: 2026-11-20
- 문제: v2 `dev` 240건
- 모델: qwen3.8-flash
- 부르는 곳: 동국 AI Gateway
- 모델 설정: temperature 그대로 보냄, 생각 기능 끔, JSON 응답 API 옵션
- 코드: 1a5ae4b
- 반복: 1번
- 시나리오 확률 기준값: 쓰지 않음
- 막연함 확률 기준값: 쓰지 않음

## 측정값

| 항목 | 평균 | 표준편차 | 실행별 |
| --- | ---: | ---: | --- |
| 시나리오 일치율 | 98.1% | - | 98.1% |
| 요청 종류 점수(macro-F1) | 0.937 | - | 0.937 |
| 값 일치율 | 99.0% | - | 99.0% |
| 되묻기 정밀도 | 67.3% | - | 67.3% |
| 되묻기 재현율 | 72.9% | - | 72.9% |
| 양식을 못 지킨 답의 비율 | 0.0% | - | 0.0% |
| 끝내 읽지 못한 질문 비율 | 0.0% | - | 0.0% |
| 오류가 난 질문 비율 | 0.0% | - | 0.0% |
| 시나리오 확률의 오차 | - | - | - |
| 막연함 확률의 오차 | - | - | - |
| 걸린 시간 가운데 값(초) | 2.105 | - | 2.105 |
| 걸린 시간 느린 쪽 값(초) | 3.090 | - | 3.090 |
| 질문당 LLM 호출 수 | 1.000 | - | 1.000 |
| 질문당 입력 토큰 | 2247.704 | - | 2247.704 |
| 질문당 출력 토큰 | 92.879 | - | 92.879 |
| 1,000건당 비용(달러) | 0.381 | - | 0.381 |
| 반복 일치율 | - | - | - |

## 처리 비율별 시나리오 일치율

이 조건은 시나리오 확률을 내지 않는다.

## 틀린 문제 (39건)

- **router-g-1231** 7만원으로 스킨케어 세트 짜줘 (1번 중 1번)
  - `needs_clarification` 기대 `False`, 실제 True
- **router-g-1234** 9만원 안에서 쿠션 컨실러 같이 골라줘 (1번 중 1번)
  - `category` 기대 `'base'`, 실제 None
- **router-g-1237** 20만원 스킨케어 풀 루틴 추천 (1번 중 1번)
  - `needs_clarification` 기대 `False`, 실제 True
- **router-g-1241** `value` 가성비 위주로 4만원 기초 세트 (1번 중 1번)
  - `needs_clarification` 기대 `False`, 실제 True
- **router-g-1242** `env` 건조한 요즘에 맞게 11만원 보습 세트 (1번 중 1번)
  - `needs_clarification` 기대 `False`, 실제 True
- **router-g-1246** 엄마 드릴 18만원 스킨케어 세트 구성 (1번 중 1번)
  - `needs_clarification` 기대 `False`, 실제 True
- **router-g-1248** 10만원에 맞춰서 진정 위주 루틴 짜줘 (1번 중 1번)
  - `needs_clarification` 기대 `False`, 실제 True
- **router-g-1250** 22만원으로 안티에이징 스킨케어 세트 (1번 중 1번)
  - `needs_clarification` 기대 `False`, 실제 True
- **router-g-1433** `ambiguous` 좋은 제품 (1번 중 1번)
  - `needs_clarification` 기대 `True`, 실제 False
- **router-g-1435** `ambiguous` 요즘 뭐가 괜찮아? (1번 중 1번)
  - `needs_clarification` 기대 `True`, 실제 False
- **router-g-1439** `ambiguous` 어제 본 거 사도 돼? (1번 중 1번)
  - `needs_clarification` 기대 `True`, 실제 False
- **router-g-1449** `ambiguous` 글쎄 (1번 중 1번)
  - `needs_clarification` 기대 `True`, 실제 False
- **router-g-1450** `ambiguous` 비싸? (1번 중 1번)
  - `needs_clarification` 기대 `True`, 실제 False
- **router-g-1558** `confusing` 후 공진향 3종 세트 괜찮아? (1번 중 1번)
  - `category` 기대 `'skincare'`, 실제 None
- **router-g-1560** `confusing` 클렌징오일 어떤 게 괜찮아? (1번 중 1번)
  - `scenario` 기대 `'S2_SEARCH'`, 실제 'S1_EVALUATE'
  - `request_type` 기대 `'SEARCH'`, 실제 'EVALUATE'
  - `needs_clarification` 기대 `False`, 실제 True
- **router-g-1562** `confusing` 닥터지 선크림 중에 뭐가 좋아? (1번 중 1번)
  - `scenario` 기대 `'S2_SEARCH'`, 실제 'S1_EVALUATE'
  - `request_type` 기대 `'SEARCH'`, 실제 'EVALUATE'
- **router-g-1564** `confusing` 더 순한 토너 없어? (1번 중 1번)
  - `request_type` 기대 `'SEARCH'`, 실제 'REFINE'
- **router-g-1565** `confusing` 이번엔 글로우한 쿠션으로 (1번 중 1번)
  - `request_type` 기대 `'SEARCH'`, 실제 'REFINE'
- **router-g-2231** 6만원으로 스킨케어 세트 구성해줘 (1번 중 1번)
  - `needs_clarification` 기대 `False`, 실제 True
- **router-g-2234** 8만원 안에서 파운데이션 파우더 같이 골라줘 (1번 중 1번)
  - `category` 기대 `'base'`, 실제 None
- **router-g-2237** 16만원 스킨케어 풀 루틴 추천 (1번 중 1번)
  - `needs_clarification` 기대 `False`, 실제 True
- **router-g-2239** 5만원으로 아침 스킨케어 루틴 (1번 중 1번)
  - `needs_clarification` 기대 `False`, 실제 True
- **router-g-2241** `value` 가성비 위주로 5만원 스킨케어 세트 (1번 중 1번)
  - `needs_clarification` 기대 `False`, 실제 True
- **router-g-2242** `env` 습한 요즘에 맞게 7만원 산뜻한 기초 세트 (1번 중 1번)
  - `needs_clarification` 기대 `False`, 실제 True
- **router-g-2246** 아빠 드릴 9만원 스킨케어 세트 구성 (1번 중 1번)
  - `needs_clarification` 기대 `False`, 실제 True
- **router-g-2250** 이십만원으로 탄력 스킨케어 세트 (1번 중 1번)
  - `needs_clarification` 기대 `False`, 실제 True
- **router-g-2432** `ambiguous` 뭐 바르면 돼? (1번 중 1번)
  - `needs_clarification` 기대 `True`, 실제 False
- **router-g-2433** `ambiguous` 괜찮은 제품 (1번 중 1번)
  - `needs_clarification` 기대 `True`, 실제 False
- **router-g-2434** `ambiguous` 하나만 골라줘 (1번 중 1번)
  - `needs_clarification` 기대 `True`, 실제 False
- **router-g-2435** `ambiguous` 요즘 뭐가 유행이야? (1번 중 1번)
  - `needs_clarification` 기대 `True`, 실제 False
- **router-g-2439** `ambiguous` 그저께 본 거 괜찮을까? (1번 중 1번)
  - `needs_clarification` 기대 `True`, 실제 False
- **router-g-2443** `ambiguous` 그거랑 비슷한 걸로 (1번 중 1번)
  - `needs_clarification` 기대 `True`, 실제 False
- **router-g-2448** `ambiguous` 전부 새로 사고 싶어 (1번 중 1번)
  - `needs_clarification` 기대 `True`, 실제 False
- **router-g-2450** `ambiguous` 얼마쯤 해? (1번 중 1번)
  - `needs_clarification` 기대 `True`, 실제 False
- **router-g-2560** `confusing` 클렌징밤 어떤 게 괜찮아? (1번 중 1번)
  - `scenario` 기대 `'S2_SEARCH'`, 실제 'S1_EVALUATE'
  - `request_type` 기대 `'SEARCH'`, 실제 'EVALUATE'
  - `needs_clarification` 기대 `False`, 실제 True
- **router-g-2562** `confusing` 이니스프리 선크림 중에 뭐가 좋아? (1번 중 1번)
  - `scenario` 기대 `'S2_SEARCH'`, 실제 'S1_EVALUATE'
  - `request_type` 기대 `'SEARCH'`, 실제 'EVALUATE'
- **router-g-2564** `confusing` 더 촉촉한 세럼 없어? (1번 중 1번)
  - `request_type` 기대 `'SEARCH'`, 실제 'REFINE'
- **router-g-2565** `confusing` 이번엔 매트한 파운데이션으로 (1번 중 1번)
  - `request_type` 기대 `'SEARCH'`, 실제 'REFINE'
- **router-g-2573** `confusing` 기초 전부 11만원에 맞춰서 사고 싶어 (1번 중 1번)
  - `needs_clarification` 기대 `False`, 실제 True

## 원인과 다음 조치

- 시나리오를 틀린 4건은 모두 "클렌징오일 어떤 게 괜찮아?", "닥터지 선크림 중에 뭐가 좋아?"처럼 종류나 브랜드만 말한 질문을 평가로 읽은 것이다.
- 되물어야 하는데 안 물은 것이 13건으로 후보 중 가장 많다. "좋은 제품", "글쎄", "비싸?" 같은 막연한 말에도 조건을 채워 넣는다.
- 안 물어도 되는데 되물은 17건 중 15건은 예산만 있고 세트 단계가 빈 질문이다.
- 동국 AI Gateway 를 거쳐 불렀다. 같은 모델을 DashScope 에 직접 부를 때보다 시간이 길게 나온다.
