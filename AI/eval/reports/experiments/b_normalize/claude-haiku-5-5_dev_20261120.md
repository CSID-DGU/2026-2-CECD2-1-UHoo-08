# Normalize 모델 비교: claude-haiku-5-5

- 조건: A2. LLM + 구조 규칙
- 날짜: 2026-11-20
- 문제: v2 `dev` 240건
- 모델: claude-haiku-5-5
- 부르는 곳: Anthropic API
- 모델 설정: temperature 보내지 않음 (받지 않는 모델), 생각 기능 끔, JSON 응답 프롬프트로만
- 코드: 1a5ae4b
- 반복: 1번
- 시나리오 확률 기준값: 쓰지 않음
- 막연함 확률 기준값: 쓰지 않음

## 측정값

| 항목 | 평균 | 표준편차 | 실행별 |
| --- | ---: | ---: | --- |
| 시나리오 일치율 | 99.0% | - | 99.0% |
| 요청 종류 점수(macro-F1) | 0.915 | - | 0.915 |
| 값 일치율 | 100.0% | - | 100.0% |
| 되묻기 정밀도 | 88.6% | - | 88.6% |
| 되묻기 재현율 | 81.2% | - | 81.2% |
| 양식을 못 지킨 답의 비율 | 3.3% | - | 3.3% |
| 끝내 읽지 못한 질문 비율 | 1.2% | - | 1.2% |
| 오류가 난 질문 비율 | 0.0% | - | 0.0% |
| 시나리오 확률의 오차 | - | - | - |
| 막연함 확률의 오차 | - | - | - |
| 걸린 시간 가운데 값(초) | 1.016 | - | 1.016 |
| 걸린 시간 느린 쪽 값(초) | 1.210 | - | 1.210 |
| 질문당 LLM 호출 수 | 1.021 | - | 1.021 |
| 질문당 입력 토큰 | 3514.000 | - | 3514.000 |
| 질문당 출력 토큰 | 142.192 | - | 142.192 |
| 1,000건당 비용(달러) | 0.422 | - | 0.422 |
| 반복 일치율 | - | - | - |

## 처리 비율별 시나리오 일치율

이 조건은 시나리오 확률을 내지 않는다.

## 틀린 문제 (22건)

- **router-g-1241** `value` 가성비 위주로 4만원 기초 세트 (1번 중 1번)
  - `needs_clarification` 기대 `False`, 실제 True
- **router-g-1242** `env` 건조한 요즘에 맞게 11만원 보습 세트 (1번 중 1번)
  - `needs_clarification` 기대 `False`, 실제 True
- **router-g-1248** 10만원에 맞춰서 진정 위주 루틴 짜줘 (1번 중 1번)
  - `needs_clarification` 기대 `False`, 실제 True
- **router-g-1433** `ambiguous` 좋은 제품 (1번 중 1번)
  - `needs_clarification` 기대 `True`, 실제 False
- **router-g-1434** `ambiguous` 골라줄래? (1번 중 1번)
  - `request_type` 기대 `'SEARCH'`, 실제 'REFINE'
  - `needs_clarification` 기대 `True`, 실제 False
- **router-g-1439** `ambiguous` 어제 본 거 사도 돼? (1번 중 1번)
  - `needs_clarification` 기대 `True`, 실제 False
- **router-g-1450** `ambiguous` 비싸? (1번 중 1번)
  - `needs_clarification` 기대 `True`, 실제 False
- **router-g-1562** `confusing` 닥터지 선크림 중에 뭐가 좋아? (1번 중 1번)
  - `scenario` 기대 `'S2_SEARCH'`, 실제 'S1_EVALUATE'
  - `request_type` 기대 `'SEARCH'`, 실제 'EVALUATE'
  - `needs_clarification` 기대 `False`, 실제 True
- **router-g-1564** `confusing` 더 순한 토너 없어? (1번 중 1번)
  - `request_type` 기대 `'SEARCH'`, 실제 'REFINE'
- **router-g-1565** `confusing` 이번엔 글로우한 쿠션으로 (1번 중 1번)
  - `request_type` 기대 `'SEARCH'`, 실제 'REFINE'
- **router-g-1566** `confusing` 다른 선스틱도 알려줘 (1번 중 1번)
  - `request_type` 기대 `'SEARCH'`, 실제 'REFINE'
- **router-g-1583** `confusing ambiguous` 이거 같은 느낌으로 다른 거 (1번 중 1번)
  - `needs_clarification` 기대 `True`, 실제 False
- **router-g-2241** `value` 가성비 위주로 5만원 스킨케어 세트 (1번 중 1번)
  - `needs_clarification` 기대 `False`, 실제 True
- **router-g-2434** `ambiguous` 하나만 골라줘 (1번 중 1번)
  - `request_type` 기대 `'SEARCH'`, 실제 None
- **router-g-2435** `ambiguous` 요즘 뭐가 유행이야? (1번 중 1번)
  - `needs_clarification` 기대 `True`, 실제 False
- **router-g-2439** `ambiguous` 그저께 본 거 괜찮을까? (1번 중 1번)
  - `needs_clarification` 기대 `True`, 실제 False
- **router-g-2442** `ambiguous` 그 쿠션 색 밝아? (1번 중 1번)
  - `needs_clarification` 기대 `True`, 실제 False
- **router-g-2555** `confusing` CNP 프로폴리스 앰플 같은 광채 앰플 또 뭐 있어? (1번 중 1번)
  - `scenario` 기대 `'S1_EVALUATE'`, 실제 'S2_SEARCH'
  - `request_type` 기대 `'EVALUATE'`, 실제 'SEARCH'
- **router-g-2564** `confusing` 더 촉촉한 세럼 없어? (1번 중 1번)
  - `request_type` 기대 `'SEARCH'`, 실제 'REFINE'
- **router-g-2565** `confusing` 이번엔 매트한 파운데이션으로 (1번 중 1번)
  - `request_type` 기대 `'SEARCH'`, 실제 'REFINE'
- **router-g-2566** `confusing` 다른 선로션도 알려줘 (1번 중 1번)
  - `request_type` 기대 `'SEARCH'`, 실제 'REFINE'
- **router-g-2583** `confusing ambiguous` 이거 같은 느낌으로 다른 틴트 (1번 중 1번)
  - `needs_clarification` 기대 `True`, 실제 False

## 원인과 다음 조치

- 후보 중 가장 빠르다(가운데 값 1.02초, 느린 쪽 값 1.21초).
- JSON 대신 대화하듯 답한 것이 8번이다. "하나만 골라줘", "어…", "글쎄"는 다시 물어도 같아 끝내 읽지 못했고 되묻기로 넘어갔다. JSON 으로만 답하게 하는 API 옵션이 없어 프롬프트로만 양식을 지키게 한 모델이다.
- 안 물어도 되는데 되물은 것이 5건으로 가장 적다(다른 모델은 14~19건). 세트 질문에서 단계를 스스로 채워 넣는 일이 많아서다. 되묻기 정밀도가 가장 높은 이유다.
- 되물어야 하는데 안 물은 것은 9건이다("그 쿠션 색 밝아?", "이거 같은 느낌으로 다른 틴트").
- 요청 종류만 틀린 10건 중 7건은 "더 순한 토너 없어?" 같은 말을 조건 수정으로 읽은 것이고, 시나리오는 맞는다.
