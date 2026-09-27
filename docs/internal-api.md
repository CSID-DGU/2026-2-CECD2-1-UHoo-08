# BE ↔ AI 내부 API

BE 가 AI 서버를 부르는 경로 목록이다. 값의 정확한 모양은 아래 두 파일이 기준이고,
이 문서는 그 둘을 한눈에 보기 위한 표다. **셋 중 하나를 고치면 나머지도 같이 고친다.**

- AI: `AI/contracts/internal_api.py`
- BE: `BE/.../common/ai/dto/AiInternalDtos.java`

## 경로

| 경로 | 방식 | 요청 | 응답 | 쓰는 곳 |
| --- | --- | --- | --- | --- |
| `POST /internal/agent/run/v2` | 비동기 202 | `jobId` `userId` `rawQuery` `basis` `targetProfile?` `parentJobId?` | `Accepted` | 검색, 조건 수정 |
| `POST /internal/agent/clarify` | 비동기 202 | `jobId` `answer` | `Accepted` | 되묻기 답변 |
| `POST /internal/products/recognize-photos` | 동기 | `nameImage` `dateImage?` | `candidates[]` `expiryDate?` `paoMonths?` `mfgDate?` `raw` | 사진 등록 |
| `POST /internal/home/run` | 비동기 202 | `userId` `kind` | `Accepted` | 홈 카드 일일 배치 |
| `POST /internal/bundle/swap` | 동기 | `jobId` `bundleIndex` `slot` `productId` | `bundle` | 예산 세트 교체 |
| `GET /internal/trends` | 동기 | `limit` | `items[]` | 홈 '요즘 뜨는 제품' |
| `POST /internal/feedback/apply` | 비동기 202 | `userId` | `Accepted` | 피드백 저장 뒤 |

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

지금은 일곱 경로가 모두 stub 이다. 응답에 `stub: true` 가 붙는다.

- **동기** 호출은 빈 결과가 온다. 표시를 보지 않으면 "결과 없음"으로 읽고 넘어가게 된다.
- **비동기** 호출은 job 이 움직이지 않는다. BE 는 `stub` 을 보면 경고 로그를 남긴다.

내용을 채우는 쪽은 `AI/api/internal/v2/` 의 해당 파일을 고친다. 파일이 경로별로
나뉘어 있어 여러 사람이 같이 작업해도 충돌하지 않는다.

## 값 이름

BE·FE 와 주고받는 값은 camelCase 다(`jobId`, `rawQuery`). 그래프 안쪽에서만
snake_case 를 쓴다(`AI/graph/state.py`). 경계를 섞으면 어느 쪽 이름인지 매번
확인해야 한다.

AI 쪽 스키마는 모르는 필드를 거부한다. BE 가 옛 이름으로 보내면 조용히 무시되는
대신 422 가 난다.
