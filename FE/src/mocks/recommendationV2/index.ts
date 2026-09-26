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

// JSON 을 import 하면 "ENV" 같은 값이 string 으로 추론돼 유니온 타입과 맞지 않는다.
// 좁히는 방향의 단언이라 구조가 틀리면 여기서 걸린다. unknown 을 거치지 않는
// 이유가 그것이다. 값이 실제로 맞는지는 AI 쪽 테스트가 검사한다.
export const recommendationV2Mocks = {
  s1Evaluate: s1Evaluate as RecommendationResult,
  s2Search: s2Search as RecommendationResult,
  s6Bundle: s6Bundle as RecommendationResult,
  s7Refine: s7Refine as RecommendationResult,
  homeRoutine: homeRoutine as RecommendationResult,
  homeEnv: homeEnv as RecommendationResult,
  clarify: clarify as RecommendationResult,
} satisfies Record<string, RecommendationResult>;
