-- 027_influencer.sql
--
-- 인플루언서 계정·게시물과 제품별 트렌드 지수.
--
-- 이 데이터는 합성할 수 없고 소급해서 모을 수도 없다. 오늘 안 모으면 오늘
-- 것은 영영 없다. 그래서 수집 배치를 가장 먼저 켠다.
--
-- 게시물 하나가 제품 하나를 말한다고 가정하지 않는다. 하울·파우치 공개
-- 게시물은 한 번에 대여섯 개를 언급한다. 한 줄에 product_id 하나만 두면
-- 나머지 언급이 통째로 사라지고, 멘토님이 강조한 '미확인률'도 셀 수 없다.
-- 그래서 게시물과 언급을 나눈다.

CREATE TABLE IF NOT EXISTS influencer_accounts (
  id            BIGSERIAL PRIMARY KEY,
  platform      VARCHAR(20) NOT NULL DEFAULT 'instagram',
  username      VARCHAR(100) NOT NULL,
  display_name  TEXT,
  follower_count INTEGER,
  -- 상위 인플루언서만 모으지 않는다. 10대가 보는 계정과 30대가 보는 계정은
  -- 다루는 제품이 다르고, 한쪽만 모으면 트렌드가 그 층의 것만 된다.
  age_group     VARCHAR(10),
  -- 메이크업 · 스킨케어 · 성분 같은 분야. 여러 개일 수 있다.
  focus         TEXT[]      NOT NULL DEFAULT '{}',
  active        BOOLEAN     NOT NULL DEFAULT TRUE,
  note          TEXT,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at    TIMESTAMPTZ NOT NULL DEFAULT now(),

  CONSTRAINT influencer_accounts_unique UNIQUE (platform, username)
);

COMMENT ON COLUMN influencer_accounts.age_group IS
  '이 계정이 대변하는 시청자 연령대 10s|20s|30s+. 선정 분산을 확인하는 기준';
COMMENT ON COLUMN influencer_accounts.follower_count IS
  '수집 시점의 값. 트렌드 지수의 영향력 항목이 쓴다';


CREATE TABLE IF NOT EXISTS influencer_posts (
  id               BIGSERIAL PRIMARY KEY,
  account_id       BIGINT      NOT NULL REFERENCES influencer_accounts (id) ON DELETE CASCADE,
  platform_post_id VARCHAR(100) NOT NULL,
  caption          TEXT,
  permalink        TEXT,
  posted_at        TIMESTAMPTZ,
  like_count       INTEGER,
  comment_count    INTEGER,
  -- 아직 판별하지 않았으면 NULL 이다. FALSE(광고 아님)와 구분해야
  -- 판별이 안 돈 게시물을 "광고 아님"으로 세지 않는다.
  is_ad            BOOLEAN,
  -- 1차 규칙에서 걸린 근거(#광고, #협찬 등). 정확도를 따질 때 규칙이
  -- 잡은 것과 LLM 이 잡은 것을 나눠 봐야 한다.
  ad_rule_hits     TEXT[]      NOT NULL DEFAULT '{}',
  ad_confidence    REAL,
  raw              JSONB,
  collected_at     TIMESTAMPTZ NOT NULL DEFAULT now(),

  CONSTRAINT influencer_posts_unique UNIQUE (account_id, platform_post_id)
);

COMMENT ON COLUMN influencer_posts.raw IS
  'API 응답 원본. 파싱을 고쳤을 때 지난 게시물을 다시 읽으려면 필요하다';

-- 트렌드 지수는 최근 게시물만 본다. 최신성 가중치가 붙기 때문이다.
CREATE INDEX IF NOT EXISTS idx_influencer_posts_posted
  ON influencer_posts (posted_at DESC);
-- 아직 판별하지 않은 게시물 훑기. 배치가 매번 찾는 대상이다.
CREATE INDEX IF NOT EXISTS idx_influencer_posts_unlabeled
  ON influencer_posts (collected_at) WHERE is_ad IS NULL;


CREATE TABLE IF NOT EXISTS influencer_post_products (
  id         BIGSERIAL PRIMARY KEY,
  post_id    BIGINT      NOT NULL REFERENCES influencer_posts (id) ON DELETE CASCADE,
  -- 캡션에서 뽑은 표현 그대로. "라네즈 네오쿠션 21호" 같은 문자열이다.
  raw_mention TEXT       NOT NULL,
  -- 마스터와 이어지지 않으면 NULL 로 둔다. 이것이 '미확인' 이고,
  -- 미확인률이 곧 식별 성능이라 지우지 않고 남긴다.
  product_id UUID        REFERENCES products (product_id) ON DELETE SET NULL,
  confidence REAL,
  matched_by VARCHAR(10) CHECK (matched_by IN ('RULE', 'LLM', 'MANUAL')),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),

  CONSTRAINT influencer_post_products_unique UNIQUE (post_id, raw_mention)
);

COMMENT ON TABLE influencer_post_products IS
  '게시물이 언급한 제품. 하울 게시물은 한 번에 여럿을 말하므로 게시물과 나눈다';
COMMENT ON COLUMN influencer_post_products.product_id IS
  'NULL 이면 미확인. 미확인률이 식별 성능 지표라 행 자체는 남긴다';

-- 제품별 언급 집계. 트렌드 지수 계산의 기본 조회다.
CREATE INDEX IF NOT EXISTS idx_post_products_product
  ON influencer_post_products (product_id) WHERE product_id IS NOT NULL;


CREATE TABLE IF NOT EXISTS product_trend_daily (
  product_id        UUID        NOT NULL REFERENCES products (product_id) ON DELETE CASCADE,
  date              DATE        NOT NULL,
  mention_count     INTEGER     NOT NULL DEFAULT 0,
  -- 광고 게시물의 언급은 따로 센다. 섞어 버리면 협찬으로 만들어진 수치와
  -- 실제 반응을 구분할 수 없다.
  ad_mention_count  INTEGER     NOT NULL DEFAULT 0,
  engagement        INTEGER     NOT NULL DEFAULT 0,
  trend_score       REAL,
  -- 어떤 계산식으로 나온 값인지. 식을 바꿔 가며 비교해야 하므로,
  -- 어느 버전의 결과인지 모르면 비교 자체가 안 된다.
  formula_version   VARCHAR(20),
  updated_at        TIMESTAMPTZ NOT NULL DEFAULT now(),

  PRIMARY KEY (product_id, date)
);

COMMENT ON TABLE product_trend_daily IS
  '제품별 일일 트렌드 지수. 홈의 요즘 뜨는 제품과 value_signal 보조 신호가 읽는다';

-- 오늘 뜨는 제품 상위 N개. 홈 카드가 매번 이 조회를 한다.
CREATE INDEX IF NOT EXISTS idx_trend_daily_date_score
  ON product_trend_daily (date DESC, trend_score DESC NULLS LAST);
