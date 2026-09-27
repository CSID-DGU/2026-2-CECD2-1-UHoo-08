-- 025_env_daily.sql
--
-- 지역별 일일 환경 기록.
--
-- 생활 환경 점수(env_fit)와 홈의 환경 보완 카드는 "오늘 날씨"가 아니라
-- 4주 누적을 본다. 어제 하루 건조했다고 보습 제품을 권하지는 않는다.
-- 그래서 매일 남겨 두는 것 말고는 방법이 없다. 지난 날씨는 소급해서
-- 모을 수 없으니 수집 배치를 먼저 켜야 한다.
--
-- services/iot/weather.py 의 fetch_outdoor 가 한 시점의 값을 돌려준다.
-- 하루에 여러 번 부르므로 (region, date) 한 줄에 누적한다.
--
--   INSERT INTO env_daily (region, date, temp_avg, humidity_avg, uv_max,
--                          pm10_avg, pm25_avg, sample_count, source)
--   VALUES (...)
--   ON CONFLICT (region, date) DO UPDATE SET
--     temp_avg     = (env_daily.temp_avg * env_daily.sample_count
--                     + EXCLUDED.temp_avg) / (env_daily.sample_count + 1),
--     uv_max       = GREATEST(env_daily.uv_max, EXCLUDED.uv_max),
--     sample_count = env_daily.sample_count + 1,
--     updated_at   = now();
--
-- 지역 이름은 weather.py 의 REGIONS 키와 같은 값을 쓴다. users.region 도
-- 같은 값이다. 셋이 어긋나면 사용자의 지역에 해당하는 기록을 못 찾는다.

CREATE TABLE IF NOT EXISTS env_daily (
  region       VARCHAR(50) NOT NULL,
  date         DATE        NOT NULL,
  temp_avg     REAL,
  temp_min     REAL,
  temp_max     REAL,
  humidity_avg REAL,
  uv_max       REAL,
  pm10_avg     REAL,
  pm25_avg     REAL,
  -- 누적에 쓴 관측 횟수. 평균을 다시 계산할 때 필요하고, 수집이 빠진 날을
  -- 구분하는 근거이기도 하다. 값이 0이면 그날은 못 받은 것이다.
  sample_count INTEGER     NOT NULL DEFAULT 0,
  source       TEXT,
  created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at   TIMESTAMPTZ NOT NULL DEFAULT now(),

  PRIMARY KEY (region, date)
);

COMMENT ON TABLE env_daily IS
  '지역별 일일 환경. 4주 누적을 보는 env_fit 점수와 홈 환경 카드가 읽는다';
COMMENT ON COLUMN env_daily.region IS
  'services/iot/weather.py 의 REGIONS 키와 같은 값. users.region 도 같다';
COMMENT ON COLUMN env_daily.source IS
  '어느 API 에서 온 값인지. 기상청과 open-meteo 를 섞어 쓰므로 남겨 둔다';

-- 4주 조회. 지역 하나의 최근 28일을 훑는 것이 이 테이블의 거의 유일한 용도다.
CREATE INDEX IF NOT EXISTS idx_env_daily_region_date
  ON env_daily (region, date DESC);
