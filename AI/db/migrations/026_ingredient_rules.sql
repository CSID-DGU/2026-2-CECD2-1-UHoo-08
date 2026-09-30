-- 026_ingredient_rules.sql
--
-- 성분 별칭 사전과 충돌 규칙.
--
-- PreFilter 가 "보유 제품과 함께 쓰면 안 되는 제품"을 걸러내려면 두 가지가
-- 필요하다. 같은 성분을 같은 이름으로 부르는 것과, 어떤 조합이 문제인지를
-- 적어 둔 표다.
--
-- 성분 이름은 표기가 제각각이다. 나이아신아마이드 · 니아신아마이드 ·
-- Niacinamide · 비타민B3 가 모두 같은 것을 가리킨다. 이걸 맞추지 않으면
-- 충돌 규칙이 대부분의 경우에 그냥 안 걸린다. 걸리지 않는 필터는 아무
-- 에러도 내지 않아서, 동작하는 것처럼 보인다.

CREATE TABLE IF NOT EXISTS ingredient_alias (
  -- 조회 키. 소문자로 바꾸고 공백·하이픈·가운뎃점을 뺀 형태로 넣는다.
  -- 읽는 쪽도 같은 방식으로 변환해서 찾는다.
  alias      TEXT PRIMARY KEY,
  -- 실제로 본 표기. 어디서 온 별칭인지 나중에 확인하려면 원문이 있어야 한다.
  alias_raw  TEXT,
  canonical  TEXT        NOT NULL,
  source     TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMENT ON TABLE ingredient_alias IS
  '성분 표기 → 표준명. 표준명은 products.feature_json 의 key_ingredient 에 '
  '쓰는 이름과 같아야 한다';
COMMENT ON COLUMN ingredient_alias.alias IS
  '소문자·공백/하이픈 제거 후의 조회 키. normalize_ingredients() 가 만든다';

-- 표준명으로 별칭을 역으로 훑을 때 쓴다. 사전을 손보다 보면 한 표준명에
-- 어떤 별칭이 붙어 있는지 확인할 일이 계속 생긴다.
CREATE INDEX IF NOT EXISTS idx_ingredient_alias_canonical
  ON ingredient_alias (canonical);


CREATE TABLE IF NOT EXISTS ingredient_conflict_rules (
  id           BIGSERIAL PRIMARY KEY,
  ingredient_a TEXT        NOT NULL,
  ingredient_b TEXT        NOT NULL,
  level        VARCHAR(10) NOT NULL CHECK (level IN ('AVOID', 'SEPARATE')),
  -- 화면에 그대로 나가는 문장. "레티놀 제품과 저녁에 나눠 쓰세요" 처럼
  -- 사용자가 무엇을 하면 되는지가 적혀 있어야 한다.
  advice       TEXT        NOT NULL,
  -- 근거 없는 규칙은 넣지 않는다. 화장품 조합은 단정하기 쉬운 주제라
  -- 어디서 온 이야기인지가 규칙 자체만큼 중요하다.
  source       TEXT        NOT NULL,
  created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),

  -- 두 성분은 항상 사전 순으로 넣는다. 그러지 않으면 (A,B) 와 (B,A) 가
  -- 따로 들어가 한쪽만 고치는 일이 생긴다. 조회하는 쪽도 정렬해서 찾는다.
  CONSTRAINT ingredient_conflict_ordered CHECK (ingredient_a < ingredient_b),
  CONSTRAINT ingredient_conflict_pair_once UNIQUE (ingredient_a, ingredient_b)
);

COMMENT ON TABLE ingredient_conflict_rules IS
  '성분 두 개의 조합 판정. 표준명끼리 비교한다';
COMMENT ON COLUMN ingredient_conflict_rules.level IS
  'AVOID(함께 쓰지 않기, 후보에서 제외) | SEPARATE(시간대 분리, 후보 유지 + 배지)';

-- 보유 제품의 성분 하나를 놓고 걸리는 규칙을 찾는 것이 기본 조회다.
-- 사전 순 제약 때문에 한쪽 컬럼만으로는 다 못 찾으므로 양쪽에 건다.
CREATE INDEX IF NOT EXISTS idx_ingredient_conflict_a ON ingredient_conflict_rules (ingredient_a);
CREATE INDEX IF NOT EXISTS idx_ingredient_conflict_b ON ingredient_conflict_rules (ingredient_b);
