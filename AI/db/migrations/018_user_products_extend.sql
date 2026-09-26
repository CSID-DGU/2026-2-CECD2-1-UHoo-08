-- 018_user_products_extend.sql
--
-- 보유 제품에 기한·잔량·상태를 남긴다.
--
-- PreFilter가 "이미 가진 제품"과 "보유 제품과 충돌하는 제품"을 걸러내려면
-- 무엇을 가지고 있는지를 읽을 자리가 있어야 한다. 홈의 루틴 점검과 가성비의
-- 개인 가격 기준도 같은 데이터를 쓴다.
--
-- 주의: user_products에는 보유 제품만 있는 게 아니다. usage_type에
-- VIEWED(조회 이력) · USING(등록) · ONBOARDING(온보딩 등록)이 섞여 있다.
-- usage_type을 건드리면 기존 조회 이력 코드가 깨지므로 그대로 두고,
-- "지금 쓰고 있는 제품인가"는 새 status 컬럼으로 본다.
--
--   usage_type  이 행이 왜 생겼는가 (기존 의미 유지)
--   status      보유 제품으로서 지금 어떤 상태인가. 조회 이력이면 NULL
--
-- Inventory와 PreFilter는 status = 'USING' 만 읽는다.

ALTER TABLE user_products
    ADD COLUMN IF NOT EXISTS status          VARCHAR(20),
    ADD COLUMN IF NOT EXISTS opened_at       DATE,
    ADD COLUMN IF NOT EXISTS purchased_at    DATE,
    ADD COLUMN IF NOT EXISTS expiry_date     DATE,
    ADD COLUMN IF NOT EXISTS pao_months      INTEGER,
    ADD COLUMN IF NOT EXISTS remaining_pct   INTEGER,
    ADD COLUMN IF NOT EXISTS rating          INTEGER,
    ADD COLUMN IF NOT EXISTS review_text     TEXT,
    ADD COLUMN IF NOT EXISTS source          VARCHAR(20),
    ADD COLUMN IF NOT EXISTS recognized_raw  JSONB,
    ADD COLUMN IF NOT EXISTS updated_at      TIMESTAMP WITH TIME ZONE;

COMMENT ON COLUMN user_products.status IS
  '보유 상태 USING|FINISHED|DISCARDED. 조회 이력(usage_type=VIEWED)이면 NULL';
COMMENT ON COLUMN user_products.expiry_date IS
  '사진에서 읽은 유통기한. 읽지 못하면 비워 둔다. 추측해서 채우지 않는다';
COMMENT ON COLUMN user_products.pao_months IS
  '개봉 후 사용기간(12M 같은 기호). opened_at과 합쳐 실제 소진 기한을 잡는다';
COMMENT ON COLUMN user_products.remaining_pct IS
  '남은 용량 0~100. 사용자가 직접 넣는 유일한 값이다';
COMMENT ON COLUMN user_products.source IS
  '등록 경로 PHOTO|MANUAL. 사진 인식 정확도를 재려면 구분이 필요하다';
COMMENT ON COLUMN user_products.recognized_raw IS
  '사진 인식 원본. 사용자가 고친 최종값과 비교해 인식 정확도를 잰다';

-- 값이 조용히 어긋나는 것을 막는다. 잔량 120%, 별점 9점 같은 값이
-- 들어오면 점수 계산이 이상해지는데 원인을 찾기 어렵다.
ALTER TABLE user_products
    DROP CONSTRAINT IF EXISTS user_products_status_check;
ALTER TABLE user_products
    ADD CONSTRAINT user_products_status_check
    CHECK (status IS NULL OR status IN ('USING', 'FINISHED', 'DISCARDED'));

ALTER TABLE user_products
    DROP CONSTRAINT IF EXISTS user_products_remaining_pct_check;
ALTER TABLE user_products
    ADD CONSTRAINT user_products_remaining_pct_check
    CHECK (remaining_pct IS NULL OR remaining_pct BETWEEN 0 AND 100);

ALTER TABLE user_products
    DROP CONSTRAINT IF EXISTS user_products_rating_check;
ALTER TABLE user_products
    ADD CONSTRAINT user_products_rating_check
    CHECK (rating IS NULL OR rating BETWEEN 1 AND 5);

-- 이미 등록 경로로 들어온 행은 쓰고 있는 제품으로 본다.
UPDATE user_products
SET status = 'USING'
WHERE status IS NULL
  AND usage_type IN ('USING', 'ONBOARDING');

-- Inventory는 사용자별로 "쓰고 있는 것"만 읽는다. 조회 이력이 훨씬 많이
-- 쌓이므로 부분 인덱스로 그쪽을 건너뛴다.
CREATE INDEX IF NOT EXISTS idx_user_products_using
    ON user_products (user_id)
    WHERE status = 'USING';
