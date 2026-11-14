# scenario_v1 생성 기록

`eval/golden/scenario/s2_search_v1.jsonl`(60건)과 `s1_evaluate_v1.jsonl`(20건)을 만든 방법이다.
Claude Code 가 아래 지시를 받아, `personas_v1` 과 읽기 전용으로 조회한 상품 마스터로 만들었다.
고정 시드는 20261114 다.

## 지시

```
personas_v1 의 20명으로 추천 경로 골든셋을 만든다.

상품 검색(S2_SEARCH)
- 페르소나마다 질의 3개, 모두 60개
- 질의 종류를 tags 첫 항목에 적는다
  plain 일반, feature 특징 조건, value 가성비, env 요즘 날씨, popular 전체 인기,
  other 다른 사람 기준, budget 제품 하나 예산 상한
- value, env, popular, other 는 각각 5개 이상
- 페르소나 특성에 맞춘다
  popular_user 는 인기 질의 2개, budget_tight 는 예산과 가성비 질의,
  conflict_pending 은 스킨케어 질의를 하나 이상
- 질의 해석(query_spec)은 사람이 그 문장을 읽고 채울 값만 적는다. 제품 종류는
  features.product_type 에 둔다
- other 는 basis 를 OTHER 로, 받을 사람 조건을 target_profile 에 화면 필드 이름
  (skinType, skinConcerns, personalColor)과 BE 값으로 적는다

상품 평가(S1_EVALUATE)
- 페르소나마다 1개, 모두 20개
- 기준 상품은 그 사람이 보유하지 않은, 가격과 제품 종류가 있는 실제 상품
- 카테고리는 skincare, sun, base, lip 을 돌아가며

기대 성질은 순위가 아니라 성질로 적는다. 쓸 수 있는 키는 eval/scenario_checks.py 의 것뿐이다.
- 모든 레코드: 보유 제품은 결과에 없다(must_exclude), 결과가 비어 있지 않다
- 상위 5개는 카테고리, 제품 종류, 예산 상한을 지킨다(top5_all)
- value: value_signal 점수 항목과 VALUE 배지
- env: env_fit 점수 항목과 ENV 배지
- popular: popularity 가 있고 personalization 이 없다
- popular 가 아니면 popularity 가 없다
- feature: query_fit, budget: budget_fit
- other: personalization (립은 퍼스널 컬러가 있는 상품이 적어 뺀다)
- 상품 평가: 대체 후보가 있고 모두 50점 이상

split 은 페르소나의 split 을 따른다. test 페르소나 6명의 레코드가 test 다.
```

## 정한 것과 그 이유

- **충돌 사유는 아직 적지 않았다.** 성분 충돌 규칙(`ingredient_conflict_rules`)이 비어 있어서,
  어떤 상품이 CONFLICT 로 빠져야 하는지 정할 수 없다. 충돌 보유자 레코드에는 `conflict_pending`
  태그만 남겼다. B 규칙이 들어오면 `personas_v2` 와 함께 `must_exclude_reason` 을 넣은 v2 를 만든다.
- **보유 제품은 OWNED 사유가 아니라 결과에 없는지만 본다.** 보유 제품이 검색 후보에
  들어오지 않으면 제외 목록에도 없으므로, 사유까지 기대하면 맞게 동작해도 실패로 나온다.
- **개인화 항목은 어느 레코드에도 기대하지 않는다.** 지시에는 other 에 개인화 항목을 적으라고
  했지만, 상품 특징에 피부 타입이나 퍼스널 컬러가 없으면 개인화 점수가 비는 것이 맞는 동작이다.
  상위 1개가 그런 상품이면 맞게 동작해도 실패로 나오므로 리뷰 뒤 other 레코드 8건에서 뺐다.
  other 는 popularity 가 없는지(breakdown_lacks)로 본다.
- **조건을 만족하는 상품이 5개 이상인 질의만 썼다.** 생성할 때 상품 마스터에서 카테고리,
  제품 종류, 예산 상한, 보유 제품 제외를 모두 지키는 상품 수를 세어 확인했다.

## 아직 통과할 수 없는 성질

다음은 다른 파트 작업이 들어와야 통과한다. 경로가 지켜야 할 성질이라 미리 적어 둔다.

- `value_signal`, VALUE 배지: C 의 가성비 신호
- `env_fit`, ENV 배지: B 의 환경 기록
- 상품 평가 전체: 상품 평가 경로(A-09)
