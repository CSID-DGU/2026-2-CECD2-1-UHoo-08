-- 036_frequently_used_products.sql
--
-- 온보딩의 "자주 사용하는 제품" 테이블 registered_products 를 frequently_used_products 로 바꾼다.
--
-- 이름만 보고는 무엇을 담는지 알 수 없고 보유 제품(user_products)과 헷갈렸다. 035 에서 사용 기록과
-- 취향 정보를 나눴으니 이름과 제약도 그 뜻에 맞춘다.
--   Hibernate 가 만든 FK 이름을 정리하고, 사용자나 제품이 지워지면 함께 지운다
--   사용자와 제품마다 한 줄만 둔다
--   id 와 created_at 에 기본값을 둔다
--
-- 배포는 마이그레이션을 실행하지 않아, 적용한 뒤에도 새 BE 로 바뀔 때까지 옛 BE 가 돈다.
-- 옛 BE 가 계속 읽고 쓰도록 옛 이름의 뷰를 남긴다(5번). 새 BE 를 배포한 뒤 다음 마이그레이션에서 지운다.
-- 여러 번 실행해도 결과가 같다.


-- 1. 테이블 이름 -------------------------------------------------------------

DO $$
BEGIN
  IF to_regclass('public.registered_products') IS NOT NULL
     AND to_regclass('public.frequently_used_products') IS NULL THEN
    ALTER TABLE registered_products RENAME TO frequently_used_products;
  END IF;
END $$;

DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_constraint
             WHERE conrelid = 'public.frequently_used_products'::regclass
               AND conname = 'registered_products_pkey') THEN
    ALTER TABLE frequently_used_products RENAME CONSTRAINT registered_products_pkey TO frequently_used_products_pkey;
  END IF;
END $$;


-- 2. FK 를 이름 있는 것으로 바꾼다 --------------------------------------------
-- Hibernate 가 만든 이름(fk502…, fkh2m…)은 환경마다 같다는 보장이 없어, 이 테이블의 FK 를 모두 찾아 지운다.

DO $$
DECLARE
  fk record;
BEGIN
  FOR fk IN
    SELECT conname FROM pg_constraint
    WHERE conrelid = 'public.frequently_used_products'::regclass
      AND contype = 'f'
      AND conname NOT IN ('frequently_used_products_user_id_fkey', 'frequently_used_products_product_id_fkey')
  LOOP
    EXECUTE format('ALTER TABLE frequently_used_products DROP CONSTRAINT %I', fk.conname);
  END LOOP;
END $$;

ALTER TABLE frequently_used_products
    DROP CONSTRAINT IF EXISTS frequently_used_products_user_id_fkey,
    DROP CONSTRAINT IF EXISTS frequently_used_products_product_id_fkey;
ALTER TABLE frequently_used_products
    ADD CONSTRAINT frequently_used_products_user_id_fkey
        FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
    ADD CONSTRAINT frequently_used_products_product_id_fkey
        FOREIGN KEY (product_id) REFERENCES products (product_id) ON DELETE CASCADE;


-- 3. 사용자와 제품마다 한 줄 -------------------------------------------------
-- 겹친 행이 있으면 먼저 고른 것을 남긴다.

DELETE FROM frequently_used_products f
USING frequently_used_products earlier
WHERE f.user_id = earlier.user_id
  AND f.product_id = earlier.product_id
  AND (earlier.created_at, earlier.id) < (f.created_at, f.id);

ALTER TABLE frequently_used_products
    DROP CONSTRAINT IF EXISTS frequently_used_products_user_product_once;
ALTER TABLE frequently_used_products
    ADD CONSTRAINT frequently_used_products_user_product_once UNIQUE (user_id, product_id);


-- 4. 기본값과 설명 ------------------------------------------------------------

ALTER TABLE frequently_used_products
    ALTER COLUMN id SET DEFAULT gen_random_uuid(),
    ALTER COLUMN created_at SET DEFAULT now();

COMMENT ON TABLE frequently_used_products IS
  '온보딩에서 고른 자주 사용하는 제품. 지금 쓰는 중인지와 상관없는 취향 정보라 보유 제품(user_products)과 따로 둔다';

COMMENT ON COLUMN user_products.usage_type IS
  'USING(쓰는 중)|USED(다 씀)|DISCARDED(버림). 산 제품 한 통마다 한 줄이다. '
  '조회는 product_views, 좋아요는 wishlists, 온보딩의 자주 사용하는 제품은 frequently_used_products 에 있다';


-- 5. 옛 이름의 뷰 -------------------------------------------------------------
-- 옛 BE 는 registered_products 를 읽고 쓴다. 테이블 하나를 그대로 비추는 뷰라 PostgreSQL 이 INSERT, DELETE 도
-- 그대로 넘기고, JPA validate 도 뷰를 테이블로 받아들인다. 새 BE 는 이 뷰를 쓰지 않는다.

CREATE OR REPLACE VIEW registered_products AS
SELECT id, user_id, product_id, created_at
FROM frequently_used_products;

COMMENT ON VIEW registered_products IS
  '옛 BE 호환용. frequently_used_products 로 이름을 바꾼 뒤 새 BE 배포 전까지만 둔다';
