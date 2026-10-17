-- 034_split_user_product_relations.sql
--
-- 사용자와 제품의 관계를 조회·좋아요·사용으로 나눈다. (1/2 단계: 추가만)
--
-- 지금은 성격이 다른 세 가지가 user_products.usage_type 한 칸에 들어 있다.
--
--   VIEWED      조회. 일어난 일의 기록이다
--   INTERESTED  좋아요. 켜고 끄는 값이다
--   USING·USED·DISCARDED  사용. 계속 바뀌는 상태다
--
-- 한 칸이라 하나를 바꾸면 다른 하나가 덮인다. 좋아요한 제품을 등록하면
-- INTERESTED 가 USING 으로 바뀌어 좋아요 기록이 사라지고, 조회는 볼 때마다
-- 지우고 다시 넣어서 기록이 쌓이지 않는다. 좋아요는 wishlists 에도 따로 있어
-- 한쪽만 바뀌면 둘이 어긋난다.
--
-- 앞으로 세 관계는 각자의 테이블에만 둔다. 한 동작은 자기 테이블만 바꾼다.
--
--   조회    product_views (새 테이블). (user, product)당 한 줄, 볼 때마다 갱신
--   좋아요  wishlists (기존). 좋아요를 누르고 취소할 때만 바뀐다
--   사용    user_products. 산 제품 한 통마다 한 줄. 다시 사면 새 줄
--
-- 운영 서버도 같은 DB 를 쓰고, 운영 코드는 아직 VIEWED·INTERESTED·ONBOARDING 을
-- user_products 에 쓴다. 그래서 이 파일은 기존 코드와 함께 동작하는 추가만 한다.
-- 옛 값을 지우고 CHECK 로 막는 일은 운영에 새 코드가 배포된 뒤 035 에서 한다.


-- 1. 조회 ---------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS product_views (
  user_id         UUID        NOT NULL REFERENCES users (id) ON DELETE CASCADE,
  product_id      UUID        NOT NULL REFERENCES products (product_id),
  first_viewed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  last_viewed_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  view_count      INTEGER     NOT NULL DEFAULT 1 CHECK (view_count >= 1),
  PRIMARY KEY (user_id, product_id)
);

COMMENT ON TABLE product_views IS
  '사용자가 본 제품. (user, product)당 한 줄이고 볼 때마다 last_viewed_at 과 view_count 를 갱신한다';

-- 최근 본 상품은 사용자별 마지막 조회 순으로 읽는다.
CREATE INDEX IF NOT EXISTS idx_product_views_recent
  ON product_views (user_id, last_viewed_at DESC);

-- 기존 조회 기록을 옮긴다. 지금까지는 볼 때마다 지우고 다시 넣었으므로
-- 남아 있는 created_at 이 마지막으로 본 시각이고, 몇 번 봤는지는 알 수 없다.
-- 여러 번 실행해도 같은 결과가 나오도록 충돌하면 시각만 넓히고 횟수는 늘리지 않는다.
INSERT INTO product_views (user_id, product_id, first_viewed_at, last_viewed_at, view_count)
SELECT user_id, product_id, created_at, created_at, 1
FROM user_products
WHERE usage_type = 'VIEWED'
ON CONFLICT (user_id, product_id) DO UPDATE
SET first_viewed_at = LEAST(product_views.first_viewed_at, EXCLUDED.first_viewed_at),
    last_viewed_at  = GREATEST(product_views.last_viewed_at, EXCLUDED.last_viewed_at);


-- 2. 좋아요 -------------------------------------------------------------------

-- user_products 에만 있던 좋아요를 wishlists 로 옮긴다. wishlists 에는 이미
-- UNIQUE (user_id, product_id) 가 있어서, 이미 있는 것은 그대로 둔다.
INSERT INTO wishlists (user_id, product_id, created_at)
SELECT user_id, product_id, created_at
FROM user_products
WHERE usage_type = 'INTERESTED'
ON CONFLICT (user_id, product_id) DO NOTHING;


-- 3. 사용 ---------------------------------------------------------------------

-- 지금은 한 사용자가 한 제품에 사용 행을 하나만 가질 수 있다(019). 그래서 다시
-- 사면 예전 행을 USING 으로 되돌리고, 지난번의 개봉일·다 쓴 날짜·잔량이 새 값에
-- 덮인다. 쓰는 중인 행만 제품당 하나로 두고, 다 쓴 행·버린 행은 몇 개든 남긴다.
-- ONBOARDING 은 쓰는 중인 것으로 보므로 USING 으로 바꾸기 전까지 함께 묶는다.
DROP INDEX IF EXISTS user_products_owned_once;

CREATE UNIQUE INDEX IF NOT EXISTS user_products_active_once
  ON user_products (user_id, product_id)
  WHERE usage_type IN ('USING', 'ONBOARDING');
