-- 022_recommendation_feedback.sql
--
-- 추천 결과에 대한 사용자의 반응.
--
-- 처음 쓰는 사용자는 데이터가 없어 추천이 맞을 수 없다. 피드백 없이 추천만
-- 반복하면 정확도가 오르지 않는다. 여기 쌓인 이유 태그를 점수 항목별로
-- 역산해 user_preference_weights 를 갱신한다.
--
-- 이름을 recommendation_feedback 으로 둔 이유: user_feedback 은 IoT 점검
-- 결과가 이미 쓰고 있다(013).

CREATE TABLE IF NOT EXISTS recommendation_feedback (
  id          BIGSERIAL PRIMARY KEY,
  job_id      UUID        NOT NULL REFERENCES recommendation_jobs (id) ON DELETE CASCADE,
  user_id     UUID        NOT NULL REFERENCES users (id) ON DELETE CASCADE,
  product_id  UUID        NOT NULL REFERENCES products (product_id) ON DELETE CASCADE,
  vote        VARCHAR(4)  NOT NULL CHECK (vote IN ('UP', 'DOWN')),
  reason_tags TEXT[]      NOT NULL DEFAULT '{}',
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),

  -- 같은 결과의 같은 제품에는 한 번만 남는다. 다시 누르면 덮어쓴다.
  -- 없으면 연타 한 번이 가중치를 여러 번 움직인다.
  CONSTRAINT recommendation_feedback_once UNIQUE (job_id, product_id, user_id)
);

COMMENT ON COLUMN recommendation_feedback.reason_tags IS
  '왜 그렇게 눌렀는지. 이 태그가 어느 점수 항목을 보정할지 정한다';

-- prior 재계산은 사용자별 최근 피드백을 읽는다.
CREATE INDEX IF NOT EXISTS idx_reco_feedback_user_created
  ON recommendation_feedback (user_id, created_at DESC);
