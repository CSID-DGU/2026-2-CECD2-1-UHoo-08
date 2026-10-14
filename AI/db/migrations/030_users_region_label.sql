-- 030_users_region_label.sql
--
-- 화면에 보여 줄 지역 이름.
--
-- users.region(024)은 환경 기록을 찾는 키다. weather.py 의 REGIONS 키
-- ("서울", "경기" …)와 같은 시·도 단위 값이라, 사용자가 고른 동네를
-- 그대로 담을 수 없다. "고양시 덕양구" 처럼 고른 이름을 화면에 다시
-- 보여 주려면 따로 남겨야 한다.
--
-- 환경 데이터를 찾을 때는 계속 region 만 쓴다. region_label 은 표시용이다.

ALTER TABLE users ADD COLUMN IF NOT EXISTS region_label VARCHAR(50);

COMMENT ON COLUMN users.region_label IS
  '화면 표시용 지역 이름. 예: 고양시 덕양구. 환경 데이터 조회에는 region 을 쓴다';
