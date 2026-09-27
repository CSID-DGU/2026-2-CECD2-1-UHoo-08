-- 019_merge_registered_products.sql
--
-- 보유 제품의 기준 테이블을 user_products 하나로 모은다.
--
-- 지금은 등록한 제품이 registered_products 와 user_products 양쪽에 들어간다
-- (RegisteredProductServiceImpl). 두 테이블이 같은 것을 가리키면 PreFilter가
-- 어느 쪽을 읽어야 할지 정할 수 없고, 사진 등록으로 들어올 기한·잔량도
-- 둘 중 한 곳에만 쌓인다.
--
-- 조회 이력 행을 보유 제품으로 쓰지는 않는다. ProductServiceImpl.recordView 가
-- 같은 상품을 다시 볼 때마다 VIEWED 행을 지우고 새로 넣기 때문에, 그 행에
-- 붙여 둔 개봉일·기한·잔량이 함께 사라진다. 보유 제품은 항상 별도 행이다.
--
-- ⚠️ 양쪽이 이미 어긋나 있다. 등록 시 user_products 삽입은
--   `existsByUserIdAndProductId(userId, productId)` 로 건너뛰는데, 이 검사에
--   usage_type 이 빠져 있다. 그래서 전에 한 번 조회한 적 있는 제품을 등록하면
--   VIEWED 행이 있다는 이유로 보유 행이 만들어지지 않는다. 등록은 됐는데
--   보유 제품으로는 잡히지 않는 상태다. 아래 INSERT 가 그 행을 채우고,
--   같은 일이 다시 생기지 않게 BE 중복 검사도 함께 고친다.

-- 한 사용자·한 상품에 조회 이력 한 줄과 보유 한 줄까지는 있어야 한다.
-- (user_id, product_id) 전체에 걸린 유니크가 남아 있으면 아래 INSERT 가
-- 바로 막히므로, 두 갈래로 나눈 부분 유니크로 바꾼다.
ALTER TABLE user_products
    DROP CONSTRAINT IF EXISTS user_products_user_id_product_id_key;

CREATE UNIQUE INDEX IF NOT EXISTS user_products_owned_once
    ON user_products (user_id, product_id)
    WHERE usage_type <> 'VIEWED';

CREATE UNIQUE INDEX IF NOT EXISTS user_products_viewed_once
    ON user_products (user_id, product_id)
    WHERE usage_type = 'VIEWED';

-- registered_products 에 있는데 보유 행이 없는 것을 채운다.
-- USED·DISCARDED 행이 있으면 건드리지 않는다. 다 썼거나 버렸다는 것이
-- 등록했다는 사실보다 나중의 정보다.
INSERT INTO user_products (user_id, product_id, usage_type, created_at, updated_at)
SELECT rp.user_id, rp.product_id, 'USING', rp.created_at, NOW()
FROM registered_products rp
WHERE NOT EXISTS (
    SELECT 1 FROM user_products up
    WHERE up.user_id = rp.user_id
      AND up.product_id = rp.product_id
      AND up.usage_type <> 'VIEWED'
);

-- registered_products 는 지우지 않는다. 온보딩 화면이 아직 이 테이블을 읽고
-- 있고, 옮긴 결과가 맞는지 확인할 근거도 여기밖에 없다. 읽는 코드가 모두
-- user_products 로 옮겨간 뒤 별도 마이그레이션에서 지운다.
COMMENT ON TABLE registered_products IS
  '더 이상 쓰지 않는다. 보유 제품의 기준은 user_products '
  '(usage_type IN (USING, ONBOARDING)) 다. 읽는 코드가 모두 옮겨간 뒤 삭제한다';
