-- 021_search_logs.sql
--
-- 실제로 들어온 질의와 그 질의가 어디로 갔는지를 남긴다.
--
-- 라우터 정확도는 합성 골든셋으로 먼저 재지만, 골든셋은 우리가 상상한
-- 질의다. 사용자가 실제로 무엇을 어떻게 쓰는지는 여기 쌓이는 것으로만 알 수
-- 있고, 오답으로 보이는 줄이 다음 골든셋 항목이 된다.
--
-- 결과 자체는 recommendation_jobs 가 갖는다. 여기는 "질의 → 해석 → 경로"
-- 까지만 본다.

CREATE TABLE IF NOT EXISTS search_logs (
  id          BIGSERIAL PRIMARY KEY,
  user_id     UUID REFERENCES users (id) ON DELETE SET NULL,
  job_id      UUID REFERENCES recommendation_jobs (id) ON DELETE SET NULL,
  raw_query   TEXT        NOT NULL,
  scenario    VARCHAR(20),
  query_spec  JSONB,
  confidence  REAL,
  clarified   BOOLEAN     NOT NULL DEFAULT FALSE,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMENT ON TABLE search_logs IS
  '질의와 그 해석 결과. 라우터 정확도를 실사용 기준으로 보기 위한 기록';
COMMENT ON COLUMN search_logs.user_id IS
  '탈퇴해도 질의 분포는 남긴다. 그래서 사용자가 지워지면 NULL 이 된다';
COMMENT ON COLUMN search_logs.scenario IS
  'Router 가 고른 경로. 비어 있으면 Normalize 단계에서 멈춘 질의다';
COMMENT ON COLUMN search_logs.clarified IS
  '되물어서 답을 받은 질의인가. 되묻기 비율이 높은 유형이 곧 개선 대상이다';

-- 시나리오별 분포와 최근 오답 훑기.
CREATE INDEX IF NOT EXISTS idx_search_logs_scenario_created
  ON search_logs (scenario, created_at DESC);

-- 확신이 낮았던 질의만 모아 본다. 골든셋에 넣을 후보가 여기 모인다.
CREATE INDEX IF NOT EXISTS idx_search_logs_low_confidence
  ON search_logs (created_at DESC)
  WHERE confidence IS NOT NULL AND confidence < 0.6;
