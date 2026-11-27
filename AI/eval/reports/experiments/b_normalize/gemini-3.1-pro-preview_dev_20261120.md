# Normalize 모델 비교: gemini-3.1-pro-preview

- 조건: A2. LLM + 구조 규칙
- 날짜: 2026-11-20
- 문제: v2 `dev` 240건
- 모델: gemini-3.1-pro-preview
- 부르는 곳: Vertex AI
- 모델 설정: temperature 보내지 않음 (기본값 권장), 생각 기능 가장 낮은 단계 (LOW), JSON 응답 API 옵션
- 코드: 1a5ae4b
- 반복: 1번
- 시나리오 확률 기준값: 쓰지 않음
- 막연함 확률 기준값: 쓰지 않음

## 측정값

| 항목 | 평균 | 표준편차 | 실행별 |
| --- | ---: | ---: | --- |
| 시나리오 일치율 | 99.5% | - | 99.5% |
| 요청 종류 점수(macro-F1) | 0.940 | - | 0.940 |
| 값 일치율 | 99.7% | - | 99.7% |
| 되묻기 정밀도 | 69.5% | - | 69.5% |
| 되묻기 재현율 | 85.4% | - | 85.4% |
| 양식을 못 지킨 답의 비율 | 7.0% | - | 7.0% |
| 끝내 읽지 못한 질문 비율 | 0.4% | - | 0.4% |
| 오류가 난 질문 비율 | 0.4% | - | 0.4% |
| 시나리오 확률의 오차 | - | - | - |
| 막연함 확률의 오차 | - | - | - |
| 걸린 시간 가운데 값(초) | 3.990 | - | 3.990 |
| 걸린 시간 느린 쪽 값(초) | 11.769 | - | 11.769 |
| 질문당 LLM 호출 수 | 1.071 | - | 1.071 |
| 질문당 입력 토큰 | 2492.529 | - | 2492.529 |
| 질문당 출력 토큰 | 287.242 | - | 287.242 |
| 1,000건당 비용(달러) | 8.432 | - | 8.432 |
| 반복 일치율 | - | - | - |

## 처리 비율별 시나리오 일치율

이 조건은 시나리오 확률을 내지 않는다.

## 틀린 문제 (31건)

- **router-g-1231** 7만원으로 스킨케어 세트 짜줘 (1번 중 1번)
  - `needs_clarification` 기대 `False`, 실제 True
- **router-g-1237** 20만원 스킨케어 풀 루틴 추천 (1번 중 1번)
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
- **router-g-1433** `ambiguous` 좋은 제품 (1번 중 1번)
  - `needs_clarification` 기대 `True`, 실제 False
- **router-g-1439** `ambiguous` 어제 본 거 사도 돼? (1번 중 1번)
  - `needs_clarification` 기대 `True`, 실제 False
- **router-g-1450** `ambiguous` 비싸? (1번 중 1번)
  - `needs_clarification` 기대 `True`, 실제 False
- **router-g-1564** `confusing` 더 순한 토너 없어? (1번 중 1번)
  - `request_type` 기대 `'SEARCH'`, 실제 'REFINE'
- **router-g-1565** `confusing` 이번엔 글로우한 쿠션으로 (1번 중 1번)
  - `request_type` 기대 `'SEARCH'`, 실제 'REFINE'
- **router-g-1566** `confusing` 다른 선스틱도 알려줘 (1번 중 1번)
  - `request_type` 기대 `'SEARCH'`, 실제 'REFINE'
- **router-g-1573** `confusing` 기초 전부 9만원에 맞춰서 사고 싶어 (1번 중 1번)
  - `needs_clarification` 기대 `False`, 실제 True
- **router-g-2048** 다크닝 없는 쿠션 추천 (1번 중 1번)
  - `실행` 기대 `None`, 실제 'ClientError("429 RESOURCE_EXHAUSTED. {\'error\': {\'code\': 429, \'message\': \'Resource exhausted. Please try again later. Please refer to https://cloud.google.com/vertex-ai/generative-ai/docs/error-code-429 for more details.\', \'status\': \'RESOURCE_EXHAUSTED\'}}")'
- **router-g-2231** 6만원으로 스킨케어 세트 구성해줘 (1번 중 1번)
  - `needs_clarification` 기대 `False`, 실제 True
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
- **router-g-2248** 8만원에 맞춰서 수분 위주 루틴 짜줘 (1번 중 1번)
  - `needs_clarification` 기대 `False`, 실제 True
- **router-g-2250** 이십만원으로 탄력 스킨케어 세트 (1번 중 1번)
  - `needs_clarification` 기대 `False`, 실제 True
- **router-g-2433** `ambiguous` 괜찮은 제품 (1번 중 1번)
  - `needs_clarification` 기대 `True`, 실제 False
- **router-g-2439** `ambiguous` 그저께 본 거 괜찮을까? (1번 중 1번)
  - `needs_clarification` 기대 `True`, 실제 False
- **router-g-2443** `ambiguous` 그거랑 비슷한 걸로 (1번 중 1번)
  - `needs_clarification` 기대 `True`, 실제 False
- **router-g-2450** `ambiguous` 얼마쯤 해? (1번 중 1번)
  - `needs_clarification` 기대 `True`, 실제 False
- **router-g-2564** `confusing` 더 촉촉한 세럼 없어? (1번 중 1번)
  - `request_type` 기대 `'SEARCH'`, 실제 'REFINE'
- **router-g-2565** `confusing` 이번엔 매트한 파운데이션으로 (1번 중 1번)
  - `request_type` 기대 `'SEARCH'`, 실제 'REFINE'
- **router-g-2573** `confusing` 기초 전부 11만원에 맞춰서 사고 싶어 (1번 중 1번)
  - `needs_clarification` 기대 `False`, 실제 True

## 원인과 다음 조치

- 결제 계정을 정식 계정으로 바꾼 뒤 다시 돌린 결과다. 무료 체험 계정에서는 열 번에 한 번꼴로 403(유료 결제 계정이 필요하다는 오류)이 났다.
- 답을 배열로 감싸 보내 읽지 못한 것이 18번이다. 한 번 더 물으면 대부분 읽히지만 "글쎄"는 끝내 읽지 못했다.
- 호출 한도(429)에 걸려 한 질문은 답을 받지 못했고, 17건이 10초를 넘겼다.
- 후보 중 가장 느리고(가운데 값 3.99초) 비용은 지금 모델의 7.8배다.
