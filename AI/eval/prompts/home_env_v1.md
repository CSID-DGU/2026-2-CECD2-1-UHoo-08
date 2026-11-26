# 홈 환경 골든셋 생성 기록

`eval/golden/scenario/home_env_v1.jsonl`(10건)을 만든 방법이다. Claude Code 가 아래 지시를 받아,
`personas_v1` 과 읽기 전용으로 조회한 보유 제품의 카테고리, 특징으로 만들었다.
평가는 시나리오 러너(`python -m eval.run_scenario_eval`)가 다른 시나리오와 함께 돈다.

## 지시

```
페르소나 10명마다 홈 환경(HOME_ENV) 레코드를 하나씩 만든다.

- input 에 persona_id, scenario, env_summary 를 적는다. 질의는 없다
- env_summary.needs 는 아래 다섯 기능 중에서 고른다(B 의 환경 요약 계약과 같은 모양)
    UV_PROTECT   자외선 차단     sun, 특징 조건 없음(선케어 제품이면 채운다)
    MOISTURE     보습 크림       skincare, 제품 종류 크림
    SOOTHING     진정 토너       skincare, 제품 종류 토너
    LIP_CARE     입술 보습       lip, 보습(moisturizing) 참
    MATTE_BASE   보송한 베이스   base, 마무리감 매트
- 종류를 tags 첫 항목에 적는다
  partial        일부만 보유 제품이 채움 3건
  covered        모두 보유 제품이 채움 1건
  multi          덮이지 않은 기능이 여럿 2건
  single         기능 하나, 덮이지 않음 1건
  no_inventory   보유 제품이 없는 페르소나 2건
  no_needs       필요한 기능이 없음 1건
- 기대 성질
  - conditions_cover: 기능마다 보유 제품이 채우는지. 보유 제품의 카테고리와 특징을
    rules/env_match.py 와 같은 규칙으로 대어 정한다
  - 덮이지 않은 기능이 있으면 결과가 비어 있지 않다(non_empty)
  - 덮이지 않은 기능이 하나면 상위 결과가 그 기능의 카테고리, 제품 종류를 지킨다(top5_all)
  - 모두 덮였거나 필요한 기능이 없으면 결과 카드가 없다(items_empty)
- split 은 페르소나의 split 을 따른다
```

## 정한 것과 그 이유

- **환경 요약은 레코드에 적는다.** 환경 집계(B)가 아직 없고, 들어온 뒤에도 날씨 데이터가 날마다
  바뀌어 같은 입력으로 다시 잴 수 없다. 러너는 이 레코드를 도는 동안 환경 집계 단계를 레코드의
  환경 요약을 내는 단계로 바꾼다. B 의 환경 골든셋(`eval/golden/env/`)이 생기면 그 출력을
  env_summary 로 옮겨 쓴다.
- **기능 다섯 개는 이 골든셋이 정한 가짜 값이다.** 키, 이름, 문구는 B 의 실제 값과 다를 수 있다.
  판정은 키로만 보므로, B 의 값이 정해지면 키를 맞추고 다시 판정한다.
- **자외선 차단은 특징 조건을 두지 않았다.** 선크림, 선스틱, 선쿠션 어느 것이든 자외선을 막는다.
  제품 종류를 선크림으로 두면 선스틱을 가진 사람에게 선크림을 또 권한다.
- **기능이 여럿 덮이지 않은 레코드는 top5_all 을 두지 않았다.** 기능마다 카드를 묶어 싣으므로
  상위 5개에 여러 카테고리가 섞이는 것이 맞다.
- **질의 해석은 홈 실행(services/home_runner.py)과 같은 값을 쓴다.** 레코드에 적지 않는다.

## 아직 통과할 수 없는 성질

- `conditions_cover` 의 true, `items_empty`(covered): B 의 보유 제품 단계(inventory). 그 전에는
  부족한 기능 확인 단계가 보유 제품을 몰라 모든 기능을 덮이지 않은 것으로 본다. 그래서 덮였다고
  기대한 기능은 실패하고, 모두 덮인 레코드에도 카드가 나온다. 리포트에서 이 실패는 홈 환경
  경로의 문제로 보지 않는다.
- 덮이지 않은 기능만 있는 레코드(no_inventory, single, multi, no_needs)는 지금도 통과해야 한다.
