# 광고 판별 검수 데이터 (2026-11-02)

`eval/golden/trend/ad_audit_20261102.jsonl` 100건을 만든 방식이다.
2차 LLM 판정을 처음 잰 데이터이고, 정기 표본 검수의 첫 회차다.

## 원본

v1 골든셋(`ad_v1.jsonl`)과 겹치지 않게, 수집 목록에 없던 인플루언서 7명을 새로 골랐다.

| 계정 | 연령대 | 분야 |
| --- | --- | --- |
| davly0y | 20대 | 화장품리뷰 |
| hanchaeng | 20대 | 화장품리뷰 |
| theweather_is | 40대이상 | 화장품리뷰 |
| sr531 | 30대 | 화장품리뷰 |
| scarlet._.sister | 20대 | 화장품리뷰 |
| kimxsuu | 20대 | 화장품리뷰 |
| jinnitto | 20대 | 화장품리뷰 |

davly0y 는 이미 수집 중인 계정이라, v1 골든셋에 들어간 게시물 2건은 뺐다.

Graph API 로 최근 180일 게시물 519건을 읽었다 (DB 에는 넣지 않았다). 캡션이 있는 517건에
그때의 1차 규칙을 돌려 1차 확정 451건, 2차로 넘김 66건이 나왔다.

## 뽑은 방식

| 단계 | 전체 | 뽑은 수 | 방식 |
| --- | ---: | ---: | --- |
| 2차로 넘김 | 66 | 66 | 전부 |
| 1차 확정 | 451 | 34 | 광고 17 / 광고 아님 17, 계정당 최대 4건 |

`random.Random(20261102)` 로 섞었다. 2차 66건 중 38건이 scarlet._.sister 다. 이 계정이
표기 없이 할인·이벤트를 거는 글을 많이 올린다.

## 라벨을 붙인 방식

규칙·LLM 판정을 숨기고, 1차 신호도 보여 주지 않은 채 사람이 캡션만 보고 광고 여부를 골랐다.
초안을 보여 주면 라벨이 초안 쪽으로 끌려가 2차 성능을 잴 수 없기 때문이다.
판정 기준은 `trend_ad_v1.md` 를 따랐다.

라벨을 붙인 뒤 결과를 보며 한 건(trend-g-0140, 본인 팔레트 나눔)을 처음에 잘못 눌렀다고 확인해
광고 → 광고 아님으로 고쳤다.

이 과정에서 기준이 하나 더 정해졌다.

- 경품 이벤트는 브랜드 제품을 알리는 경품만 광고다. 본인이 쓰던 물건 나눔은 제품 이름이
  적혀 있어도, "화장품 한보따리"처럼 제품이 특정되지 않은 선물은 광고가 아니다.

## split

전부 `dev` 다. 이 데이터의 오답을 보고 2차 프롬프트를 고쳤으므로 성능을 재는 데 쓰지 않는다.

## 레코드

```json
{"id": "trend-g-0101", "split": "dev", "source": "real", "tags": ["llm"], "note": "",
 "input": {"post_id": null, "platform_post_id": "...", "username": "...", "posted_at": "2026-08-27", "caption": "..."},
 "expected": {"is_ad": true}, "check": "exact",
 "audit": {"stage": "LLM", "population": {"RULE": 451, "LLM": 66}, "window_days": 180, "sampled_at": "2026-11-02",
           "prediction": {"is_ad": true, "version": "ad-llm-v1", "reason_code": "PROMOTIONAL_COPY", "reason": "..."}}}
```

- `input.post_id` 는 DB 에 넣지 않은 게시물이라 null 이다. `platform_post_id` 로 구분한다.
- `audit.stage` 는 그 게시물을 판정한 단계(RULE / LLM), `audit.population` 은 그때 1차·2차가
  맡은 게시물 수다. 전체 정확도를 단계 비율로 가중할 때 쓴다.
- `audit.prediction` 은 라벨을 붙일 때 숨겨 둔 판정이다. 1차는 `ad-rule-v2` 에서 여는 괄호 없는
  `광고)` 를 고치기 전 상태다.
