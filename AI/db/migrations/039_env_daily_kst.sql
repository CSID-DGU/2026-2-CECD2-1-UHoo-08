-- 039_env_daily_kst.sql
--
-- refresh_env_daily 의 하루 경계를 KST 로 고친다.
--
-- 025 는 p_date::timestamptz 로 하루를 잘랐다. 이 캐스트는 세션 시간대를 따르는데
-- Supabase 의 시간대는 UTC 다. 그래서 "11월 27일" 집계가 KST 27일 09시 ~ 28일 09시
-- 관측을 묶었다. BE 는 "오늘"을 Asia/Seoul 로 정하므로(hwadam.zone) 화면의 날짜와
-- 집계 날짜가 9시간 어긋난다.
--
-- 날짜를 KST 자정으로 읽어 timestamptz 로 바꾸면 세션 시간대와 상관없이 같은 경계가
-- 나온다. 함수 시그니처는 그대로라 부르는 쪽은 바꿀 것이 없다.
--
-- 이 파일 전에 쌓인 env_daily 가 있으면 아래 맨 끝 주석의 재집계를 한 번 돌린다.

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
    AND observed_at >= (p_date::timestamp       AT TIME ZONE 'Asia/Seoul')
    AND observed_at <  ((p_date + 1)::timestamp AT TIME ZONE 'Asia/Seoul')
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
  '그날(KST) 관측 전체로 집계를 다시 만든다. 몇 번을 돌려도 결과가 같다';

-- 이미 쌓인 관측을 KST 기준으로 다시 집계할 때:
--
-- SELECT refresh_env_daily(region, d::date)
-- FROM (SELECT DISTINCT region, (observed_at AT TIME ZONE 'Asia/Seoul')::date AS d
--       FROM env_observations) t;
