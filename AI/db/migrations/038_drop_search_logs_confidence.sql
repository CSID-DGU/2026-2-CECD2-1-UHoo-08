-- 038_drop_search_logs_confidence.sql
--
-- search_logs 에서 confidence 컬럼과 그 컬럼을 쓰는 인덱스를 지운다.
--
-- 되물을지를 LLM 이 매긴 확신 점수가 아니라 양식이 얼마나 비었는지로 정하게 되면서
-- AI 는 확신 점수를 보내지 않고, BE 도 저장하지 않는다. 이 컬럼은 앞으로 늘 비어 있다.
-- 골든셋에 넣을 질의는 되물은 질의 표시(clarified)로 찾는다.
--
-- BE 는 스키마를 검사하므로, 이 컬럼을 읽는 BE 가 운영에서 내려간 뒤에 적용한다.
-- 예전 줄에 남아 있던 확신 점수는 함께 사라진다. 여러 번 실행해도 결과가 같다.

-- 컬럼을 지우는 동안 테이블을 잠근다. 다른 작업이 잠금을 오래 쥐고 있으면 기다리지 않고 실패하게 한다.
SET lock_timeout = '5s';

DROP INDEX IF EXISTS idx_search_logs_low_confidence;

ALTER TABLE search_logs DROP COLUMN IF EXISTS confidence;

RESET lock_timeout;
