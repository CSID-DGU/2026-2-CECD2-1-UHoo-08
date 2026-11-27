import { Sparkles } from "lucide-react";
import type { ResultItem } from "../../api/recommendationQueryApi";
import { ProductThumbnail } from "../common/ProductThumbnail";

/** 총점에 붙이는 한 줄. 상품 기준 추천 보고서(matchLabel)와 같은 구간을 쓴다. */
function scoreLabel(score: number) {
  if (score >= 85) return "인생템 확률 매칭";
  if (score >= 70) return "높은 적합도";
  if (score >= 50) return "괜찮은 선택";
  return "아쉬운 매칭";
}

/**
 * 실수 몫들을 정수로 나누되 합이 total 이 되게 한다(최대 나머지 방식).
 * 따로 반올림하면 만점 합이 101 이 되거나, 항목 점수 합이 총점과 1 점씩 어긋난다.
 */
function apportion(values: number[], total: number): number[] {
  const sum = values.reduce((a, b) => a + b, 0);
  if (sum <= 0) return values.map(() => 0);
  const exact = values.map((v) => (v / sum) * total);
  const floors = exact.map(Math.floor);
  let left = total - floors.reduce((a, b) => a + b, 0);
  const order = exact
    .map((v, i) => ({ i, rest: v - Math.floor(v) }))
    .sort((a, b) => b.rest - a.rest);
  for (const { i } of order) {
    if (left <= 0) break;
    floors[i] += 1;
    left -= 1;
  }
  return floors;
}

/** 결과 카드 배지 종류(AI contracts) 별 짧은 이름 */
const BADGE_LABEL: Record<string, string> = {
  CONFLICT_SEPARATE: "함께 쓸 때",
  ENV: "요즘 환경",
  VALUE: "가성비",
  TREND: "요즘 인기",
};

const won = (value: number | null) =>
  value == null ? "가격 정보 없음" : `${value.toLocaleString("ko-KR")}원`;

/**
 * "이 제품 어때?"(S1_EVALUATE) 결과 보고서.
 *
 * 평가한 제품 하나(items[0])의 총점과 점수 분해를 보여준다. 신형식 breakdown 은 항목마다
 * score(0~100)와 weight(0~1)를 주고 총점은 둘을 곱해 더한 값이라, 항목을
 * "가중치 만큼의 만점 중 몇 점"(예: 28 / 30)으로 그린다. 가중치가 0인 항목은 총점에
 * 들어가지 않으니 뺀다. 비슷한 사람들 제품과 대체 제품은 검색 결과 화면이 아래에 그린다.
 */
export function EvaluationReport({
  item,
  onOpen,
}: {
  item: ResultItem;
  onOpen: () => void;
}) {
  const total = item.totalScore;
  const weighted = (item.breakdown ?? []).filter((row) => row.weight > 0);
  // 항목별 만점은 가중치 비율대로 100 점을 나눈다. 가중치는 사용자마다(피드백으로) 달라져
  // 30·25 처럼 딱 떨어지지 않을 수 있다.
  const maxes = apportion(weighted.map((row) => row.weight), 100);
  // 항목 점수는 score × weight 비율대로 총점을 나눠, 합이 위의 총점과 같게 한다.
  const earned = weighted.map((row) => row.score * row.weight);
  const pointsList =
    total != null
      ? apportion(earned, total)
      : earned.map((value) => Math.round(value));
  const rows = weighted
    .map((row, i) => ({
      key: row.key,
      label: row.label,
      max: maxes[i],
      points: Math.min(maxes[i], pointsList[i]),
    }))
    .filter((row) => row.max > 0);
  const badges = (item.badges ?? []).filter((badge) => badge.text);

  return (
    <section className="mt-4" aria-label="추천 결과 보고서">
      {/* 총점 */}
      {total != null && (
        <div className="relative overflow-hidden rounded-2xl bg-gray-500 p-6 text-white">
          <p className="text-caption text-primary-300">AI 매칭 완료</p>
          <p className="mt-1 text-[40px] font-bold leading-none tabular-nums">
            {total}
            <span className="text-body1"> 점</span>
          </p>
          <p className="mt-3 text-caption text-primary-300">{scoreLabel(total)}</p>
          <span aria-hidden="true" className="absolute right-10 top-4 h-[84px] w-[84px] rounded-full bg-gray-400" />
          <span aria-hidden="true" className="absolute right-5 top-14 h-[60px] w-[60px] rounded-full bg-primary-700" />
          <Sparkles aria-hidden="true" className="absolute right-[62px] top-[66px] h-6 w-6 text-white" />
        </div>
      )}

      {/* 점수 분해 */}
      {rows.length > 0 && (
        <div className="mt-3 rounded-xl border border-slate-200 bg-white p-4">
          <h2 className="text-body2 font-semibold text-slate-800">이 점수는 이렇게 나왔어요</h2>
          <ul className="mt-3 grid gap-3">
            {rows.map((row) => (
              <li key={row.key}>
                <div className="flex items-baseline justify-between gap-2">
                  <span className="text-caption font-semibold text-slate-700">{row.label}</span>
                  <span className="text-caption tabular-nums text-slate-500">
                    <span className="font-semibold text-primary-600">{row.points}</span> / {row.max}
                  </span>
                </div>
                <div
                  className="mt-1.5 h-1.5 overflow-hidden rounded-full bg-primary-50"
                  role="meter"
                  aria-label={row.label}
                  aria-valuemin={0}
                  aria-valuemax={row.max}
                  aria-valuenow={row.points}
                >
                  <div
                    className="h-full w-full origin-left rounded-full bg-primary-500"
                    style={{ transform: `scaleX(${row.max ? row.points / row.max : 0})` }}
                  />
                </div>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* AI 가 분석한 이유 */}
      {item.reason && (
        <div className="mt-3 rounded-xl border border-primary-100 bg-primary-50 p-4">
          <h2 className="text-body2 font-semibold text-primary-600">AI가 분석한 추천 이유</h2>
          <p className="mt-2 text-caption leading-6 text-slate-600">{item.reason}</p>
          {badges.length > 0 && (
            <ul className="mt-3 grid gap-1.5">
              {badges.map((badge) => (
                <li key={`${badge.type}-${badge.text}`} className="text-caption leading-5 text-slate-600">
                  <span className="mr-1.5 font-semibold text-primary-600">{BADGE_LABEL[badge.type] ?? "참고"}</span>
                  {badge.text}
                </li>
              ))}
            </ul>
          )}
        </div>
      )}

      {/* 평가한 제품 */}
      <h2 className="mt-5 text-base font-semibold text-slate-800">평가한 제품</h2>
      <button
        type="button"
        onClick={onOpen}
        className="mt-3 flex w-full items-center gap-4 rounded-xl border border-primary-300 bg-white p-4 text-left"
      >
        <div className="grid h-[64px] w-[64px] shrink-0 place-items-center overflow-hidden rounded-xl bg-primary-50">
          {item.imageUrl ? (
            <img src={item.imageUrl} alt="" className="h-full w-full object-contain" />
          ) : (
            <ProductThumbnail className="h-full w-full bg-primary-50" shape={item.name.includes("쿠션") ? "cushion" : "bottle"} />
          )}
        </div>
        <div className="min-w-0 flex-1">
          <p className="truncate text-caption text-slate-500">{item.brand}</p>
          <p className="truncate text-body2 text-slate-800">{item.name}</p>
          <p className="mt-1 text-body2 font-semibold tabular-nums text-primary-600">{won(item.price)}</p>
        </div>
        {total != null && (
          <div className="shrink-0 text-right">
            <p className="text-h3 tabular-nums text-primary-600">{total}점</p>
            <p className="text-caption text-slate-500">매칭</p>
          </div>
        )}
      </button>
    </section>
  );
}
