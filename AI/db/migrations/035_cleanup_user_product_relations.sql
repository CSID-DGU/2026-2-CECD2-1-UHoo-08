-- 035_cleanup_user_product_relations.sql
--
-- 사용자와 제품의 관계를 조회·좋아요·사용으로 나눈다.
--
-- 034 에서 조회는 product_views, 좋아요는 wishlists 로 옮겼다. 운영 코드가 아직
-- user_products 에 옛 값을 쓰고 있어 그때는 지우지 못했다. 운영에 새 코드가
-- 배포됐으므로(2026-10-17) 이제 user_products 를 사용 기록만 남게 정리하고,
-- 다시 섞이지 않게 CHECK 로 막는다.
--
--   VIEWED      → product_views 에 있다. 지운다
--   INTERESTED  → wishlists 에 있다. 지운다
--   ONBOARDING  → 온보딩의 "자주 사용하는 제품"은 지금 쓰는 중인지 알 수 없는 취향 정보라
--                 사용 기록이 아니다. registered_products 에 있다. USING 으로 바꾸지 않고 지운다
--
-- 남는 값은 USING(쓰는 중)·USED(다 씀)·DISCARDED(버림) 셋이다.
--
-- 019 와 예전 등록 코드는 좋아요(INTERESTED) 행을 USING 으로 바꿔 보유로 올렸다.
-- 그 행들의 좋아요 기록은 그때 이미 사라져 여기서 되살릴 수 없다.
--
-- 이 파일을 적용한 뒤에야 UsageType 에서 옛 값을 뺀 BE 코드를 띄울 수 있다.
-- 옛 값이 남은 행이 있으면 BE 가 그 행을 읽지 못한다.


-- 1. 옮기지 못한 것이 없도록 한 번 더 옮긴다 ------------------------------------
-- 034 이후 운영의 옛 코드가 남긴 행이 있을 수 있다. 034 와 같은 규칙이라 여러 번 실행해도 결과가 같다.

INSERT INTO product_views (user_id, product_id, first_viewed_at, last_viewed_at, view_count)
SELECT user_id, product_id, created_at, created_at, 1
FROM user_products
WHERE usage_type = 'VIEWED'
ON CONFLICT (user_id, product_id) DO UPDATE
SET first_viewed_at = LEAST(product_views.first_viewed_at, EXCLUDED.first_viewed_at),
    last_viewed_at  = GREATEST(product_views.last_viewed_at, EXCLUDED.last_viewed_at);

INSERT INTO wishlists (user_id, product_id, created_at)
SELECT user_id, product_id, created_at
FROM user_products
WHERE usage_type = 'INTERESTED'
ON CONFLICT (user_id, product_id) DO NOTHING;

-- registered_products 에는 기본값과 유니크가 없어 id 를 직접 만들고, 이미 있는 것은 건너뛴다.
INSERT INTO registered_products (id, user_id, product_id, created_at)
SELECT gen_random_uuid(), up.user_id, up.product_id, up.created_at
FROM user_products up
WHERE up.usage_type = 'ONBOARDING'
  AND NOT EXISTS (
    SELECT 1 FROM registered_products rp
    WHERE rp.user_id = up.user_id AND rp.product_id = up.product_id
  );


-- 2. 사용 기록이 아닌 행을 지운다 ---------------------------------------------

DELETE FROM user_products
WHERE usage_type IN ('VIEWED', 'INTERESTED', 'ONBOARDING');


-- 3. 인덱스를 사용 기록 기준으로 맞춘다 --------------------------------------

-- 조회·좋아요는 이제 다른 테이블에 있다.
DROP INDEX IF EXISTS user_products_viewed_once;
DROP INDEX IF EXISTS user_products_interested_once;

-- 쓰는 중인 행만 제품당 하나. 034 에서는 ONBOARDING 도 묶었지만 이제 USING 하나다.
DROP INDEX IF EXISTS user_products_active_once;
CREATE UNIQUE INDEX user_products_active_once
  ON user_products (user_id, product_id)
  WHERE usage_type = 'USING';

-- 사용자별로 지금 쓰는 제품을 읽는 조회용. 018 에서는 ONBOARDING 도 묶었다.
DROP INDEX IF EXISTS idx_user_products_owned;
CREATE INDEX idx_user_products_owned
  ON user_products (user_id)
  WHERE usage_type = 'USING';


-- 4. 다시 섞이지 않게 막는다 -------------------------------------------------

ALTER TABLE user_products
    DROP CONSTRAINT IF EXISTS user_products_usage_type_check;
ALTER TABLE user_products
    ADD CONSTRAINT user_products_usage_type_check
    CHECK (usage_type IN ('USING', 'USED', 'DISCARDED'));

COMMENT ON COLUMN user_products.usage_type IS
  'USING(쓰는 중)|USED(다 씀)|DISCARDED(버림). 산 제품 한 통마다 한 줄이다. '
  '조회는 product_views, 좋아요는 wishlists, 온보딩의 자주 사용하는 제품은 registered_products 에 있다';
