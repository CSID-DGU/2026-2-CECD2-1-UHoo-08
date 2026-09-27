-- 020_recommendation_jobs_v2.sql
--
-- 추천 job 이 v2 그래프를 담을 수 있게 한다.
--
-- 지금 job 은 "기준 상품 하나를 평가한 기록"이다. 그래서 base_product_id 가
-- NOT NULL 이고, 어떤 경로로 돌았는지도 남지 않는다. v2 에서는
--
--   · 조건 탐색(S2)처럼 기준 상품 없이 시작하는 요청이 있고
--   · 같은 질의라도 시나리오에 따라 다른 경로로 돌며
--   · 조건 수정(S7)은 직전 job 의 후보와 조건을 다시 꺼내 쓰고
--   · 되묻는 동안 job 이 중간 상태로 멈춰 있어야 한다.
--
-- 네 가지를 남길 자리를 만든다.

ALTER TABLE recommendation_jobs
    ADD COLUMN IF NOT EXISTS scenario       VARCHAR(20),
    ADD COLUMN IF NOT EXISTS query_spec     JSONB,
    ADD COLUMN IF NOT EXISTS parent_job_id  UUID,
    ADD COLUMN IF NOT EXISTS state_snapshot JSONB;

-- 조건 탐색은 기준 상품이 없다. 이 제약이 남아 있으면 job 자체를 못 만든다.
ALTER TABLE recommendation_jobs
    ALTER COLUMN base_product_id DROP NOT NULL;

-- 조건 수정은 부모 job 의 스냅샷에서 후보와 조건을 복원한다.
-- 부모가 지워지면 되돌릴 근거가 없어지므로 연결만 끊고 job 자체는 남긴다.
ALTER TABLE recommendation_jobs
    DROP CONSTRAINT IF EXISTS recommendation_jobs_parent_fk;
ALTER TABLE recommendation_jobs
    ADD CONSTRAINT recommendation_jobs_parent_fk
    FOREIGN KEY (parent_job_id) REFERENCES recommendation_jobs (id) ON DELETE SET NULL;

COMMENT ON COLUMN recommendation_jobs.scenario IS
  '어느 경로로 돌았는지. graph/registry.py 의 SCENARIOS 키';
COMMENT ON COLUMN recommendation_jobs.query_spec IS
  'Normalize 가 만든 QuerySpec 전문. 화면에는 요약만 나가므로 원본은 여기 남긴다';
COMMENT ON COLUMN recommendation_jobs.parent_job_id IS
  '조건 수정 전 job. 되돌리기와 수정 이력이 이 고리를 따라간다';
COMMENT ON COLUMN recommendation_jobs.state_snapshot IS
  '실행이 끝난 시점의 GraphState. 재탐색·되돌리기가 후보를 다시 만들지 않아도 되게 한다';
COMMENT ON COLUMN recommendation_jobs.status IS
  'PENDING|IN_PROGRESS|NEEDS_CLARIFICATION|COMPLETED|FAILED. '
  'NEEDS_CLARIFICATION 은 되묻는 중이라 사용자의 답을 기다리는 상태다';

-- 수정 이력을 거슬러 올라갈 때 쓴다. 부모가 없는 job 이 대부분이라
-- 부분 인덱스로 둔다.
CREATE INDEX IF NOT EXISTS idx_reco_jobs_parent
    ON recommendation_jobs (parent_job_id)
    WHERE parent_job_id IS NOT NULL;

-- 사용자의 최근 job 조회. 되돌리기 목록과 조건 수정 이력이 쓴다.
CREATE INDEX IF NOT EXISTS idx_reco_jobs_user_created
    ON recommendation_jobs (user_id, created_at DESC);
