// Stage names reported by the recommendation status API, with readable labels.
export const RECOMMENDATION_STAGES = [
  { label: "조건 파악", description: "원하는 조건과 피부 정보를 확인하고 있어요", keys: ["normalize", "요청 이해", "조건 파악"] },
  { label: "후보 제품 찾기", description: "조건에 맞는 후보와 기준 제품을 확인하고 있어요", keys: ["retrieve", "discovery", "조건에 맞는 상품 찾기", "기준 상품 확인"] },
  { label: "보유 제품 · 성분 충돌 확인", description: "보유 제품과 중복되거나 충돌하는 후보를 확인하고 있어요", keys: ["inventory", "prefilter", "보유 제품 불러오기", "이미 가진 것·충돌 거르기"] },
  { label: "피부 적합도 비교", description: "피부 타입과 요청 조건을 기준으로 적합도를 비교하고 있어요", keys: ["score", "score_lite", "적합도 계산", "추가 후보 검증"] },
  { label: "비슷한 사용자 후기 확인", description: "비슷한 피부를 가진 분들의 선택을 살펴보고 있어요", keys: ["collaborative", "비슷한 사람들의 선택 보기"] },
  { label: "추천 이유 · 결과 정리", description: "추천 이유를 정리하고 결과의 표현을 점검하고 있어요", keys: ["compose", "guard", "결과 정리", "표현 점검"] },
];

export function recommendationStageIndex(step: string) {
  return RECOMMENDATION_STAGES.findIndex(stage => stage.keys.includes(step));
}
