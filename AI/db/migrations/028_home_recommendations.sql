-- 028_home_recommendations.sql
--
-- 홈 화면 맞춤 추천 카드의 계산 결과.
--
-- 홈은 검색 없이 열리는 화면이라, 열 때마다 그래프를 돌릴 수 없다. 하루에
-- 한 번 배치로 만들어 두고 화면은 읽기만 한다.
--
-- 사용자·종류당 한 줄이다. 어제 것을 남겨 둘 이유가 없고, 지난 추천이
-- 필요하면 recommendation_jobs 쪽에 job 으로 남는다.
--
-- '요즘 뜨는 제품'은 여기 없다. 그건 사용자별 계산이 아니라 전체 공통이라
-- product_trend_daily 에서 바로 읽는다.

CREATE TABLE IF NOT EXISTS home_recommendations (
  user_id      UUID        NOT NULL REFERENCES users (id) ON DELETE CASCADE,
  -- ROUTINE 보유 제품끼리 성분이 충돌하는지 점검하고 대체 제품을 권한다
  -- ENV     4주 환경에 견줘 부족한 기능을 채울 제품을 권한다
  kind         VARCHAR(20) NOT NULL CHECK (kind IN ('ROUTINE', 'ENV')),
  -- Compose 가 만든 추천 결과 그대로. contracts/result.py 와 같은 모양이다.
  result       JSONB       NOT NULL,
  job_id       UUID        REFERENCES recommendation_jobs (id) ON DELETE SET NULL,
  generated_at TIMESTAMPTZ NOT NULL DEFAULT now(),

  PRIMARY KEY (user_id, kind)
);

COMMENT ON TABLE home_recommendations IS
  '홈 맞춤 추천 카드의 일일 계산 결과. 사용자·종류당 한 줄이며 매일 덮어쓴다';
COMMENT ON COLUMN home_recommendations.result IS
  '보여줄 것이 없을 때도 빈 결과를 넣는다. 행이 없는 것(아직 안 돌았다)과 '
  '항목이 없는 것(돌았는데 권할 게 없다)은 화면에서 다르게 보여야 한다';
COMMENT ON COLUMN home_recommendations.job_id IS
  '이 카드를 만든 실행. 카드가 이상할 때 어떤 후보를 보고 그랬는지 되짚는다';

-- 배치가 오래된 것부터 다시 만든다. 실패하면 덮어쓰지 않으므로 옛 행이
-- 그대로 남고, 다음 배치에서 다시 대상이 된다.
CREATE INDEX IF NOT EXISTS idx_home_reco_generated
  ON home_recommendations (generated_at);
