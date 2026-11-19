# 홈 루틴 골든셋 생성 기록

`eval/golden/scenario/home_routine_v1.jsonl`(7건)을 만든 방법이다. Claude Code 가 아래 지시를 받아
`personas_v1` 의 보유 제품(상품 id, 별점, 개봉일)으로 만들었다.
평가는 시나리오 러너(`python -m eval.run_scenario_eval`)가 다른 시나리오와 함께 돈다.

## 지시

```
보유 제품이 4개 이상인 페르소나 7명마다 홈 루틴(HOME_ROUTINE) 레코드를 하나씩 만든다.
성분 충돌 페르소나(conflict_pending) 5명을 모두 넣는다.

- input 에 persona_id, scenario, routine_pairs 를 적는다. 질의는 없다
- routine_pairs 는 그 페르소나 보유 제품의 상품 id 로 적은 궁합 쌍 {a, b, level} 이다
  level 은 OK, SEPARATE, AVOID 중 하나다
- 종류를 tags 첫 항목에 적는다
  most_avoid   AVOID 쌍에 가장 많이 나온 제품이 하나 2건
  rating       AVOID 횟수가 같고 별점으로 갈림 2건
  opened_at    AVOID 횟수와 별점이 같고 개봉일로 갈림 2건
  no_avoid     AVOID 쌍이 없음 1건
- 기대 성질
  - replace_target_in: 바꿀 제품의 상품 id. graph/nodes/alternative.py 의 고르기 규칙
    (횟수, 별점, 개봉일, user_product_id 순)으로 계산한다. AVOID 가 없으면 빈 목록
  - replacement_items_no_avoid: 바꿀 제품이 있으면 대체 후보가 남은 보유 제품과 AVOID 가 아니다
- split 은 페르소나의 split 을 따른다
```

## 정한 것과 그 이유

- **궁합 쌍은 레코드에 적는다.** 성분 충돌 규칙(B)이 아직 비어 있어 실제 루틴 점검으로는 AVOID
  쌍이 나오지 않는다. 바꿀 제품 고르기와 대체 후보를 지금 잴 수 있게, 러너가 이 레코드를 도는
  동안 루틴 점검 단계를 이 쌍을 옮겨 적는 단계로 바꾼다.
- **쌍은 상품 id 로 적는다.** 보유 제품 행의 id(user_product_id)는 합성 데이터를 DB 에 넣을 때
  만들어져 미리 알 수 없다. 러너가 실제 보유 제품 단계가 읽은 행으로 옮긴다. 보유 제품 자체는
  실제 경로의 것을 쓴다.
- **바꿀 제품 기대 값은 고르기 규칙을 그대로 돌려 계산했다.** 손으로 정하면 동률 순서를 잘못 적기
  쉽다. 별점과 개봉일은 personas_v1 의 값이다.
- **대체 후보의 AVOID 여부는 실제 성분 부품으로 다시 판정한다.** 레코드에 적은 쌍은 보유 제품끼리의
  것이고, 대체 후보는 실행할 때 정해져 미리 적을 수 없다. 러너가 PreFilter 와 같은 함수로 바꿀
  제품을 뺀 보유 제품과 다시 판정해 넘긴다.
- **쌍 개수는 적은 쌍만 센다.** 보유 제품 쌍 전부를 적지 않았다. BE 는 쌍 개수가 실린 쌍 수
  이상인지만 본다.

## 아직 통과할 수 없는 성질

- 모든 레코드: B 의 보유 제품 단계(inventory). 그 전에는 보유 제품 행이 없어 러너가 루틴 점검을
  만들지 못하고 실행 오류로 남는다. 루틴 점검 단계(compatibility)가 없어도 러너가 바꿔 끼우므로
  돈다.
- `replacement_items_no_avoid`: B 의 성분 부품(services.ingredient_store, rules.compatibility)과
  성분 충돌 규칙. 그 전에는 다시 판정할 수 없어 실패로 남는다. 리포트에서 이 실패는 홈 루틴
  경로의 문제로 보지 않는다.
