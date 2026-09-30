-- 018_user_products_extend.sql
--
-- 보유 제품에 기한·잔량·인식 원본을 남긴다.
--
-- PreFilter가 "이미 가진 제품"과 "보유 제품과 충돌하는 제품"을 걸러내려면
-- 무엇을 가지고 있는지를 읽을 자리가 있어야 한다. 홈의 루틴 점검과 가성비의
-- 개인 가격 기준도 같은 데이터를 쓴다.
--
-- 보유 상태는 새 컬럼을 만들지 않고 기존 usage_type 을 그대로 쓴다.
-- 이 컬럼은 이미 생명주기를 담고 있고(db/iot/reader.py, db/iot/writer.py),
-- 같은 뜻의 컬럼을 하나 더 두면 두 값이 언제든 어긋난다.
--
--   VIEWED      조회 이력. 보유가 아니다
--   INTERESTED  위시리스트. 아직 가진 것이 아니다
--   USING       쓰고 있다
--   ONBOARDING  온보딩에서 등록했다. 쓰고 있는 것으로 본다
--   USED        다 썼다
--   DISCARDED   버렸다
--
-- Inventory 와 PreFilter 는 USING·ONBOARDING 만 읽는다.

COMMENT ON COLUMN user_products.usage_type IS
  'VIEWED(조회 이력)|INTERESTED(위시리스트)|USING|ONBOARDING|USED|DISCARDED. '
  '지금 보유한 것은 USING·ONBOARDING 뿐이다. VIEWED 와 INTERESTED 는 보유가 아니다';

ALTER TABLE user_products
    ADD COLUMN IF NOT EXISTS expiry_date     DATE,
    ADD COLUMN IF NOT EXISTS pao_months      INTEGER,
    ADD COLUMN IF NOT EXISTS remaining_pct   INTEGER,
    ADD COLUMN IF NOT EXISTS review_text     TEXT,
    ADD COLUMN IF NOT EXISTS source          VARCHAR(20),
    ADD COLUMN IF NOT EXISTS recognized_raw  JSONB,
    ADD COLUMN IF NOT EXISTS updated_at      TIMESTAMPTZ;

COMMENT ON COLUMN user_products.expiry_date IS
  '사진에서 읽은 유통기한. 읽지 못하면 비워 둔다. 추측해서 채우지 않는다';
COMMENT ON COLUMN user_products.pao_months IS
  '개봉 후 사용기간(12M 같은 기호). opened_at 과 합쳐 실제 소진 기한을 잡는다';
COMMENT ON COLUMN user_products.remaining_pct IS
  '남은 용량 0~100. 사용자가 직접 넣는 유일한 값이다';
COMMENT ON COLUMN user_products.source IS
  '등록 경로 PHOTO|MANUAL. 사진 인식 정확도를 재려면 구분이 필요하다';
COMMENT ON COLUMN user_products.recognized_raw IS
  '사진 인식 원본. 사용자가 고친 최종값과 비교해 인식 정확도를 잰다';

-- 새로 만드는 컬럼에만 제약을 건다. 잔량 120% 같은 값이 들어오면 소진 예측만
-- 이상해지고 원인은 드러나지 않는다. 기존 컬럼은 과거 값을 알 수 없어 둔다.
ALTER TABLE user_products
    DROP CONSTRAINT IF EXISTS user_products_remaining_pct_check;
ALTER TABLE user_products
    ADD CONSTRAINT user_products_remaining_pct_check
    CHECK (remaining_pct IS NULL OR remaining_pct BETWEEN 0 AND 100);

-- Inventory 는 사용자별로 보유 제품만 읽는다. 조회 이력이 훨씬 많이 쌓이므로
-- 부분 인덱스로 그쪽을 건너뛴다.
CREATE INDEX IF NOT EXISTS idx_user_products_owned
    ON user_products (user_id)
    WHERE usage_type IN ('USING', 'ONBOARDING');
