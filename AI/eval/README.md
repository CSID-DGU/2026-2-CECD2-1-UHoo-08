# 합성 데이터와 골든셋

각자 자기 기능을 테스트하면서 직접 만든다. 형식만 맞추면 나중에 한 리포트로 합칠 수 있다.

PR 을 올리기 전에 검증을 통과시킨다.

```bash
cd AI
python -m eval.validate            # 형식만 본다. DB 없이 돈다
python -m eval.validate --db       # 상품 마스터에 있는 product_id 인지까지 본다
```

## 어디에 두나

폴더는 **만드는 사람이 아니라 무엇을 만들고 무엇을 평가하는지**로 나눈다. 담당이 바뀌어도 자리가 그대로고, 같은 대상을 두 사람이 만들어도 한곳에 모인다.

```
data/synthetic/
  personas/   페르소나와 보유 제품
  queries/    검색 질의
  feedback/   피드백·조건 수정 세션
  env/        환경 기록 백필

eval/golden/
  router/         질의 → 시나리오·QuerySpec
  scenario/       페르소나 + 질의 → 추천 결과
  recognize/      제품 사진 → 인식 필드
  compatibility/  성분 쌍 → 충돌 등급
  env/            4주 환경 → 제품 조건
  bundle/         예산 요청 → 조합
  trend/          인스타 캡션 → 제품 식별·광고 판별

eval/prompts/   생성에 쓴 프롬프트 원문
eval/assets/    JSONL 에 넣을 수 없는 원본 (인식용 사진 등)
eval/reports/   평가 결과
```

파일 이름은 `<종류>_v<n>.jsonl` 이다. **기존 파일은 고치지 않는다.** 내용이 바뀌면 `v2`, `v3` 으로 새 파일을 만든다. 그래야 "전보다 나아졌는지"를 비교할 수 있다.

시나리오처럼 종류가 여럿이면 폴더를 더 만들지 말고 파일 이름으로 나눈다.
`eval/golden/scenario/s2_search_v1.jsonl`

**생성 프롬프트는 반드시 남긴다.** 2차 멘토링에서 "합성 데이터를 어떻게 만들었는지"가 질문 항목이다.

## 형식

한 줄에 레코드 하나인 JSONL, UTF-8, 키는 snake_case.

### 모든 레코드가 갖는 것

```json
{
  "id": "persona-0001",
  "split": "dev",
  "source": "claude",
  "tags": ["conflict"],
  "note": ""
}
```

- **`id`** — 접두어는 그 파일이 든 폴더 이름이다. 골든셋은 `-g` 를 붙인다.
  `data/synthetic/personas/` → `persona-0001` · `eval/golden/router/` → `router-g-0001`
  `env` 는 양쪽에 다 있어서, 붙이지 않으면 id 가 겹친다.
- **`split`** — `dev` 70% / `test` 30%. 프롬프트나 규칙은 **dev 를 보고만** 고치고,
  리포트 수치는 **test** 로 낸다. 골든셋에 맞춰 튜닝한 결과를 성능이라고 부르지 않기 위해서다.
- **`source`** — `claude` | `manual` | `real`
- `tags`, `note` 는 없어도 된다.

누가 만들었는지는 적지 않는다. git 이 이미 알고 있다.

### 골든셋 레코드

```json
{
  "id": "scenario-g-0007", "split": "test", "source": "claude",
  "input": {"persona_id": "persona-0003", "scenario": "S2_SEARCH",
            "query_spec": {"category": "skincare"}},
  "expected": {"must_exclude": ["<보유 레티놀 세럼 ID>"], "top5_all": {"category": "skincare"}},
  "check": "property"
}
```

`check` 는 세 가지다.

| 값 | 뜻 |
| --- | --- |
| `exact` | 값이 정확히 같아야 한다 |
| `contains` | 기대 항목이 결과에 들어 있어야 한다 |
| `property` | 결과가 조건을 만족해야 한다 |

**추천 결과는 순위를 맞추게 하지 않는다.** 합성 데이터에는 "정답 1위"가 사실상 없다. 대신 성질로 본다 — 보유·충돌 제품이 빠졌는지, 상위 다섯 개가 조건을 만족하는지, 피드백 뒤 순위가 올라갔는지.

### 페르소나

페르소나와 보유 제품은 PreFilter 와 성분 충돌이 함께 쓴다. 필드를 통일한다.

```json
{
  "id": "persona-0001", "split": "dev", "source": "claude", "tags": ["conflict"],
  "skin_type": "DRY", "skin_concerns": ["주름", "건조"], "personal_color": "WARM",
  "age_group": "30s", "region": "서울", "price_sensitivity": "high",
  "inventory": [
    {"product_id": "…", "opened_at": "2026-08-01", "remaining_pct": 60,
     "usage_type": "USING", "rating": 4}
  ]
}
```

**`product_id` 는 실제 상품 마스터의 ID 여야 한다.** 없는 ID 를 쓰면 적재까지는 되지만, PreFilter 가 그 제품을 찾지 못해 보유 제품이 없는 것처럼 동작한다. `--db` 검증이 이걸 잡는다.

`region` 은 `services/iot/weather.py` 의 `REGIONS` 키와 같은 값을 쓴다.

## DB 에 넣고 빼기

```bash
python -m eval.load_synthetic            # 페르소나를 users·user_products 에 넣는다
python -m eval.purge_synthetic           # 넣은 것을 전부 지운다
```

적재한 사용자는 `users.is_synthetic = true` 로 표시된다. 삭제는 이 표시를 기준으로 하므로 실제 사용자는 건드리지 않는다.

## 2차 멘토링 전 최소 개수

| 대상 | 최소 |
| --- | --- |
| router | 시나리오당 30개 이상, 모호한 질의 20% 포함 |
| scenario | 페르소나 20명, 페르소나당 질의 3개, 충돌 보유자 5명 이상 |
| recognize | 실제 사진 20장 |
| compatibility | 성분 쌍 30개 |
| env | 환경 시나리오 5개 |
| bundle | 예산 요청 10개 |
| trend | 캡션 100건 수작업 라벨 |

## 리포트

`eval/reports/<대상>_<YYYYMMDD>.md` 에 쓴다.

1. 데이터 개수와 파일 버전
2. 핵심 지표 (test split 기준)
3. 실패 사례 5개 이상과 원인 추정
4. 다음 조치
