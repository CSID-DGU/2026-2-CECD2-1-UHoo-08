-- 031_photo_recognitions.sql
--
-- 사진 등록의 중간 결과.
--
-- 사진으로 보유 제품을 등록하는 일은 두 번의 요청으로 나뉜다.
-- 제품명 사진을 읽어 후보를 고르고, 이어서 기한 사진을 읽은 뒤, 마지막에
-- 등록한다. 첫 요청의 결과를 두 번째 요청과 등록까지 이어 줄 자리가 있어야
-- 한다. 서버 메모리에 두면 서버가 여러 대일 때 다음 요청이 다른 서버로 가서
-- 결과를 찾지 못하므로 DB 에 둔다.
--
-- 인식 결과는 잠깐만 쓴다. expires_at 이 지난 행은 정리 배치가 지운다.
-- 업로드한 이미지는 등록된 제품의 근거가 될 수 있어 지우지 않는다.

CREATE TABLE IF NOT EXISTS photo_recognitions (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id         UUID NOT NULL REFERENCES users (id) ON DELETE CASCADE,
  name_image_url  TEXT NOT NULL,
  date_image_url  TEXT,
  read_text       TEXT,
  candidates      JSONB NOT NULL DEFAULT '[]'::jsonb,
  expiry_result   JSONB,
  raw             JSONB,
  expires_at      TIMESTAMPTZ NOT NULL,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMENT ON COLUMN photo_recognitions.candidates IS
  '제품명 사진에서 찾은 제품 후보 목록';
COMMENT ON COLUMN photo_recognitions.expiry_result IS
  '기한 사진에서 읽은 값. {expiryDate, paoMonths, manufacturedAt}';
COMMENT ON COLUMN photo_recognitions.raw IS
  'AI 응답 원본. 등록할 때 user_products.recognized_raw 로 옮긴다';
COMMENT ON COLUMN photo_recognitions.expires_at IS
  '이 시각이 지나면 기한 사진 인식과 등록에 쓸 수 없다. 정리 배치가 지운다';

-- 정리 배치가 만료된 행을 찾는다.
CREATE INDEX IF NOT EXISTS idx_photo_recognitions_expires ON photo_recognitions (expires_at);
