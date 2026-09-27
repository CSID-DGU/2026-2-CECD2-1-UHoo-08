-- 025_env_daily.sql
--
-- 지역별 환경 관측과 일일 집계.
--
-- 생활 환경 점수(env_fit)와 홈의 환경 보완 카드는 "오늘 날씨"가 아니라
-- 4주 누적을 본다. 어제 하루 건조했다고 보습 제품을 권하지는 않는다.
-- 지난 날씨는 소급해서 모을 수 없으니 수집 배치를 먼저 켜야 한다.
--
-- 관측과 집계를 나눈다. 017 에서 피부 측정의 원본 채널값을 남긴 것과 같은
-- 이유다. 집계만 남기면 계산 방식을 바꿨을 때 지난 기록을 다시 만들 수 없고,
-- 한 줄에 누적하면서 평균을 갱신하는 방식은 값이 하나만 빠져도(그날 UV 만
-- 못 받는 일이 흔하다) 이후 평균이 전부 어긋난다.
--
-- 배치는 관측을 넣고, 그날 것을 통째로 다시 집계한다. 몇 번을 다시 돌려도
-- 같은 결과가 나온다.

CREATE TABLE IF NOT EXISTS env_observations (
  id          BIGSERIAL PRIMARY KEY,
  region      VARCHAR(50) NOT NULL,
  observed_at TIMESTAMPTZ NOT NULL,
  temperature REAL,
  humidity    REAL,
  uv_index    REAL,
  pm10        REAL,
  pm25        REAL,
  source      TEXT,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),

  -- 같은 시점을 두 번 넣지 않는다. 배치가 겹쳐 돌아도 집계가 흔들리지 않는다.
  CONSTRAINT env_observations_once UNIQUE (region, observed_at)
);

COMMENT ON TABLE env_observations IS
  'services/iot/weather.py 의 fetch_outdoor 가 돌려주는 시점 값 그대로';
COMMENT ON COLUMN env_observations.region IS
  'weather.py 의 REGIONS 키와 같은 값. users.region 도 같다';

CREATE INDEX IF NOT EXISTS idx_env_obs_region_time
  ON env_observations (region, observed_at DESC);


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
  -- 그날 집계에 쓴 관측 수. 0 이면 아예 못 받은 날이다. 4주 집계에서
  -- 못 받은 날을 "건조하지 않은 날"로 세지 않으려면 이 값이 필요하다.
  sample_count INTEGER     NOT NULL DEFAULT 0,
  updated_at   TIMESTAMPTZ NOT NULL DEFAULT now(),

  PRIMARY KEY (region, date)
);

COMMENT ON TABLE env_daily IS
  'env_observations 를 하루 단위로 접은 값. 원본에서 언제든 다시 만들 수 있다';

-- 4주 조회. 지역 하나의 최근 28일을 훑는 것이 이 테이블의 거의 유일한 용도다.
CREATE INDEX IF NOT EXISTS idx_env_daily_region_date
  ON env_daily (region, date DESC);


-- 하루치를 다시 집계한다. 관측을 넣은 뒤 그날에 대해 부른다.
-- 컬럼별로 값이 있는 관측만 평균 내므로, UV 만 빠진 날에도 나머지는 남는다.
CREATE OR REPLACE FUNCTION refresh_env_daily(p_region VARCHAR, p_date DATE)
RETURNS VOID AS $$
  INSERT INTO env_daily (region, date, temp_avg, temp_min, temp_max,
                         humidity_avg, uv_max, pm10_avg, pm25_avg,
                         sample_count, updated_at)
  SELECT p_region, p_date,
         AVG(temperature), MIN(temperature), MAX(temperature),
         AVG(humidity), MAX(uv_index), AVG(pm10), AVG(pm25),
         COUNT(*), now()
  FROM env_observations
  WHERE region = p_region
    AND observed_at >= p_date::timestamptz
    AND observed_at <  (p_date + 1)::timestamptz
  ON CONFLICT (region, date) DO UPDATE SET
    temp_avg     = EXCLUDED.temp_avg,
    temp_min     = EXCLUDED.temp_min,
    temp_max     = EXCLUDED.temp_max,
    humidity_avg = EXCLUDED.humidity_avg,
    uv_max       = EXCLUDED.uv_max,
    pm10_avg     = EXCLUDED.pm10_avg,
    pm25_avg     = EXCLUDED.pm25_avg,
    sample_count = EXCLUDED.sample_count,
    updated_at   = now();
$$ LANGUAGE SQL;

COMMENT ON FUNCTION refresh_env_daily IS
  '그날 관측 전체로 집계를 다시 만든다. 몇 번을 돌려도 결과가 같다';
