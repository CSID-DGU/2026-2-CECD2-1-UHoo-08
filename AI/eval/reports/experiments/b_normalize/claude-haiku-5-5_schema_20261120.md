# Normalize 모델 비교: claude-haiku-5-5

- 조건: A2. LLM + 구조 규칙
- 날짜: 2026-11-20
- 문제: v2 `test` 360건
- 모델: claude-haiku-5-5
- 부르는 곳: Anthropic API
- 모델 설정: temperature 보내지 않음 (받지 않는 모델), 생각 기능 끔, JSON 응답 스키마로 강제 (구조화 출력)
- 코드: d3687b0
- 반복: 3번
- 시나리오 확률 기준값: 쓰지 않음
- 막연함 확률 기준값: 쓰지 않음

## 측정값

| 항목 | 평균 | 표준편차 | 실행별 |
| --- | ---: | ---: | --- |
| 시나리오 일치율 | 99.2% | 0.2% | 99.0%, 99.0%, 99.4% |
| 요청 종류 점수(macro-F1) | 0.945 | 0.001 | 0.944, 0.944, 0.947 |
| 값 일치율 | 99.8% | 0.0% | 99.8%, 99.8%, 99.8% |
| 되묻기 정밀도 | 96.0% | 0.9% | 96.6%, 96.4%, 94.9% |
| 되묻기 재현율 | 81.4% | 1.7% | 82.4%, 79.4%, 82.4% |
| 양식을 못 지킨 답의 비율 | 0.0% | 0.0% | 0.0%, 0.0%, 0.0% |
| 끝내 읽지 못한 질문 비율 | 0.0% | 0.0% | 0.0%, 0.0%, 0.0% |
| 오류가 난 질문 비율 | 0.0% | 0.0% | 0.0%, 0.0%, 0.0% |
| 시나리오 확률의 오차 | - | - | -, -, - |
| 막연함 확률의 오차 | - | - | -, -, - |
| 걸린 시간 가운데 값(초) | 1.195 | 0.016 | 1.204, 1.204, 1.176 |
| 걸린 시간 느린 쪽 값(초) | 1.508 | 0.137 | 1.666, 1.428, 1.432 |
| 질문당 LLM 호출 수 | 1.000 | 0.000 | 1.000, 1.000, 1.000 |
| 질문당 입력 토큰 | 4936.853 | 0.000 | 4936.853, 4936.853, 4936.853 |
| 질문당 출력 토큰 | 139.019 | 0.223 | 139.122, 138.764, 139.172 |
| 1,000건당 비용(달러) | 0.563 | 0.000 | 0.563, 0.563, 0.563 |
| 반복 일치율 | 98.1% | - | - |

## 처리 비율별 시나리오 일치율

이 조건은 시나리오 확률을 내지 않는다.

## 틀린 문제 (25건)

- **router-g-1215** `env` 요즘 날씨에 맞춰 9만원으로 스킨케어 세트 (3번 중 1번)
  - `needs_clarification` 기대 `False`, 실제 True
- **router-g-1402** `ambiguous` 하나 골라줘 (3번 중 3번)
  - `request_type` 기대 `'SEARCH'`, 실제 'REFINE'
  - `needs_clarification` 기대 `True`, 실제 False
- **router-g-1404** `ambiguous` 요즘 뭐 사야 돼? (3번 중 2번)
  - `needs_clarification` 기대 `True`, 실제 False
- **router-g-1407** `ambiguous` 쓸 만한 거 없어? (3번 중 3번)
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
- **router-g-1430** `ambiguous` 얼마야? (3번 중 2번)
  - `needs_clarification` 기대 `True`, 실제 False
- **router-g-1522** `confusing` 더 저렴한 쿠션 없어? (3번 중 3번)
  - `request_type` 기대 `'SEARCH'`, 실제 'REFINE'
- **router-g-1524** `confusing` 이번엔 매트한 립스틱으로 찾아줘 (3번 중 3번)
  - `request_type` 기대 `'SEARCH'`, 실제 'REFINE'
- **router-g-1525** `confusing` 다른 세럼도 보여줘 (3번 중 3번)
  - `request_type` 기대 `'SEARCH'`, 실제 'REFINE'
- **router-g-2011** 만 오천원 넘지 않는 클렌징밤 (3번 중 3번)
  - `budget_max` 기대 `15000`, 실제 5000
- **router-g-2215** `env` 요즘 건조한 날씨에 맞게 10만원 스킨케어 세트 (3번 중 1번)
  - `needs_clarification` 기대 `False`, 실제 True
- **router-g-2402** `ambiguous` 좋은 거 하나만 (3번 중 3번)
  - `needs_clarification` 기대 `True`, 실제 False
- **router-g-2408** `ambiguous` 내 피부에 맞는 걸로 (3번 중 3번)
  - `needs_clarification` 기대 `True`, 실제 False
- **router-g-2409** `ambiguous` 생일 선물 뭐가 좋을까 (3번 중 3번)
  - `needs_clarification` 기대 `True`, 실제 False
- **router-g-2410** `ambiguous` 무난한 거 (3번 중 3번)
  - `needs_clarification` 기대 `True`, 실제 False
- **router-g-2415** `ambiguous` 인스타에서 본 건데 살 만해? (3번 중 3번)
  - `needs_clarification` 기대 `True`, 실제 False
- **router-g-2418** `ambiguous` 엄마가 쓰던 에센스인데 나도 써도 될까 (3번 중 3번)
  - `needs_clarification` 기대 `True`, 실제 False
- **router-g-2505** `confusing` 아넷사 퍼펙트 UV 같은 선크림 국산으로 없어? (3번 중 2번)
  - `scenario` 기대 `'S1_EVALUATE'`, 실제 'S2_SEARCH'
  - `request_type` 기대 `'EVALUATE'`, 실제 'SEARCH'
- **router-g-2518** `confusing` 지성한테 젤크림 어때? (3번 중 3번)
  - `scenario` 기대 `'S2_SEARCH'`, 실제 'S1_EVALUATE'
  - `request_type` 기대 `'SEARCH'`, 실제 'EVALUATE'
  - `needs_clarification` 기대 `False`, 실제 True
- **router-g-2522** `confusing` 더 가벼운 파운데이션 없어? (3번 중 3번)
  - `request_type` 기대 `'SEARCH'`, 실제 'REFINE'
- **router-g-2537** `confusing` 이사하면서 화장품 다 버렸는데 8만원으로 기초 한꺼번에 사려고 (3번 중 2번)
  - `needs_clarification` 기대 `False`, 실제 True

## 원인과 다음 조치

- 같은 모델을 답의 스키마까지 강제해(구조화 출력) 다시 잰 결과다. 프롬프트로만 양식을 지키게 한 결과는 `claude-haiku-5-5_20261120.md` 에 있다.
- 양식을 못 지킨 답이 없어졌다(3.3% → 0%). "흠", "몰라", "다른 브랜드로"에도 한 번에 JSON 으로 답했고, 질문당 호출 수가 1.02 에서 1.00 이 됐다.
- 입력 토큰이 질문당 3,512 에서 4,937 로 늘었다. 스키마 설명이 입력에 붙기 때문이다. 1,000건당 비용은 0.42달러에서 0.56달러가 됐다.
- 시간은 가운데 값 1.20초, 느린 쪽 값 1.51초다. 앞선 측정(1.00초, 1.19초)과는 다른 시간대에 쟀다. 같은 시각에 스키마를 붙인 호출과 안 붙인 호출을 번갈아 30건씩 불러 보면 스키마 쪽이 가운데 값으로 0.07초 느리다.
- 안 물어도 되는데 되물은 것이 10건에서 4건으로 줄었다. 세트 질문에서 단계를 채운 답이 228개 중 208개에서 224개로 늘어서다. 되묻기 정밀도가 96.0% 가 됐다.
- 되물어야 하는데 안 물은 것은 14건으로 앞선 측정(15건)과 비슷하다. "하나 골라줘", "무난한 거", "선물할 건데 뭐가 좋아?" 같은 말에 조건을 채워 넣는다.
- 시나리오를 틀린 것은 3건이다. "쓸 만한 거 없어?"와 "지성한테 젤크림 어때?"를 세 번 모두 평가로, "아넷사 퍼펙트 UV 같은 선크림 국산으로 없어?"를 두 번 검색으로 읽었다. 앞선 측정과 한두 문제 차이다.
- "만 오천원 넘지 않는 클렌징밤"의 예산은 여전히 5,000원으로 읽는다.
- 묻지 않은 참거짓 특징을 false 로 적는 일이 늘었다. 답 1,080개 중 31개에서 fragrance_free, waterproof, white_cast 를 false 로 적었다(앞선 측정 4개). "여름용 산뜻한 수분크림"에 waterproof false 를 적는 식이다. 그 카테고리의 특징 표에 없는 키를 적은 답도 3개에서 23개로 늘었다. 스키마에는 특징 키가 카테고리 구분 없이 한 목록으로 열려 있다. 지금 측정 항목은 특징을 채점하지 않아 위 수치에는 드러나지 않는다.
