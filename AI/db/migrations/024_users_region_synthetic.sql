-- 024_users_region_synthetic.sql
--
-- 지역과 합성 사용자 표시.
--
-- region: 생활 환경 점수는 사용자가 사는 곳의 4주 기록을 본다. 어디 사는지
--         모르면 환경 기반 추천을 켤 수 없다.
-- is_synthetic: 테스트용으로 만든 사용자를 실제 사용자와 섞어 두면 통계가
--         오염되고, 정리할 때 무엇을 지워야 할지 알 수 없다.

ALTER TABLE users
    ADD COLUMN IF NOT EXISTS region       VARCHAR(50),
    ADD COLUMN IF NOT EXISTS is_synthetic BOOLEAN NOT NULL DEFAULT FALSE;

COMMENT ON COLUMN users.region IS
  '환경 기록을 찾을 지역 이름. env_daily.region 과 같은 값을 쓴다';
COMMENT ON COLUMN users.is_synthetic IS
  '합성 데이터로 만든 사용자. 적재 스크립트가 켜고, 정리 스크립트가 이것만 지운다';

-- 합성 사용자 일괄 정리. 대부분 false 라 부분 인덱스로 둔다.
CREATE INDEX IF NOT EXISTS idx_users_synthetic
    ON users (id) WHERE is_synthetic;
