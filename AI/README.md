# AI 서버

FastAPI + LangGraph. 추천 파이프라인은 StateGraph로 조립한다.

기존 `graph/action_model.py`(ReAct)는 새 그래프가 그 역할을 대체할 때까지 그대로 둔다.
새 코드는 아래 v2 디렉터리에만 올린다.

## 디렉터리

```
graph/
  state.py        GraphState — 노드 사이를 흐르는 값 전부
  registry.py     시나리오 → 단계(노드) 배열
  builder.py      registry를 읽어 StateGraph를 조립
  nodes/          노드 1개 = 파일 1개
contracts/        여러 파트가 같이 읽는 값의 pydantic 스키마
scorers/          점수 항목 1개 = 파일 1개
rules/            LLM 없이 표와 조건문으로만 판정하는 코드
data/synthetic/   합성 데이터 — 만드는 종류별로 나눈다
eval/golden/      골든셋 — 무엇을 평가하는지로 나눈다
eval/prompts/     생성에 쓴 프롬프트 원문
eval/assets/      JSONL에 넣을 수 없는 원본 (인식용 사진 등)
eval/reports/     평가 리포트
```

## 노드 작성 규칙

### 1. 파일 이름이 단계 이름이다

`registry.py`에 적는 단계 이름, 파일 이름, 함수 이름 셋이 같아야 한다.
`prefilter` 단계라면 `nodes/prefilter.py`의 `async def prefilter(...)` 다.

### 2. 시그니처는 하나뿐이다

```python
async def prefilter(state: GraphState) -> dict:
```

인자는 `state` 하나다. 노드마다 필요한 값을 따로 받기 시작하면 빌더가
단계를 배열로 조립할 수 없다. 필요한 값은 전부 `GraphState`에 있다.

### 3. 반환 dict에는 바꾼 키만 담는다

```python
return {"candidates": kept, "excluded": dropped}
```

state 전체를 복사해 돌려주지 않는다. 무엇을 바꾸는 노드인지가 반환값에 드러나야 한다.

### 4. 상단 docstring에 READS / WRITES 를 적는다

```python
"""보유 제품과 성분이 충돌하는 후보를 걸러낸다.

READS:  candidates, inventory
WRITES: candidates, excluded
"""
```

노드가 늘어나면 어떤 값이 어디서 만들어지고 어디서 쓰이는지 코드만 봐서는
추적이 안 된다. 단계 순서를 바꾸거나 새 단계를 끼워 넣을 때 이 줄만 보면 된다.

`AI/tests/v2/test_scaffold.py`가 1·2·4번을 기계로 검사한다. 규칙을 어기면 CI가 막는다.

### 5. 값은 GraphState로만 옮긴다

모듈 전역 dict에 담아 다음 노드에서 꺼내 쓰지 않는다. 그렇게 하면 같은 요청이
동시에 두 개 들어올 때 값이 섞이고, 실패했을 때 어느 단계까지 갔는지 남지 않는다.

### 6. 예외는 삼키지 않는다

노드 안에서 `try/except`로 덮고 빈 결과를 돌려주지 않는다. 빌더가 예외를 받아
job을 실패로 기록한다. 조용히 빈 값을 넘기면 다음 노드가 0점을 계산해 내보내고,
결과만 보면 정상처럼 보인다.

### 7. 진행률은 노드가 갱신하지 않는다

빌더가 노드 전후로 공통 처리한다. 노드는 자기 일만 한다.

## scorer 작성 규칙

파일 하나가 점수 항목 하나다. Score 노드가 `scorers/`를 읽어 로딩하므로
항목을 추가할 때 Score 노드를 고치지 않는다.

```python
def env_fit(product: dict, ctx: ScoreContext) -> float | None:
```

0~100을 돌려준다. **적용할 수 없는 후보에는 `None`을 돌려준다.** 0점이 아니다.
0점은 "환경에 안 맞는 제품"이고 `None`은 "이 요청에서는 따지지 않는 항목"이다.
`None`인 항목은 가중치 계산에서 빠진다.

## rules 작성 규칙

입력이 같으면 출력이 같아야 한다. LLM을 부르지 않는다.
판정 근거(어떤 성분 쌍이 걸렸는지 등)를 반환값에 담고, 단위 테스트를 같이 올린다.

## 테스트

```bash
# v2 코어만 — 시크릿 없이 돈다. CI가 도는 것과 같다.
pip install -r requirements-core.txt
pytest tests/v2

# 전체 — .env 와 무거운 의존성이 필요하다.
pip install -r requirements.txt
pytest tests
```
