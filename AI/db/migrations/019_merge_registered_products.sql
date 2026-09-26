-- 019_merge_registered_products.sql
--
-- 보유 제품의 기준 테이블을 user_products 하나로 모은다.
--
-- 지금은 등록한 제품이 registered_products 와 user_products 양쪽에 들어간다
-- (RegisteredProductServiceImpl). 두 테이블이 같은 것을 가리키면 PreFilter가
-- 어느 쪽을 읽어야 할지 정할 수 없고, 사진 등록으로 들어올 기한·잔량도
-- 둘 중 한 곳에만 쌓인다.
--
-- ⚠️ 양쪽이 이미 어긋나 있다. 등록 시 user_products 삽입은
--   `existsByUserIdAndProductId(userId, productId)` 로 건너뛰는데, 이 검사에
--   usage_type이 빠져 있다. 그래서 전에 한 번 조회한 적 있는 제품을 등록하면
--   usage_type='VIEWED' 행이 이미 있다는 이유로 USING 행이 만들어지지 않는다.
--   등록은 됐는데 보유 제품으로는 잡히지 않는 상태다.
--
--   아래 UPDATE 가 그렇게 어긋난 과거 데이터를 맞춘다. 같은 일이 다시
--   생기지 않게 하려면 BE 쪽 중복 검사도 함께 고쳐야 한다.

-- 1) registered_products 에 있는데 user_products 쪽 상태가 비어 있는 행을 맞춘다.
--    usage_type 은 건드리지 않는다. 조회 이력이라는 사실 자체는 사실이다.
UPDATE user_products up
SET status     = 'USING',
    updated_at = NOW()
FROM registered_products rp
WHERE rp.user_id = up.user_id
  AND rp.product_id = up.product_id
  AND up.status IS NULL;

-- 2) registered_products 에만 있고 user_products 에 아예 없는 행을 옮긴다.
INSERT INTO user_products (user_id, product_id, usage_type, status, created_at, updated_at)
SELECT rp.user_id, rp.product_id, 'USING', 'USING', rp.created_at, NOW()
FROM registered_products rp
WHERE NOT EXISTS (
    SELECT 1 FROM user_products up
    WHERE up.user_id = rp.user_id
      AND up.product_id = rp.product_id
);

-- registered_products 는 지우지 않는다. 온보딩 화면이 아직 이 테이블을 읽고
-- 있고, 옮긴 결과가 맞는지 확인할 근거도 여기밖에 없다. 읽는 코드가 모두
-- user_products 로 옮겨간 뒤 별도 마이그레이션에서 지운다.
COMMENT ON TABLE registered_products IS
  '더 이상 쓰지 않는다. 보유 제품의 기준은 user_products (status=USING) 다. '
  '읽는 코드가 모두 옮겨간 뒤 삭제한다';
