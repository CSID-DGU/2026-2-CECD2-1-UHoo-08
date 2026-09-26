/**
 * 시나리오별 추천 결과 mock.
 *
 * AI 테스트(`AI/tests/v2/test_result_mocks.py`)가 이 JSON 들을 직접 읽어
 * 스키마와 대조한다. 필드를 고치면 그쪽 테스트가 먼저 잡는다.
 */
import type { RecommendationResult } from "../../api/recommendationV2";

import clarify from "./clarify.json";
import homeEnv from "./home_env.json";
import homeRoutine from "./home_routine.json";
import s1Evaluate from "./s1_evaluate.json";
import s2Search from "./s2_search.json";
import s6Bundle from "./s6_bundle.json";
import s7Refine from "./s7_refine.json";

// JSON 을 읽으면 문자열 필드가 전부 string 으로 추론돼 유니온 타입과 맞지 않는다.
// 값 자체는 AI 테스트가 검증하므로 여기서는 단언한다.
const asResult = (value: unknown) => value as RecommendationResult;

export const recommendationV2Mocks = {
  s1Evaluate: asResult(s1Evaluate),
  s2Search: asResult(s2Search),
  s6Bundle: asResult(s6Bundle),
  s7Refine: asResult(s7Refine),
  homeRoutine: asResult(homeRoutine),
  homeEnv: asResult(homeEnv),
  clarify: asResult(clarify),
} satisfies Record<string, RecommendationResult>;
