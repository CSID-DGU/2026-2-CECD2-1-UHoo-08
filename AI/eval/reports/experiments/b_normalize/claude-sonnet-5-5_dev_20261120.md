# Normalize 모델 비교: claude-sonnet-5-5

- 조건: A2. LLM + 구조 규칙
- 날짜: 2026-11-20
- 문제: v2 `dev` 240건
- 모델: claude-sonnet-5-5
- 부르는 곳: Anthropic API
- 모델 설정: temperature 보내지 않음 (받지 않는 모델), 생각 기능 끔, JSON 응답 프롬프트로만
- 코드: 1a5ae4b
- 반복: 1번
- 시나리오 확률 기준값: 쓰지 않음
- 막연함 확률 기준값: 쓰지 않음

## 측정값

| 항목 | 평균 | 표준편차 | 실행별 |
| --- | ---: | ---: | --- |
| 시나리오 일치율 | 100.0% | - | 100.0% |
| 요청 종류 점수(macro-F1) | 0.942 | - | 0.942 |
| 값 일치율 | 100.0% | - | 100.0% |
| 되묻기 정밀도 | 72.4% | - | 72.4% |
| 되묻기 재현율 | 87.5% | - | 87.5% |
| 양식을 못 지킨 답의 비율 | 0.0% | - | 0.0% |
| 끝내 읽지 못한 질문 비율 | 0.0% | - | 0.0% |
| 오류가 난 질문 비율 | 0.0% | - | 0.0% |
| 시나리오 확률의 오차 | - | - | - |
| 막연함 확률의 오차 | - | - | - |
| 걸린 시간 가운데 값(초) | 1.906 | - | 1.906 |
| 걸린 시간 느린 쪽 값(초) | 3.314 | - | 3.314 |
| 질문당 LLM 호출 수 | 1.000 | - | 1.000 |
| 질문당 입력 토큰 | 3442.533 | - | 3442.533 |
| 질문당 출력 토큰 | 128.375 | - | 128.375 |
| 1,000건당 비용(달러) | 8.169 | - | 8.169 |
| 반복 일치율 | - | - | - |

## 처리 비율별 시나리오 일치율

이 조건은 시나리오 확률을 내지 않는다.

## 틀린 문제 (26건)

- **router-g-1231** 7만원으로 스킨케어 세트 짜줘 (1번 중 1번)
  - `needs_clarification` 기대 `False`, 실제 True
- **router-g-1239** 6만원으로 저녁 스킨케어 루틴 (1번 중 1번)
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
- **router-g-1439** `ambiguous` 어제 본 거 사도 돼? (1번 중 1번)
  - `needs_clarification` 기대 `True`, 실제 False
- **router-g-1564** `confusing` 더 순한 토너 없어? (1번 중 1번)
  - `request_type` 기대 `'SEARCH'`, 실제 'REFINE'
- **router-g-1565** `confusing` 이번엔 글로우한 쿠션으로 (1번 중 1번)
  - `request_type` 기대 `'SEARCH'`, 실제 'REFINE'
- **router-g-1573** `confusing` 기초 전부 9만원에 맞춰서 사고 싶어 (1번 중 1번)
  - `needs_clarification` 기대 `False`, 실제 True
- **router-g-1583** `confusing ambiguous` 이거 같은 느낌으로 다른 거 (1번 중 1번)
  - `needs_clarification` 기대 `True`, 실제 False
- **router-g-2231** 6만원으로 스킨케어 세트 구성해줘 (1번 중 1번)
  - `needs_clarification` 기대 `False`, 실제 True
- **router-g-2239** 5만원으로 아침 스킨케어 루틴 (1번 중 1번)
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
- **router-g-2434** `ambiguous` 하나만 골라줘 (1번 중 1번)
  - `request_type` 기대 `'SEARCH'`, 실제 'REFINE'
  - `needs_clarification` 기대 `True`, 실제 False
- **router-g-2439** `ambiguous` 그저께 본 거 괜찮을까? (1번 중 1번)
  - `needs_clarification` 기대 `True`, 실제 False
- **router-g-2443** `ambiguous` 그거랑 비슷한 걸로 (1번 중 1번)
  - `needs_clarification` 기대 `True`, 실제 False
- **router-g-2448** `ambiguous` 전부 새로 사고 싶어 (1번 중 1번)
  - `needs_clarification` 기대 `True`, 실제 False
- **router-g-2564** `confusing` 더 촉촉한 세럼 없어? (1번 중 1번)
  - `request_type` 기대 `'SEARCH'`, 실제 'REFINE'
- **router-g-2565** `confusing` 이번엔 매트한 파운데이션으로 (1번 중 1번)
  - `request_type` 기대 `'SEARCH'`, 실제 'REFINE'
- **router-g-2573** `confusing` 기초 전부 11만원에 맞춰서 사고 싶어 (1번 중 1번)
  - `needs_clarification` 기대 `False`, 실제 True

## 원인과 다음 조치

- 시나리오와 값을 모두 맞혔고 양식을 어긴 답도 없다.
- 안 물어도 되는데 되물은 16건은 모두 예산만 있고 세트 단계가 빈 질문이다. 모델이 아니라 되묻는 규칙에서 나온 것으로, 다른 모델에서도 비슷하게 나온다.
- 되물어야 하는데 안 물은 것은 6건이다("어제 본 거 사도 돼?", "그거랑 비슷한 걸로").
- 비용이 지금 모델의 7.6배다.
