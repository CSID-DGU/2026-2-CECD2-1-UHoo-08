-- 032_preference_weight_changes.sql
--
-- 가중치를 움직인 사건 하나하나.
--
-- user_preference_weights(023)는 사용자당 현재 값 한 줄뿐이다. 어떤 피드백이
-- 값을 얼마나 바꿨는지 남지 않아서 "되돌리기"를 할 수 없다. 사건마다 변화량을
-- 남겨 두면 그 사건만 골라 취소할 수 있다.
--
-- 조건 수정에서 반복되는 패턴(예: 계속 더 싼 것을 찾음)은 사용자 확인 없이
-- 바로 반영하고(REFINE_PATTERN), 사용자는 결과 보고서의 "되돌리기"로 취소한다.
-- 그래서 별도의 제안 테이블은 만들지 않는다.
--
-- 행은 AI 의 피드백 반영 처리만 만든다. 가중치 계산 규칙을 한곳에 두기
-- 위해서다. BE 는 되돌릴 때 reverted_at 만 채운다.

CREATE TABLE IF NOT EXISTS preference_weight_changes (
  id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id      UUID NOT NULL REFERENCES users (id) ON DELETE CASCADE,
  source       VARCHAR(20) NOT NULL CHECK (source IN ('FEEDBACK','REFINE_PATTERN')),
  source_ref   TEXT,
  deltas       JSONB NOT NULL,
  text         TEXT NOT NULL,
  reverted_at  TIMESTAMPTZ,
  created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMENT ON COLUMN preference_weight_changes.source_ref IS
  '무엇 때문에 움직였는지. FEEDBACK 이면 recommendation_feedback.id, REFINE_PATTERN 이면 패턴 키(CHEAPER 등)';
COMMENT ON COLUMN preference_weight_changes.deltas IS
  '점수 항목별 변화량. 예: {"budget_fit": 0.05, "value_signal": 0.05}. 되돌릴 때 이 값을 빼면 된다';
COMMENT ON COLUMN preference_weight_changes.text IS
  '화면에 보여 줄 문장. 예: ''너무 비싸요'' 피드백으로 가격 비중 ↑';
COMMENT ON COLUMN preference_weight_changes.reverted_at IS
  '사용자가 되돌린 시각. NULL 이면 아직 반영된 상태다';

-- 결과 보고서와 이력 화면이 사용자별 최근 변경을 읽는다.
CREATE INDEX IF NOT EXISTS idx_pref_changes_user ON preference_weight_changes (user_id, created_at DESC);
