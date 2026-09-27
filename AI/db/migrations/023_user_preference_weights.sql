-- 023_user_preference_weights.sql
--
-- 사용자별 점수 가중치 prior.
--
-- 가중치는 요청 맥락을 보고 LLM 이 매번 정하는데, 그 앞에 사용자의 성향을
-- 깔아 둔다. 피드백(022)과 조건 수정 이력 두 가지가 같은 곳으로 모인다.
-- 값이 흩어지면 "무엇 때문에 이 가중치가 됐는지"를 되짚을 수 없다.
--
-- 사용자당 한 줄이다. 이력이 필요하면 source_counts 로 몇 번의 신호가
-- 반영됐는지만 본다. 전체 이력은 피드백 테이블에 이미 있다.

CREATE TABLE IF NOT EXISTS user_preference_weights (
  user_id       UUID PRIMARY KEY REFERENCES users (id) ON DELETE CASCADE,
  weights       JSONB       NOT NULL DEFAULT '{}'::jsonb,
  source_counts JSONB       NOT NULL DEFAULT '{}'::jsonb,
  updated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMENT ON COLUMN user_preference_weights.weights IS
  '점수 항목별 prior. 키는 scorers/ 의 파일 이름과 같다 (budget_fit, review 등)';
COMMENT ON COLUMN user_preference_weights.source_counts IS
  '이 값이 어떤 신호 몇 번으로 만들어졌는지. 예: {"feedback": 12, "refine": 3}. '
  '보정 규칙을 고쳤을 때 결과가 왜 달라졌는지 설명하는 근거가 된다';
