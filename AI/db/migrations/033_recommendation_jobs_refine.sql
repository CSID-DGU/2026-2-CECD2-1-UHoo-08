-- 033_recommendation_jobs_refine.sql
--
-- 추천 job 의 진행 단계, 조건 수정 입력, 원문 질의.
--
-- 추천은 비동기라 화면이 진행 상태를 폴링한다. 지금은 step 하나와 progress
-- 숫자뿐이라 "조건 이해 → 후보 찾기 → 순위 매기기" 같은 단계 목록을 보여 줄
-- 수 없다. steps 는 AI 빌더가 단계마다 갱신한다.
--
-- 조건 수정(재탐색)은 부모 job(parent_job_id, 020)에서 이어지는 새 job 이다.
-- 사용자가 고른 선택지와 직접 쓴 문장을 남겨야 조건 수정 이력을 보여 주고,
-- 반복되는 패턴을 가중치에 반영할 수 있다.
--
-- raw_query 는 사용자가 친 원문이다. query_spec(020)은 해석한 결과라
-- 원문으로 되돌릴 수 없다.
--
-- recommendation_feedback.applied_at 은 AI 가 그 피드백을 가중치에 반영한
-- 시각이다. 반영은 비동기라 NULL 이면 아직 반영 전이다. 같은 피드백을 두 번
-- 반영하지 않는 기준이 된다.

ALTER TABLE recommendation_jobs
    ADD COLUMN IF NOT EXISTS steps          JSONB,
    ADD COLUMN IF NOT EXISTS refine_presets TEXT[],
    ADD COLUMN IF NOT EXISTS refine_text    TEXT,
    ADD COLUMN IF NOT EXISTS raw_query      TEXT,
    ADD COLUMN IF NOT EXISTS basis          VARCHAR(10),
    ADD COLUMN IF NOT EXISTS target_profile JSONB;

COMMENT ON COLUMN recommendation_jobs.steps IS
  '진행 단계 목록. [{key, label, state}]. AI 빌더가 단계마다 갱신한다';
COMMENT ON COLUMN recommendation_jobs.refine_presets IS
  '조건 수정에서 고른 선택지 키';
COMMENT ON COLUMN recommendation_jobs.refine_text IS
  '조건 수정에서 사용자가 직접 쓴 문장';
COMMENT ON COLUMN recommendation_jobs.raw_query IS
  '사용자가 친 원문. query_spec 은 이것을 해석한 결과다';

ALTER TABLE recommendation_feedback
    ADD COLUMN IF NOT EXISTS applied_at TIMESTAMPTZ;

COMMENT ON COLUMN recommendation_feedback.applied_at IS
  'AI 가 이 피드백을 가중치에 반영한 시각. NULL 이면 아직 반영 전이다';
