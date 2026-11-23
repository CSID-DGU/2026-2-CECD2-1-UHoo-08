# Normalize 모델 비교: qwen-plus

- 조건: A2. LLM + 구조 규칙
- 날짜: 2026-11-20
- 문제: v2 `dev` 240건
- 모델: qwen-plus
- 부르는 곳: DashScope
- 모델 설정: temperature 그대로 보냄, 생각 기능 기본으로 꺼져 있음, JSON 응답 API 옵션
- 코드: 1a5ae4b
- 반복: 1번
- 시나리오 확률 기준값: 쓰지 않음
- 막연함 확률 기준값: 쓰지 않음

## 측정값

| 항목 | 평균 | 표준편차 | 실행별 |
| --- | ---: | ---: | --- |
| 시나리오 일치율 | 99.5% | - | 99.5% |
| 요청 종류 점수(macro-F1) | 0.959 | - | 0.959 |
| 값 일치율 | 98.7% | - | 98.7% |
| 되묻기 정밀도 | 76.3% | - | 76.3% |
| 되묻기 재현율 | 93.8% | - | 93.8% |
| 양식을 못 지킨 답의 비율 | 0.0% | - | 0.0% |
| 끝내 읽지 못한 질문 비율 | 0.0% | - | 0.0% |
| 오류가 난 질문 비율 | 0.0% | - | 0.0% |
| 시나리오 확률의 오차 | - | - | - |
| 막연함 확률의 오차 | - | - | - |
| 걸린 시간 가운데 값(초) | 1.686 | - | 1.686 |
| 걸린 시간 느린 쪽 값(초) | 3.380 | - | 3.380 |
| 질문당 LLM 호출 수 | 1.000 | - | 1.000 |
| 질문당 입력 토큰 | 2442.625 | - | 2442.625 |
| 질문당 출력 토큰 | 84.388 | - | 84.388 |
| 1,000건당 비용(달러) | 1.078 | - | 1.078 |
| 반복 일치율 | - | - | - |

## 처리 비율별 시나리오 일치율

이 조건은 시나리오 확률을 내지 않는다.

## 틀린 문제 (23건)

- **router-g-1231** 7만원으로 스킨케어 세트 짜줘 (1번 중 1번)
  - `needs_clarification` 기대 `False`, 실제 True
- **router-g-1236** 4만원으로 립스틱이랑 립밤 맞춰줘 (1번 중 1번)
  - `category` 기대 `'lip'`, 실제 None
- **router-g-1239** 6만원으로 저녁 스킨케어 루틴 (1번 중 1번)
  - `needs_clarification` 기대 `False`, 실제 True
- **router-g-1241** `value` 가성비 위주로 4만원 기초 세트 (1번 중 1번)
  - `needs_clarification` 기대 `False`, 실제 True
- **router-g-1242** `env` 건조한 요즘에 맞게 11만원 보습 세트 (1번 중 1번)
  - `needs_clarification` 기대 `False`, 실제 True
- **router-g-1243** 5만원으로 아이섀도랑 마스카라 조합 (1번 중 1번)
  - `category` 기대 `'eye'`, 실제 None
- **router-g-1246** 엄마 드릴 18만원 스킨케어 세트 구성 (1번 중 1번)
  - `needs_clarification` 기대 `False`, 실제 True
- **router-g-1250** 22만원으로 안티에이징 스킨케어 세트 (1번 중 1번)
  - `needs_clarification` 기대 `False`, 실제 True
- **router-g-1441** `ambiguous` 친구가 추천한 건데 어떨까 (1번 중 1번)
  - `needs_clarification` 기대 `True`, 실제 False
- **router-g-1565** `confusing` 이번엔 글로우한 쿠션으로 (1번 중 1번)
  - `request_type` 기대 `'SEARCH'`, 실제 'REFINE'
- **router-g-1573** `confusing` 기초 전부 9만원에 맞춰서 사고 싶어 (1번 중 1번)
  - `needs_clarification` 기대 `False`, 실제 True
- **router-g-2140** 식물나라 산소수 선크림 밀림 있어? (1번 중 1번)
  - `scenario` 기대 `'S1_EVALUATE'`, 실제 'S2_SEARCH'
  - `request_type` 기대 `'EVALUATE'`, 실제 'SEARCH'
  - `base_product_ref_present` 기대 `True`, 실제 False
- **router-g-2231** 6만원으로 스킨케어 세트 구성해줘 (1번 중 1번)
  - `needs_clarification` 기대 `False`, 실제 True
- **router-g-2241** `value` 가성비 위주로 5만원 스킨케어 세트 (1번 중 1번)
  - `needs_clarification` 기대 `False`, 실제 True
- **router-g-2242** `env` 습한 요즘에 맞게 7만원 산뜻한 기초 세트 (1번 중 1번)
  - `needs_clarification` 기대 `False`, 실제 True
- **router-g-2246** 아빠 드릴 9만원 스킨케어 세트 구성 (1번 중 1번)
  - `needs_clarification` 기대 `False`, 실제 True
- **router-g-2248** 8만원에 맞춰서 수분 위주 루틴 짜줘 (1번 중 1번)
  - `needs_clarification` 기대 `False`, 실제 True
- **router-g-2250** 이십만원으로 탄력 스킨케어 세트 (1번 중 1번)
  - `needs_clarification` 기대 `False`, 실제 True
- **router-g-2439** `ambiguous` 그저께 본 거 괜찮을까? (1번 중 1번)
  - `needs_clarification` 기대 `True`, 실제 False
- **router-g-2441** `ambiguous` 동생이 쓰는 건데 어떨까 (1번 중 1번)
  - `needs_clarification` 기대 `True`, 실제 False
- **router-g-2564** `confusing` 더 촉촉한 세럼 없어? (1번 중 1번)
  - `request_type` 기대 `'SEARCH'`, 실제 'REFINE'
- **router-g-2565** `confusing` 이번엔 매트한 파운데이션으로 (1번 중 1번)
  - `request_type` 기대 `'SEARCH'`, 실제 'REFINE'
  - `category` 기대 `'base'`, 실제 None
- **router-g-2573** `confusing` 기초 전부 11만원에 맞춰서 사고 싶어 (1번 중 1번)
  - `needs_clarification` 기대 `False`, 실제 True

## 원인과 다음 조치

- 지금 서비스가 쓰는 모델이다. 다른 후보는 이 결과와 견준다.
- 시나리오를 틀린 것은 "식물나라 산소수 선크림 밀림 있어?" 하나다. 제품 이름이 있는데 검색으로 읽고 기준 제품을 비웠다.
- 안 물어도 되는데 되물은 14건은 모두 예산만 있고 세트 단계가 빈 질문이다. 모델이 아니라 되묻는 규칙에서 나온 것으로, 다른 모델에서도 비슷하게 나온다.
- 되물어야 하는데 안 물은 것은 3건으로 후보 중 가장 적다. "친구가 추천한 건데 어떨까"처럼 이름 없이 가리킨 제품을 기준 제품으로 받아들였다.
- 값을 틀린 4건 중 3건은 카테고리를 비운 것이다("4만원으로 립스틱이랑 립밤 맞춰줘").
