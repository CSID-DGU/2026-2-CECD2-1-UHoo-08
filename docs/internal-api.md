# BE ↔ AI 내부 API

BE 가 AI 서버를 부르는 경로 목록이다. 값의 정확한 모양은 아래 두 파일이 기준이고,
이 문서는 그 둘을 한눈에 보기 위한 표다. **셋 중 하나를 고치면 나머지도 같이 고친다.**

- AI: `AI/contracts/internal_api.py`
- BE: `BE/.../common/ai/dto/AiInternalDtos.java`

경로별 요청과 응답 예시는 `docs/internal-api-fixtures/` 에 있다. 계약을 바꿀 때는 예시를 먼저 고치고 코드를 고친다.

## 경로

| 경로 | 방식 | 요청 | 응답 | 쓰는 곳 |
| --- | --- | --- | --- | --- |
| `POST /internal/agent/run/v2` | 비동기 202 | `jobId` `userId` `rawQuery?` `baseProductId?` (둘 중 하나 필수) `basis` `targetProfile?` `parentJobId?` | `Accepted` | 검색, 조건 수정, 상품 평가 |
| `POST /internal/agent/clarify` | 비동기 202 | `jobId` `answer` | `Accepted` | 되묻기 답변 |
| `POST /internal/products/recognize-photos` | 동기 | `nameImage?` `dateImage?` (둘 중 하나 필수) | `candidates[]` `expiryDate?` `paoMonths?` `mfgDate?` `raw` | 사진 등록 |
| `POST /internal/home/run` | 비동기 202 | `userId` `kind` | `Accepted` | 홈 카드 일일 배치 |
| `POST /internal/bundle/swap` | 동기 | `jobId` `bundleIndex` `slot` `productId` | `bundle` | 예산 세트 교체 |
| `GET /internal/trends` | 동기 | `limit` | `items[]` | 홈 '요즘 뜨는 제품' |
| `POST /internal/feedback/apply` | 비동기 202 | `userId` | `Accepted` | 피드백 저장 뒤 |
| `POST /internal/compatibility/check` | 동기 | `userId` `productId` | `level` `pairs[]` `userProductId` `ingredientA` `ingredientB` `level` `advice?` `schedule?` | 상품 상세, 보유 제품 등록의 궁합 확인 |

`baseProductId` 가 있으면 문장을 해석하지 않고 평가 경로(S1)로 바로 간다. 되묻지도 않는다.
`rawQuery` 가 함께 와도 조건으로 읽지 않는다.

기존 `/internal/agent/run`(ReAct)과 `/internal/search` 는 그대로 둔다. v2 가 그 역할을
대신할 때까지 현재 서비스가 돌아야 한다.

## 비동기와 동기

**비동기**는 202 만 돌려주고 끝난다. 결과는 응답이 아니라 DB 로 간다.

- 추천 실행·되묻기 → `recommendation_jobs`
- 홈 카드 → `home_recommendations`
- 피드백 반영 → `user_preference_weights`

BE 는 202 를 받은 뒤 job 을 조회해 진행 상태를 본다. 응답을 기다리면 추천 한 번에
수십 초를 붙잡게 된다.

호출이 실패해도 BE 는 예외를 올리지 않는다. 호출한 쪽은 이미 job 을 만들어 두었고,
여기서 실패로 끝내면 AI 가 그 사이 실행을 시작했을 때 상태가 엇갈린다. 실패는 job 이
진행되지 않는 것으로 드러난다.

**동기**는 화면이 바로 기다리는 호출이다. 사진 인식은 60초, 나머지는 30초로 끊는다.

## job 상태

```
PENDING → IN_PROGRESS → COMPLETED
                      ↘ FAILED
                      ↘ NEEDS_CLARIFICATION → (답변) → IN_PROGRESS → …
```

`NEEDS_CLARIFICATION` 은 **실패가 아니다.** 되묻는 중이라 사용자의 답을 기다리는
상태다. 이 상태의 job 을 정리하면 답을 받아도 이어 돌릴 수 없다.

되묻기는 한 번까지다. 답을 받고도 값이 모자라면 그대로 진행한다.

## 아직 stub 인 경로

피드백 반영을 뺀 일곱 경로가 stub 이다. 응답에 `stub: true` 가 붙는다.

- **동기** 호출은 빈 결과가 온다. 표시를 보지 않으면 "결과 없음"으로 읽고 넘어가게 된다.
  궁합 확인(`compatibility/check`)의 `level=OK` 도 판정 결과가 아니다. 판정하는 코드와 규칙이 아직 없다.
- **비동기** 호출은 job 이 움직이지 않는다. BE 는 `stub` 을 보면 경고 로그를 남긴다.
  추천 실행(`run/v2`)과 되묻기 답변(`clarify`)도 결과를 조립하는 단계가 없으면 실행을 걸지 않는다.
  job 은 `PENDING` 으로 남고, 멈춘 job 정리 배치가 15분 뒤 `FAILED`(`timeout`)로 바꾼다.

내용을 채우는 쪽은 `AI/api/internal/v2/` 의 해당 파일을 고친다. 파일이 경로별로
나뉘어 있어 여러 사람이 같이 작업해도 충돌하지 않는다.

## 되묻기 결과

되물어야 하면 job 결과의 `clarify` 에 질문과 함께 `missingFields` 를 담는다.

- 값은 `budget.total`, `bundle_steps`, `base_product_ref` 다. 무엇이 비었는지를 뜻하고, 경로가 정해진 뒤 필수 값을 검사한 결과다.
- 필수 값은 다 있는데 요청이 막연해서 묻는 경우에는 빈 목록이다. 이때 무엇을 물을지는 BE 가 정한다.

## 피드백 반영

`feedback/apply` 는 부를 때마다 그 사용자의 신호를 변경 이력(`preference_weight_changes`)으로 옮기고,
되돌리지 않은 변경을 기본 가중치에 더해 `user_preference_weights` 를 다시 쓴다.

- 이유가 있는 별로예요는 이유별 항목을 올린다. 좋아요와 이유 없는 별로예요는 그 제품에서 점수가 평균보다 높은 항목을 기본값의 10% 만큼 올리거나 내린다.
- 최근 30일 조건 수정에서 같은 선택지를 3번 이상 고르면 패턴으로 반영한다. 반영 중이거나 30일 안에 되돌린 패턴은 다시 만들지 않는다.
- 실패하면 로그만 남긴다. 반영 시각은 변경을 저장한 뒤에 채우므로, 실패한 피드백은 다음 호출이 다시 처리한다. 이때 앞서 들어간 변경은 합산에서 뺀다.

## 홈 카드 결과

홈 카드는 추천 결과(`AI/contracts/result.py`)에 아래 블록을 더 담는다.

| 카드 | 필드 | 뜻 |
| --- | --- | --- |
| `HOME_ENV` | `conditions[]` `key` `label` `basis?` `covered` `coveredBy?` | 요즘 환경에 필요한 기능과 그것을 채운 보유 제품 |
| `HOME_ROUTINE` | `counts` `ok` `separate` `avoid` | 궁합 단계별 쌍의 수 |
| `HOME_ROUTINE` | `pairs[]` `a` `b` `level` `title?` `reason?` | 보유 제품 쌍의 궁합. `level` 은 `OK`, `SEPARATE`, `AVOID` |
| `HOME_ROUTINE` | `replacement?` `replaceTarget` `message?` `items[]` | 바꿀 제품과 대체 후보 |
| `HOME_ROUTINE` | `schedule` `morning[]` `evening[]` `tip?` | 아침, 저녁 사용 순서 |
| `HOME_ROUTINE` | `uncomparedCount` | 비교하지 못한 제품 수 |

`null` 은 아직 분석 전이고, 빈 목록은 분석했지만 해당 항목이 없다는 뜻이다. BE 는 `conditions`, `counts`, `pairs` 가 `null` 이면 카드를 분석 전으로 내려보낸다. `replacement` 만은 바꿀 제품이 없을 때도 `null` 이다.

## 예산 세트 칸

조합의 제품(`bundles[].items[]`)은 `slotKey?`, `slotLabel?` 로 어느 칸을 채우는지 알린다. 칸 정보가 없는 기존 결과는 BE 가 칸 순서로 처리한다.

세트 교체에 쓸 칸별 후보는 결과가 아니라 job 의 `state_snapshot.bundle_slots` 에 둔다. 조합이 달라도 후보가 같아 job 에 한 벌만 남긴다.

| 필드 | 뜻 |
| --- | --- |
| `slotKey` `label` | 칸 키와 칸 이름 |
| `candidates[]` `productId` `name` `price` `score` | 고를 수 있는 제품. 합계를 다시 계산하므로 `price` 는 필수다 |

## 값 이름

BE·FE 와 주고받는 값은 camelCase 다(`jobId`, `rawQuery`). 그래프 안쪽에서만
snake_case 를 쓴다(`AI/graph/state.py`). 경계를 섞으면 어느 쪽 이름인지 매번
확인해야 한다.

AI 쪽 스키마는 모르는 필드를 거부한다. BE 가 옛 이름으로 보내면 조용히 무시되는
대신 422 가 난다.
