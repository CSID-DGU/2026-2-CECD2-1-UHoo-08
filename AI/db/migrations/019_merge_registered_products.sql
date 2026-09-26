-- 019_merge_registered_products.sql
--
-- 보유 제품의 기준 테이블을 user_products 하나로 모은다.
--
-- 지금은 등록한 제품이 registered_products 와 user_products 양쪽에 들어간다
-- (RegisteredProductServiceImpl). 두 테이블이 같은 것을 가리키면 PreFilter가
-- 어느 쪽을 읽어야 할지 정할 수 없고, 사진 등록으로 들어올 기한·잔량도
-- 둘 중 한 곳에만 쌓인다.
--
-- 주의: 조회 이력 행(usage_type='VIEWED')에 status를 달아 보유 제품으로
-- 쓰면 안 된다. ProductServiceImpl.recordView 가 같은 제품을 다시 볼 때마다
-- VIEWED 행을 지우고 새로 넣기 때문에, 그 행에 붙여 둔 기한·잔량이 함께
-- 사라진다. 보유 제품은 항상 별도의 USING 행으로 둔다.
--
-- ⚠️ 양쪽이 이미 어긋나 있다. 등록 시 user_products 삽입은
--   `existsByUserIdAndProductId(userId, productId)` 로 건너뛰는데, 이 검사에
--   usage_type이 빠져 있다. 그래서 전에 한 번 조회한 적 있는 제품을 등록하면
--   VIEWED 행이 이미 있다는 이유로 USING 행이 만들어지지 않는다. 등록은
--   됐는데 보유 제품으로는 잡히지 않는 상태다. 아래 INSERT 가 그렇게 빠진
--   행을 채우고, 같은 일이 다시 생기지 않도록 BE 중복 검사도 함께 고친다.

-- registered_products 에 있는데 보유 행(VIEWED 가 아닌 행)이 없는 것을 채운다.
INSERT INTO user_products (user_id, product_id, usage_type, status, created_at, updated_at)
SELECT rp.user_id, rp.product_id, 'USING', 'USING', rp.created_at, NOW()
FROM registered_products rp
WHERE NOT EXISTS (
    SELECT 1 FROM user_products up
    WHERE up.user_id = rp.user_id
      AND up.product_id = rp.product_id
      AND up.usage_type <> 'VIEWED'
);

-- 보유 행인데 018 의 보정에서 빠진 것이 있으면 맞춘다.
UPDATE user_products up
SET status     = 'USING',
    updated_at = NOW()
FROM registered_products rp
WHERE rp.user_id = up.user_id
  AND rp.product_id = up.product_id
  AND up.usage_type <> 'VIEWED'
  AND up.status IS NULL;

-- registered_products 는 지우지 않는다. 온보딩 화면이 아직 이 테이블을 읽고
-- 있고, 옮긴 결과가 맞는지 확인할 근거도 여기밖에 없다. 읽는 코드가 모두
-- user_products 로 옮겨간 뒤 별도 마이그레이션에서 지운다.
COMMENT ON TABLE registered_products IS
  '더 이상 쓰지 않는다. 보유 제품의 기준은 user_products (status=USING) 다. '
  '읽는 코드가 모두 옮겨간 뒤 삭제한다';
