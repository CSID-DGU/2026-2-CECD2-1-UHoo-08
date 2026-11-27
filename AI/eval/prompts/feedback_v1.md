# 피드백 반영 골든셋 생성 기록

`data/synthetic/feedback/feedback_v1.jsonl`(세션 20건)과 `eval/golden/scenario/feedback_v1.jsonl`(20건)을
만든 방법이다. Claude Code 가 아래 지시를 받아 `personas_v1` 과 `s2_search_v1` 의 질의로 만들었다.
평가는 `python -m eval.run_feedback_eval` 로 돈다.

## 지시

```
personas_v1 의 20명마다 피드백 세션 하나와, 그 세션에 질의 하나를 붙인 골든 레코드 하나를 만든다.

- 세션: persona_id 와 events. 이벤트는 둘 중 하나다
    {"reasons": [...]}   별로예요와 고른 이유. BE 가 보내는 TOO_EXPENSIVE, NOT_MY_SKIN, BAD_REVIEWS 만 쓴다
    {"revert": n}        n 번째(0부터) 이벤트가 만든 변경을 되돌린다
- 골든 레코드: input 에 session_id, persona_id, scenario(S2_SEARCH), raw_query, query_spec 을 적는다
- 종류를 tags 첫 항목에 적는다
  cheaper_once     더 비싸요 1번 3건
  cheaper_repeat   더 비싸요 2~3번 4건
  cheaper_mixed    더 비싸요와 다른 이유를 함께 3건
  cheaper_partial  더 비싸요는 남기고 다른 이유만 되돌림 2건
  revert_one       이유 하나를 고르고 되돌림 3건
  revert_all       여러 번 고르고 모두 되돌림 3건
  revert_mixed     이유 여럿을 고르고 모두 되돌림 2건
- 기대 성질
  - cheaper_* 는 cheaper_rank_up: 기본 결과에서 가격이 중앙값 이하인 상품의 평균 순위가 오른다
  - revert_* 는 revert_restores: 모두 되돌린 뒤의 결과 순서가 기본 결과와 같다
- split 은 페르소나의 split 을 따른다
```

## 정한 것과 그 이유

- **예산 상한이 없는 질의만 썼다.** 예산 상한이 있으면 상한 안의 상품은 예산 점수가 모두 100이라,
  예산 가중치를 올려도 저렴한 상품끼리의 순서가 바뀌지 않는다. 상한이 없으면 카테고리 가격
  중앙값과 비교하므로 저렴할수록 점수가 높다. 그래서 `s2_search_v1` 의 plain, feature 질의
  여섯 가지(수분크림, 진정 토너, 주름 세럼, 커버력 쿠션, 오래가는 틴트, 촉촉한 선크림)만 골랐다.
- **인기 기준, 다른 사람 기준, 가성비 질의는 쓰지 않았다.** 요청 플래그가 켜는 최소 가중치가
  피드백으로 바뀐 값을 덮을 수 있어, 피드백 효과와 요청 효과가 섞인다.
- **세션에는 질의를 적지 않았다.** 같은 세션을 다른 질의에 붙일 수 있게 질의는 골든 레코드에만 둔다.
- **가중치는 실제 반영과 같은 함수로 계산한다.** 러너가 `services/preference_apply` 의 이유 변환과
  합산을 그대로 쓴다. 더 비싸요 한 번은 예산 적합과 가성비 신호를 각각 0.05 올린다.
- **"이미 비슷한 걸 써요"는 넣지 않았다.** BE, FE 에서 지워진 이유라 세션에 쓰지 않는다.
  러너는 모르는 이유를 변경 없이 넘긴다.

## 결과를 읽을 때

- `cheaper_rank_up`: 지금 가성비 신호(value_signal) 점수 항목이 없어(C 작업 전) 그 가중치는 쓰이지
  않는다. 예산 적합 가중치만 올라간 효과를 잰다. 더 비싸요 한 번(+0.05)은 효과가 작아 저렴한 상품
  순위가 그대로일 수 있다. 이 실패는 반영 폭이 작다는 신호로 본다.
- `revert_restores`: 모두 되돌리면 가중치는 기본값과 똑같다. 그래도 채점의 LLM 가중치 보정이
  실행마다 조금 다를 수 있어 순서가 가끔 달라진다. 이 성질의 실패는 먼저 같은 레코드를 다시
  돌려 재현되는지 본다.
