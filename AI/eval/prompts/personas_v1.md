# personas_v1 생성 기록

`data/synthetic/personas/personas_v1.jsonl` 20명을 만든 방법이다. Claude Code 가 아래 지시를 받아,
상품 마스터를 읽기 전용으로 조회한 뒤 고정 시드(20261114)로 뽑았다.

## 지시

```
추천 경로 평가에 쓸 합성 페르소나 20명을 만든다.

- 피부 타입 5종(DRY, OILY, NORMAL, COMBINATION, OILY_DEHYDRATED)을 4명씩 고르게 둔다
- 퍼스널 컬러, 피부 고민은 BE 가 저장하는 값만 쓴다
  - 퍼스널 컬러: SPRING_WARM, SUMMER_COOL, AUTUMN_MUTE, WINTER_COOL, UNKNOWN
  - 피부 고민 1~2개: SENSITIVE, DEHYDRATED, WRINKLE, BRIGHTENING, PORE
- 지역은 services/iot/weather.py 의 REGIONS 키만 쓴다
- 보유 제품은 상품 마스터에 실제로 있는 상품만, 사용 중(USING)으로 3~8개
  - 가격이 있는 skincare, sun, base, lip 상품에서 고른다
  - 개봉일, 남은 양, 평점은 그럴듯한 범위에서 무작위로 둔다
- 특성은 tags 로 표시한다
  - conflict_pending 5명: 성분 충돌 규칙에 걸릴 성분(레티놀, 레티닐팔미테이트, AHA, BHA)이 든 실제 상품을
    보유 제품 첫 항목으로 둔다
  - budget_tight 4명: 2만원 이하 상품만 보유, price_sensitivity high
  - popular_user 3명: 전체 인기 기준 질의를 주로 할 사람
  - no_inventory 2명: 보유 제품이 없다. 보유 제품이 없을 때 경로가 깨지지 않는지 보려는 것이다
  - 나머지 6명은 특성 없음
- 충돌 보유자가 아닌 사람의 보유 제품에는 위 충돌 성분과 비타민C가 든 상품을 넣지 않는다.
  충돌 판정 결과를 해석하기 쉽게 하려는 것이다
- dev 14명, test 6명. test 는 특성마다 고르게 나눈다
```

## 성분 충돌 규칙이 비어 있던 것

만들 때 `ingredient_conflict_rules` 가 비어 있었다(0행). 그래서 충돌 보유자 5명은 `conflict` 대신
`conflict_pending` 으로 두었다. B 의 규칙이 들어오면 실제 규칙에 걸리는지 확인해 `personas_v2` 를 만든다.

## 보유 제품 수 규칙의 예외

보유 제품은 3~8개가 원칙이지만, `no_inventory` 2명은 일부러 0개다.
