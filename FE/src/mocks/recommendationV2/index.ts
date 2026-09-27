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

// JSON 을 import 하면 "ENV" 같은 값이 string 으로 추론돼 유니온 타입과 맞지 않아
// 단언이 필요하다. 좁히는 방향의 단언이라 필드가 빠지면 여기서 걸리지만,
// scenario 나 배지 종류가 잘못된 값인지까지는 tsc 가 보지 못한다.
// 그쪽은 AI/tests/v2/test_result_mocks.py 가 스키마로 검사한다.
//
// 단언한 값에 satisfies 를 붙여 봐야 단언된 타입만 다시 볼 뿐이라 쓰지 않는다.
export const recommendationV2Mocks = {
  s1Evaluate: s1Evaluate as RecommendationResult,
  s2Search: s2Search as RecommendationResult,
  s6Bundle: s6Bundle as RecommendationResult,
  s7Refine: s7Refine as RecommendationResult,
  homeRoutine: homeRoutine as RecommendationResult,
  homeEnv: homeEnv as RecommendationResult,
  clarify: clarify as RecommendationResult,
};
