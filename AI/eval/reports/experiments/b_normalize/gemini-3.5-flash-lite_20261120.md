# Normalize 모델 비교: gemini-3.5-flash-lite

- 조건: A2. LLM + 구조 규칙
- 날짜: 2026-11-20
- 문제: v2 `test` 360건
- 모델: gemini-3.5-flash-lite
- 부르는 곳: Vertex AI
- 모델 설정: temperature 보내지 않음 (기본값 권장), 생각 기능 가장 낮은 단계 (MINIMAL), JSON 응답 API 옵션
- 코드: 2fd22c7
- 반복: 3번
- 시나리오 확률 기준값: 쓰지 않음
- 막연함 확률 기준값: 쓰지 않음

## 측정값

| 항목 | 평균 | 표준편차 | 실행별 |
| --- | ---: | ---: | --- |
| 시나리오 일치율 | 99.4% | 0.3% | 99.0%, 99.4%, 99.7% |
| 요청 종류 점수(macro-F1) | 0.960 | 0.002 | 0.958, 0.959, 0.962 |
| 값 일치율 | 99.7% | 0.5% | 99.2%, 100.0%, 100.0% |
| 되묻기 정밀도 | 70.1% | 0.3% | 69.9%, 70.5%, 69.9% |
| 되묻기 재현율 | 87.3% | 3.4% | 85.3%, 91.2%, 85.3% |
| 양식을 못 지킨 답의 비율 | 0.4% | 0.4% | 0.8%, 0.3%, 0.0% |
| 끝내 읽지 못한 질문 비율 | 0.1% | 0.2% | 0.3%, 0.0%, 0.0% |
| 오류가 난 질문 비율 | 0.0% | 0.0% | 0.0%, 0.0%, 0.0% |
| 시나리오 확률의 오차 | - | - | -, -, - |
| 막연함 확률의 오차 | - | - | -, -, - |
| 걸린 시간 가운데 값(초) | 1.048 | 0.009 | 1.059, 1.042, 1.043 |
| 걸린 시간 느린 쪽 값(초) | 1.370 | 0.081 | 1.464, 1.323, 1.323 |
| 질문당 LLM 호출 수 | 1.003 | 0.003 | 1.006, 1.003, 1.000 |
| 질문당 입력 토큰 | 2344.636 | 6.511 | 2351.150, 2344.631, 2338.128 |
| 질문당 출력 토큰 | 142.967 | 0.181 | 143.131, 142.997, 142.772 |
| 1,000건당 비용(달러) | 1.061 | 0.002 | 1.063, 1.061, 1.058 |
| 반복 일치율 | 97.5% | - | - |

## 처리 비율별 시나리오 일치율

이 조건은 시나리오 확률을 내지 않는다.

## 틀린 문제 (43건)

- **router-g-1202** 12만원 예산으로 스킨케어 루틴 짜줘 (3번 중 3번)
  - `needs_clarification` 기대 `False`, 실제 True
- **router-g-1204** 20만원으로 기초 라인 한 번에 맞추고 싶어 (3번 중 3번)
  - `needs_clarification` 기대 `False`, 실제 True
- **router-g-1208** 지성 피부인데 10만원으로 스킨케어 세트 짜줘 (3번 중 3번)
  - `needs_clarification` 기대 `False`, 실제 True
- **router-g-1214** `value` 가성비로 6만원 스킨케어 세트 구성 (3번 중 3번)
  - `needs_clarification` 기대 `False`, 실제 True
- **router-g-1215** `env` 요즘 날씨에 맞춰 9만원으로 스킨케어 세트 (3번 중 3번)
  - `needs_clarification` 기대 `False`, 실제 True
- **router-g-1218** 건성 피부 겨울 루틴 11만원으로 짜줘 (3번 중 3번)
  - `needs_clarification` 기대 `False`, 실제 True
- **router-g-1221** 18만원으로 스킨케어 4단계 구성해줘 (3번 중 3번)
  - `needs_clarification` 기대 `False`, 실제 True
- **router-g-1222** 친구 선물용으로 8만원 스킨케어 세트 짜줘 (3번 중 3번)
  - `needs_clarification` 기대 `False`, 실제 True
- **router-g-1223** 6만원 안에서 블러셔랑 하이라이터 같이 추천 (3번 중 1번)
  - `category` 기대 `'cheek'`, 실제 None
- **router-g-1225** 14만원으로 아침 스킨케어 루틴 만들어줘 (3번 중 3번)
  - `needs_clarification` 기대 `False`, 실제 True
- **router-g-1227** 트러블 피부용으로 10만원 진정 루틴 짜줘 (3번 중 3번)
  - `needs_clarification` 기대 `False`, 실제 True
- **router-g-1229** `value` 저렴하게 5만원으로 기초 세 가지 맞춰줘 (3번 중 3번)
  - `needs_clarification` 기대 `False`, 실제 True
- **router-g-1304** 향 없는 걸로만 (3번 중 3번)
  - `request_type` 기대 `'REFINE'`, 실제 'SEARCH'
- **router-g-1409** `ambiguous` 선물할 건데 뭐가 좋아? (3번 중 2번)
  - `needs_clarification` 기대 `True`, 실제 False
- **router-g-1410** `ambiguous` 예쁜 거 (3번 중 3번)
  - `needs_clarification` 기대 `True`, 실제 False
- **router-g-1411** `ambiguous` 이거 써도 돼? (3번 중 1번)
  - `needs_clarification` 기대 `True`, 실제 False
- **router-g-1413** `ambiguous` 저번에 산 거 나한테 맞는 거야? (3번 중 3번)
  - `needs_clarification` 기대 `True`, 실제 False
- **router-g-1418** `ambiguous` 언니가 준 크림인데 써도 될까 (3번 중 1번)
  - `needs_clarification` 기대 `True`, 실제 False
- **router-g-1419** `ambiguous` 방금 그거 성분 괜찮아? (3번 중 1번)
  - `needs_clarification` 기대 `True`, 실제 False
- **router-g-1522** `confusing` 더 저렴한 쿠션 없어? (3번 중 3번)
  - `request_type` 기대 `'SEARCH'`, 실제 'REFINE'
- **router-g-1537** `confusing` 기초 다 떨어졌는데 7만원으로 한꺼번에 사려고 (3번 중 3번)
  - `needs_clarification` 기대 `False`, 실제 True
- **router-g-2202** 9만 원 예산으로 저녁 스킨케어 루틴 구성 (3번 중 3번)
  - `needs_clarification` 기대 `False`, 실제 True
- **router-g-2204** 17만원으로 기초 한 번에 싹 바꾸고 싶어 (3번 중 3번)
  - `needs_clarification` 기대 `False`, 실제 True
- **router-g-2208** 건성인데 12만원으로 보습 세트 짜줘 (3번 중 3번)
  - `needs_clarification` 기대 `False`, 실제 True
- **router-g-2214** `value` 가성비 좋게 8만원 기초 세트 구성 (3번 중 3번)
  - `needs_clarification` 기대 `False`, 실제 True
- **router-g-2215** `env` 요즘 건조한 날씨에 맞게 10만원 스킨케어 세트 (3번 중 3번)
  - `needs_clarification` 기대 `False`, 실제 True
- **router-g-2218** 지성 피부 여름 루틴 9만원으로 짜줘 (3번 중 3번)
  - `needs_clarification` 기대 `False`, 실제 True
- **router-g-2221** 15만원으로 스킨케어 3단계 구성해줘 (3번 중 3번)
  - `needs_clarification` 기대 `False`, 실제 True
- **router-g-2222** 엄마 선물로 13만원 스킨케어 세트 짜줘 (3번 중 3번)
  - `needs_clarification` 기대 `False`, 실제 True
- **router-g-2223** 4만원 안에서 블러셔랑 쉐딩 같이 추천 (3번 중 1번)
  - `category` 기대 `'cheek'`, 실제 None
- **router-g-2225** 19만원으로 저녁 안티에이징 루틴 만들어줘 (3번 중 3번)
  - `scenario` 기대 `'S6_BUNDLE'`, 실제 'S2_SEARCH'
  - `request_type` 기대 `'BUNDLE'`, 실제 None
  - `needs_clarification` 기대 `False`, 실제 True
  - `category` 기대 `'skincare'`, 실제 None
  - `budget_total` 기대 `190000`, 실제 None
- **router-g-2227** 민감성 피부용으로 11만원 저자극 루틴 짜줘 (3번 중 3번)
  - `needs_clarification` 기대 `False`, 실제 True
- **router-g-2229** 알뜰하게 4만원으로 기초 두 가지 맞춰줘 (3번 중 2번)
  - `needs_clarification` 기대 `False`, 실제 True
- **router-g-2305** 커버력은 좀 낮아도 되니까 가벼운 걸로 (3번 중 3번)
  - `request_type` 기대 `'REFINE'`, 실제 'SEARCH'
- **router-g-2408** `ambiguous` 내 피부에 맞는 걸로 (3번 중 1번)
  - `needs_clarification` 기대 `True`, 실제 False
- **router-g-2409** `ambiguous` 생일 선물 뭐가 좋을까 (3번 중 3번)
  - `needs_clarification` 기대 `True`, 실제 False
- **router-g-2410** `ambiguous` 무난한 거 (3번 중 3번)
  - `needs_clarification` 기대 `True`, 실제 False
- **router-g-2413** `ambiguous` 지난주에 산 거 계속 써도 돼? (3번 중 3번)
  - `needs_clarification` 기대 `True`, 실제 False
- **router-g-2418** `ambiguous` 엄마가 쓰던 에센스인데 나도 써도 될까 (3번 중 2번)
  - `needs_clarification` 기대 `True`, 실제 False
- **router-g-2430** `ambiguous` 가격은? (3번 중 3번)
  - `needs_clarification` 기대 `True`, 실제 False
- **router-g-2518** `confusing` 지성한테 젤크림 어때? (3번 중 3번)
  - `scenario` 기대 `'S2_SEARCH'`, 실제 'S1_EVALUATE'
  - `request_type` 기대 `'SEARCH'`, 실제 'EVALUATE'
  - `needs_clarification` 기대 `False`, 실제 True
- **router-g-2522** `confusing` 더 가벼운 파운데이션 없어? (3번 중 2번)
  - `scenario` 기대 `'S2_SEARCH'`, 실제 'S1_EVALUATE'
  - `request_type` 기대 `'SEARCH'`, 실제 'EVALUATE'
  - `needs_clarification` 기대 `False`, 실제 True
- **router-g-2537** `confusing` 이사하면서 화장품 다 버렸는데 8만원으로 기초 한꺼번에 사려고 (3번 중 3번)
  - `needs_clarification` 기대 `False`, 실제 True

## 원인과 다음 조치

- 한 번이라도 틀린 문제는 43건이다.
- 안 물어도 되는데 되물은 것이 26건으로 가장 많다. 24건이 예산만 있고 세트 단계가 빈 질문이다.
- 시나리오를 틀린 것은 3건이다. "지성한테 젤크림 어때?"(세 번)와 "더 가벼운 파운데이션 없어?"(두 번)를 평가로 읽었다. "19만원으로 저녁 안티에이징 루틴 만들어줘"는 한 번 답을 읽지 못해 검색으로 남았다.
- JSON 응답 옵션을 켰는데도 JSON 이 깨진 답이 4번 나왔다. 값 사이에 `.output` 같은 코드 조각이 끼어 있었다. 위의 세트 질문과 "라운드랩 독도 토너랑 아누아 어성초 토너 중에 뭐가 나아?" 두 문제에서 나왔다.
- 되물어야 하는데 안 물은 것은 12건으로 지금 모델(11건)과 비슷하다.
- 값을 틀린 것 중 2건은 "블러셔랑 하이라이터", "블러셔랑 쉐딩"에서 카테고리를 비운 것이다.
