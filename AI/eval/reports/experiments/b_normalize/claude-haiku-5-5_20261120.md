# Normalize 모델 비교: claude-haiku-5-5

- 조건: A2. LLM + 구조 규칙
- 날짜: 2026-11-20
- 문제: v2 `test` 360건
- 모델: claude-haiku-5-5
- 부르는 곳: Anthropic API
- 모델 설정: temperature 보내지 않음 (받지 않는 모델), 생각 기능 끔, JSON 응답 프롬프트로만
- 코드: 2fd22c7
- 반복: 3번
- 시나리오 확률 기준값: 쓰지 않음
- 막연함 확률 기준값: 쓰지 않음

## 측정값

| 항목 | 평균 | 표준편차 | 실행별 |
| --- | ---: | ---: | --- |
| 시나리오 일치율 | 99.6% | 0.2% | 99.4%, 99.7%, 99.7% |
| 요청 종류 점수(macro-F1) | 0.951 | 0.005 | 0.947, 0.956, 0.949 |
| 값 일치율 | 99.6% | 0.2% | 99.8%, 99.4%, 99.8% |
| 되묻기 정밀도 | 88.8% | 2.3% | 90.0%, 86.2%, 90.3% |
| 되묻기 재현율 | 81.4% | 1.7% | 79.4%, 82.4%, 82.4% |
| 양식을 못 지킨 답의 비율 | 3.3% | 0.3% | 3.0%, 3.5%, 3.3% |
| 끝내 읽지 못한 질문 비율 | 1.4% | 0.0% | 1.4%, 1.4%, 1.4% |
| 오류가 난 질문 비율 | 0.0% | 0.0% | 0.0%, 0.0%, 0.0% |
| 시나리오 확률의 오차 | - | - | -, -, - |
| 막연함 확률의 오차 | - | - | -, -, - |
| 걸린 시간 가운데 값(초) | 0.998 | 0.011 | 0.991, 0.992, 1.010 |
| 걸린 시간 느린 쪽 값(초) | 1.192 | 0.018 | 1.203, 1.172, 1.202 |
| 질문당 LLM 호출 수 | 1.019 | 0.003 | 1.017, 1.022, 1.019 |
| 질문당 입력 토큰 | 3511.536 | 9.553 | 3501.994, 3521.100, 3511.514 |
| 질문당 출력 토큰 | 142.591 | 0.590 | 143.067, 142.775, 141.931 |
| 1,000건당 비용(달러) | 0.422 | 0.001 | 0.422, 0.423, 0.422 |
| 반복 일치율 | 96.7% | - | - |

## 처리 비율별 시나리오 일치율

이 조건은 시나리오 확률을 내지 않는다.

## 틀린 문제 (32건)

- **router-g-1030** `target` 요즘 많이들 쓰는 파우더 알려줘 (3번 중 1번)
  - `request_type` 기대 `'SEARCH'`, 실제 None
  - `needs_clarification` 기대 `False`, 실제 True
  - `category` 기대 `'base'`, 실제 None
  - `target` 기대 `'POPULAR'`, 실제 None
- **router-g-1204** 20만원으로 기초 라인 한 번에 맞추고 싶어 (3번 중 2번)
  - `needs_clarification` 기대 `False`, 실제 True
- **router-g-1214** `value` 가성비로 6만원 스킨케어 세트 구성 (3번 중 2번)
  - `needs_clarification` 기대 `False`, 실제 True
- **router-g-1215** `env` 요즘 날씨에 맞춰 9만원으로 스킨케어 세트 (3번 중 3번)
  - `needs_clarification` 기대 `False`, 실제 True
- **router-g-1218** 건성 피부 겨울 루틴 11만원으로 짜줘 (3번 중 2번)
  - `needs_clarification` 기대 `False`, 실제 True
- **router-g-1222** 친구 선물용으로 8만원 스킨케어 세트 짜줘 (3번 중 3번)
  - `needs_clarification` 기대 `False`, 실제 True
- **router-g-1227** 트러블 피부용으로 10만원 진정 루틴 짜줘 (3번 중 3번)
  - `needs_clarification` 기대 `False`, 실제 True
- **router-g-1402** `ambiguous` 하나 골라줘 (3번 중 3번)
  - `request_type` 기대 `'SEARCH'`, 실제 'REFINE'
  - `needs_clarification` 기대 `True`, 실제 False
- **router-g-1404** `ambiguous` 요즘 뭐 사야 돼? (3번 중 1번)
  - `needs_clarification` 기대 `True`, 실제 False
- **router-g-1407** `ambiguous` 쓸 만한 거 없어? (3번 중 1번)
  - `scenario` 기대 `'S2_SEARCH'`, 실제 'S1_EVALUATE'
  - `request_type` 기대 `'SEARCH'`, 실제 'EVALUATE'
- **router-g-1408** `ambiguous` 나한테 맞는 거 찾아줘 (3번 중 3번)
  - `needs_clarification` 기대 `True`, 실제 False
- **router-g-1409** `ambiguous` 선물할 건데 뭐가 좋아? (3번 중 3번)
  - `needs_clarification` 기대 `True`, 실제 False
- **router-g-1410** `ambiguous` 예쁜 거 (3번 중 3번)
  - `needs_clarification` 기대 `True`, 실제 False
- **router-g-1413** `ambiguous` 저번에 산 거 나한테 맞는 거야? (3번 중 3번)
  - `needs_clarification` 기대 `True`, 실제 False
- **router-g-1419** `ambiguous` 방금 그거 성분 괜찮아? (3번 중 3번)
  - `needs_clarification` 기대 `True`, 실제 False
- **router-g-1430** `ambiguous` 얼마야? (3번 중 3번)
  - `needs_clarification` 기대 `True`, 실제 False
- **router-g-1522** `confusing` 더 저렴한 쿠션 없어? (3번 중 3번)
  - `request_type` 기대 `'SEARCH'`, 실제 'REFINE'
- **router-g-1525** `confusing` 다른 세럼도 보여줘 (3번 중 3번)
  - `request_type` 기대 `'SEARCH'`, 실제 'REFINE'
- **router-g-1532** `confusing` 기초 세트는 있고 세럼만 추가로 찾아줘 (3번 중 2번)
  - `request_type` 기대 `'SEARCH'`, 실제 'REFINE'
- **router-g-2011** 만 오천원 넘지 않는 클렌징밤 (3번 중 3번)
  - `budget_max` 기대 `15000`, 실제 5000
- **router-g-2214** `value` 가성비 좋게 8만원 기초 세트 구성 (3번 중 1번)
  - `needs_clarification` 기대 `False`, 실제 True
- **router-g-2222** 엄마 선물로 13만원 스킨케어 세트 짜줘 (3번 중 1번)
  - `needs_clarification` 기대 `False`, 실제 True
- **router-g-2227** 민감성 피부용으로 11만원 저자극 루틴 짜줘 (3번 중 3번)
  - `needs_clarification` 기대 `False`, 실제 True
- **router-g-2402** `ambiguous` 좋은 거 하나만 (3번 중 3번)
  - `needs_clarification` 기대 `True`, 실제 False
- **router-g-2406** `ambiguous` 인기템 알려줘 (3번 중 1번)
  - `needs_clarification` 기대 `True`, 실제 False
- **router-g-2408** `ambiguous` 내 피부에 맞는 걸로 (3번 중 3번)
  - `needs_clarification` 기대 `True`, 실제 False
- **router-g-2409** `ambiguous` 생일 선물 뭐가 좋을까 (3번 중 3번)
  - `needs_clarification` 기대 `True`, 실제 False
- **router-g-2410** `ambiguous` 무난한 거 (3번 중 3번)
  - `needs_clarification` 기대 `True`, 실제 False
- **router-g-2413** `ambiguous` 지난주에 산 거 계속 써도 돼? (3번 중 1번)
  - `needs_clarification` 기대 `True`, 실제 False
- **router-g-2418** `ambiguous` 엄마가 쓰던 에센스인데 나도 써도 될까 (3번 중 3번)
  - `needs_clarification` 기대 `True`, 실제 False
- **router-g-2505** `confusing` 아넷사 퍼펙트 UV 같은 선크림 국산으로 없어? (3번 중 3번)
  - `scenario` 기대 `'S1_EVALUATE'`, 실제 'S2_SEARCH'
  - `request_type` 기대 `'EVALUATE'`, 실제 'SEARCH'
- **router-g-2522** `confusing` 더 가벼운 파운데이션 없어? (3번 중 3번)
  - `request_type` 기대 `'SEARCH'`, 실제 'REFINE'

## 원인과 다음 조치

- 한 번이라도 틀린 문제는 32건으로 셋 중 가장 적다. 시간도 가장 짧다(가운데 값 1.00초, 느린 쪽 값 1.19초).
- JSON 대신 대화하듯 답한 것이 세 번 실행에서 34번이다. "흠", "몰라", "음"은 세 번 모두 끝내 읽지 못했다. 이런 말은 되묻는 것이 맞아 결과에는 영향이 없다. 다만 조건 수정인 "다른 브랜드로"(세 번 중 두 번), "국내 브랜드로만"(한 번)과 평범한 검색인 "요즘 많이들 쓰는 파우더 알려줘"(한 번)도 읽지 못했다.
- 시나리오를 틀린 것은 2건이다. "아넷사 퍼펙트 UV 같은 선크림 국산으로 없어?"를 세 번 모두 검색으로 읽었다. 기준 제품은 적었지만 요청 종류를 평가로 하지 않았다. "쓸 만한 거 없어?"는 한 번 평가로 읽었다.
- "만 오천원 넘지 않는 클렌징밤"의 예산을 세 번 모두 5,000원으로 읽었다. 지금 모델은 15,000원으로 읽는다.
- 안 물어도 되는데 되물은 것이 10건으로 가장 적다(지금 모델 19건). 세트 질문에서 단계를 스스로 채워 넣는 일이 많아서다. 되묻기 정밀도가 가장 높은 이유다.
- 되물어야 하는데 안 물은 것은 15건으로 가장 많다. "하나 골라줘", "좋은 거 하나만", "나한테 맞는 거 찾아줘", "얼마야?" 같은 말에 조건을 채워 넣었다.
