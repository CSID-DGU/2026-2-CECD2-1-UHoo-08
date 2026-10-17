-- 029_user_products_more.sql
--
-- 보유 제품 화면이 보여 주고 고치는 값을 남긴다.
--
-- 보유 제품 등록·수정 화면은 다 쓴 날짜와 제조일을 받는다.
-- 018 에서 기한·잔량·후기 자리를 만들었지만 이 둘은 없어서, 화면에서
-- 받은 값을 저장할 곳이 없다.
--
-- 보유 상태는 018 의 결정대로 새 컬럼 없이 usage_type 을 쓴다.
-- '모두 사용' 은 USED 로 바꾸고 finished_at 에 날짜를 남긴다.
--
-- rating 은 여기서 추가하지 않는다. 이미 INTEGER 컬럼과 1~5 CHECK
-- (user_products_rating_check)가 있고, 협업 추천이 이 컬럼을 읽고 있다.
-- 타입을 바꾸지 않고 그대로 쓴다.

ALTER TABLE user_products
    ADD COLUMN IF NOT EXISTS finished_at     DATE,
    ADD COLUMN IF NOT EXISTS manufactured_at DATE;

COMMENT ON COLUMN user_products.finished_at IS
  '''모두 사용'' 또는 ''진작 다 씀'' 을 고른 날짜. usage_type 이 USED 일 때 채운다';
COMMENT ON COLUMN user_products.manufactured_at IS
  '기한 사진에서 읽은 제조일. 개봉 후 사용 기한(pao_months)이 없을 때 기한을 어림하는 데 쓴다';
