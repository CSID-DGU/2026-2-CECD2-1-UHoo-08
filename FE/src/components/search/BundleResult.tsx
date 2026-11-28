import { useEffect, useMemo, useState } from "react";
import { ArrowLeft, ArrowRight } from "lucide-react";
import {
  apiErrorCode,
  getBundleSlotOptions,
  swapBundleProduct,
  type Bundle,
  type BundleSlot,
  type BundleSlotOptions,
} from "../../api/recommendationQueryApi";
import { ProductThumbnail } from "../common/ProductThumbnail";

type SlotOption = BundleSlotOptions["options"][number];

// 병 모양 썸네일은 큰 칸용 크기라(76px) 이 화면의 56px 칸에 맞게 줄인다
const THUMB = "h-14 w-14 shrink-0 overflow-hidden rounded-xl bg-surface-tint [&>div]:scale-[0.65]";

const won = (value: number | null | undefined) =>
  value == null ? "가격 정보 없음" : `${value.toLocaleString("ko-KR")}원`;

/** 50000 → "5만원". 만 원 단위가 아니면 그대로 적는다 */
const budgetLabel = (value: number) =>
  value % 10000 === 0 ? `${value / 10000}만원` : won(value);

const COUNT_WORD = ["", "한", "두", "세", "네", "다섯", "여섯", "일곱", "여덟"];
const countWord = (n: number) => COUNT_WORD[n] ?? String(n);

const CIRCLED = ["①", "②", "③", "④", "⑤", "⑥", "⑦", "⑧", "⑨"];
const circled = (index: number) => CIRCLED[index - 1] ?? `${index}.`;

/** 받침이 있으면 "은", 없으면 "는" */
const topicJosa = (word: string) => {
  const code = word.charCodeAt(word.length - 1) - 0xac00;
  return code >= 0 && code <= 11171 && code % 28 !== 0 ? "은" : "는";
};

/**
 * 조합 성격 설명. AI 가 성격 이름만 주므로(rules/bundle_pick.py) 이름으로 문장을 고른다.
 * 모르는 이름이면 설명 없이 이름만 보여준다.
 */
function bundleDescription(label: string, slotCount: number): string | null {
  if (label === "균형형") return `${countWord(slotCount)} 단계 점수가 고르게 높아요`;
  if (label === "알뜰형") return "점수는 지키면서 가장 적게 들어요";
  if (label === "가성비형") return "같은 돈으로 점수를 가장 많이 받아요";
  if (label.endsWith(" 집중형")) return `${label.replace(" 집중형", "")}에 가장 좋은 제품을 넣었어요`;
  if (label === "최저가 조합") return "예산 안에서는 다 채울 수 없어 가장 싸게 맞췄어요";
  if (label === "다른 조합") return "점수 순으로 고른 다른 조합이에요";
  return null;
}

/** 조합의 예산. 예산이 없는 결과면 null */
const budgetOf = (bundle: Bundle) =>
  bundle.remaining == null ? null : bundle.total + bundle.remaining;

/**
 * 예산 세트(S6) 결과. 조합을 고르고, 칸마다 다른 제품으로 바꿀 수 있다.
 *
 * 세트 총점은 칸 점수의 합이다(BE ResultAssembler). 칸마다 1등을 고르면 예산을 넘기 쉬워
 * AI 가 합계 기준으로 조합을 골랐고, 화면도 합으로 비교하게 보여준다.
 * 교체 후보와 바꿨을 때의 합계는 서버가 계산한다(예산을 넘는 후보는 고를 수 없게 표시).
 */
export function BundleResult({
  jobId,
  bundles,
  onChange,
  onSaveAll,
}: {
  jobId: string;
  bundles: Bundle[];
  onChange: (bundle: Bundle) => void;
  /** 조합의 제품을 찜 목록에 담는다. 담기 API 가 없어 찜으로 대신한다 */
  onSaveAll?: (productIds: string[]) => Promise<void>;
}) {
  const [active, setActive] = useState(bundles[0]?.index ?? 1);
  const [editing, setEditing] = useState<BundleSlot | null>(null);
  // 조합마다 따로 담으므로 담은 상태도 조합별로 둔다
  const [saveStates, setSaveStates] = useState<Record<number, "saving" | "saved" | "failed">>({});
  const bundle = bundles.find((b) => b.index === active) ?? bundles[0];

  if (!bundle) return null;

  const saveState = saveStates[bundle.index] ?? "idle";
  const setSaveState = (state: "saving" | "saved" | "failed") =>
    setSaveStates((previous) => ({ ...previous, [bundle.index]: state }));

  const budget = budgetOf(bundle);
  const over = bundle.remaining != null && bundle.remaining < 0;
  const allOver = bundles.every((b) => b.remaining != null && b.remaining < 0);
  const description = bundleDescription(bundle.label, bundle.slots.length);

  async function saveAll() {
    if (!onSaveAll || saveState === "saving") return;
    setSaveState("saving");
    try {
      await onSaveAll(bundle.slots.map((slot) => slot.productId));
      setSaveState("saved");
    } catch {
      setSaveState("failed");
    }
  }

  return (
    <section className="mt-5" aria-label="예산 세트">
      <h2 className="whitespace-pre-line text-lg font-bold leading-7 text-slate-800">
        {allOver
          ? "예산 안에서는 모든 칸을\n채울 수 없었어요"
          : budget != null
            ? `${budgetLabel(budget)} 안에서 짤 수 있는\n조합 ${bundles.length}가지를 가져왔어요`
            : `조합 ${bundles.length}가지를 가져왔어요`}
      </h2>
      <p className="mt-2 text-caption leading-5 text-slate-500">
        {allOver
          ? "가장 저렴하게 맞춘 조합이에요. 칸을 바꿔 보거나 예산을 늘려 다시 찾아보세요."
          : "칸마다 1등만 고르면 예산을 넘기 쉬워요. 합쳐서 가장 좋은 쪽으로 골랐어요."}
      </p>

      {/* 고른 조합 */}
      <div className="mt-4 rounded-2xl border border-primary-300 bg-white p-4">
        <div className="flex flex-wrap items-center gap-2">
          <span className="rounded-md bg-primary-600 px-2 py-0.5 text-[11px] font-semibold text-white">
            {circled(bundle.index)} {bundle.label}
          </span>
          {description && <span className="text-[11px] text-slate-500">{description}</span>}
        </div>
        <div className="mt-3 flex items-end justify-between">
          <span className="text-caption text-slate-500">합계</span>
          <span className="text-xl font-bold tabular-nums text-slate-800">{won(bundle.total)}</span>
        </div>
        {bundle.remaining != null && (
          <p
            className={`mt-2 rounded-lg px-3 py-1.5 text-[11px] tabular-nums ${
              over ? "bg-red-50 font-semibold text-red-700" : "bg-primary-50 text-primary-700"
            }`}
          >
            {over ? `예산보다 ${won(-bundle.remaining)} 넘어요` : `예산까지 ${won(bundle.remaining)} 남았어요`}
          </p>
        )}
        {over && bundle.label === "최저가 조합" && (
          <p className="mt-1 text-[11px] text-slate-400">예산 안에서는 모든 칸을 채울 수 없어요</p>
        )}

        <ol className="mt-3 grid gap-3">
          {bundle.slots.map((slot) => (
            <li key={slot.slotKey} className="flex items-center gap-3">
              <ProductThumbnail className={THUMB} shape="bottle" />
              <div className="min-w-0 flex-1">
                <span className="inline-block rounded-md bg-primary-50 px-1.5 py-0.5 text-[11px] font-semibold text-primary-600">
                  {slot.label ?? slot.slotKey}
                </span>
                <p className="mt-1 truncate text-caption text-slate-800">{slot.name}</p>
                <p className="text-[11px] tabular-nums text-slate-500">{won(slot.price)}</p>
              </div>
              <div className="flex shrink-0 flex-col items-end gap-1">
                {slot.score != null && (
                  <span className="text-body2 font-semibold tabular-nums text-primary-600">{slot.score}점</span>
                )}
                <button
                  type="button"
                  onClick={() => setEditing(slot)}
                  className="min-h-8 rounded-lg border border-slate-200 px-2.5 text-[11px] text-slate-600"
                >
                  바꾸기
                </button>
              </div>
            </li>
          ))}
        </ol>
      </div>

      {/* 다른 조합 */}
      {bundles.length > 1 && (
        <>
          <div className="mt-6 flex items-center justify-between">
            <h3 className="text-body2 font-semibold text-slate-800">다른 조합</h3>
            <span className="text-[11px] text-slate-400">
              총점 = {countWord(bundle.slots.length)} 제품 적합도 합
            </span>
          </div>
          <ul className="mt-2 grid gap-2">
            {bundles.map((b) => {
              const selected = b.index === bundle.index;
              return (
                <li key={b.index}>
                  <button
                    type="button"
                    aria-pressed={selected}
                    onClick={() => setActive(b.index)}
                    className={`flex min-h-12 w-full items-center gap-3 rounded-xl border px-3 text-left ${
                      selected ? "border-primary-300 bg-primary-50" : "border-slate-100 bg-white"
                    }`}
                  >
                    <span
                      className={`grid h-6 w-6 shrink-0 place-items-center rounded-md text-[11px] font-semibold ${
                        selected ? "bg-primary-600 text-white" : "bg-slate-100 text-slate-500"
                      }`}
                    >
                      {b.index}
                    </span>
                    <span className="min-w-0 flex-1 truncate text-caption font-medium text-slate-800">{b.label}</span>
                    <span className="shrink-0 text-[11px] tabular-nums text-slate-500">{won(b.total)}</span>
                    <span
                      className={`w-12 shrink-0 text-right text-caption font-semibold tabular-nums ${
                        selected ? "text-primary-600" : "text-slate-500"
                      }`}
                    >
                      {b.totalScore}점
                    </span>
                  </button>
                </li>
              );
            })}
          </ul>
        </>
      )}

      {onSaveAll && (
        <div className="mt-5">
          <button
            type="button"
            onClick={() => void saveAll()}
            disabled={saveState === "saving" || saveState === "saved"}
            className="h-12 w-full rounded-xl bg-primary-600 text-body2 font-semibold text-white disabled:opacity-60"
          >
            {saveState === "saving" ? "담는 중" : saveState === "saved" ? "찜 목록에 담았어요" : "이 조합 담기"}
          </button>
          {saveState === "failed" && (
            <p role="alert" className="mt-2 text-center text-[11px] text-red-700">
              담지 못했어요. 다시 시도해주세요.
            </p>
          )}
        </div>
      )}

      {editing && (
        <SwapPage
          jobId={jobId}
          bundle={bundle}
          otherCount={bundles.length - 1}
          slot={editing}
          onClose={() => setEditing(null)}
          onSwapped={(updated) => {
            onChange(updated);
            setEditing(null);
          }}
        />
      )}
    </section>
  );
}

/** 지금 제품 → 예산 안의 후보(점수순) → 예산을 넘는 후보(점수순) */
function orderOptions(options: SlotOption[]): SlotOption[] {
  const byScore = (a: SlotOption, b: SlotOption) => (b.score ?? -1) - (a.score ?? -1);
  return [
    ...options.filter((o) => o.isCurrent),
    ...options.filter((o) => !o.isCurrent && o.selectable).sort(byScore),
    ...options.filter((o) => !o.isCurrent && !o.selectable).sort(byScore),
  ];
}

/** 칸 하나 바꾸기. 고른 뒤 [이걸로 바꾸기]를 눌러야 바뀐다 */
function SwapPage({
  jobId,
  bundle,
  otherCount,
  slot,
  onClose,
  onSwapped,
}: {
  jobId: string;
  bundle: Bundle;
  otherCount: number;
  slot: BundleSlot;
  onClose: () => void;
  onSwapped: (bundle: Bundle) => void;
}) {
  const [options, setOptions] = useState<BundleSlotOptions | null>(null);
  const [picked, setPicked] = useState<string>(slot.productId);
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);
  const label = slot.label ?? "제품";

  // 화면이 열리면 이 칸의 후보를 받는다.
  useEffect(() => {
    let active = true;
    getBundleSlotOptions(jobId, bundle.index, slot.slotKey)
      .then(({ data }) => {
        if (active) setOptions(Array.isArray(data?.options) ? data : { budget: null, currentTotal: bundle.total, options: [] });
      })
      .catch(() => {
        if (active) setError("바꿀 후보를 불러오지 못했어요.");
      });
    return () => {
      active = false;
    };
  }, [jobId, bundle.index, bundle.total, slot.slotKey]);

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => event.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const ordered = useMemo(() => orderOptions(options?.options ?? []), [options]);
  const current = ordered.find((o) => o.isCurrent);
  const chosen = ordered.find((o) => o.productId === picked) ?? current;
  const changed = chosen != null && !chosen.isCurrent;
  const currentTotal = options?.currentTotal ?? bundle.total;
  // 지금 제품보다 점수가 높은데 예산 때문에 못 고르는 후보가 있으면 이유를 알려준다
  const blockedBetter = ordered.some(
    (o) => !o.selectable && !o.isCurrent && (o.score ?? 0) > (current?.score ?? slot.score ?? 0),
  );
  const others = bundle.slots.filter((s) => s.slotKey !== slot.slotKey).map((s) => s.label ?? "다른 칸");
  const othersText = others.length ? `${others.join("·")}${topicJosa(others[others.length - 1])} 그대로 두고 ` : "";

  async function confirm() {
    if (!chosen || !changed || saving) return;
    setSaving(true);
    setError("");
    try {
      const { data } = await swapBundleProduct(jobId, bundle.index, { slotKey: slot.slotKey, productId: chosen.productId });
      onSwapped(data.bundle);
    } catch (e) {
      setError(apiErrorCode(e) === "BUNDLE_OVER_BUDGET" ? "이 제품으로 바꾸면 예산을 넘어요." : "바꾸지 못했어요. 다시 시도해주세요.");
      setSaving(false);
    }
  }

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label={`${label} 바꾸기`}
      className="fixed inset-y-0 left-1/2 z-50 flex w-full max-w-[430px] -translate-x-1/2 flex-col bg-white"
    >
      <header className="relative flex h-14 shrink-0 items-center justify-center">
        <button type="button" aria-label="뒤로" onClick={onClose} className="absolute left-3 grid h-10 w-10 place-items-center text-slate-700">
          <ArrowLeft aria-hidden="true" className="h-5 w-5" />
        </button>
        <h2 className="text-body1 font-semibold text-slate-800">{label} 바꾸기</h2>
      </header>

      <div className="flex-1 overflow-y-auto px-5 pb-6">
        {/* 바꾸기 전후 */}
        <div className="rounded-2xl border border-primary-300 bg-primary-50 p-4">
          <div className="flex items-center justify-between text-[11px]">
            <span className="font-semibold text-primary-700">
              {circled(bundle.index)} {bundle.label} 유지 중
            </span>
            <span className="text-slate-500">남은 예산</span>
          </div>
          <div className="mt-1 flex items-end justify-between gap-2">
            <p className="flex items-center gap-2 text-lg font-bold tabular-nums text-slate-800">
              {won(currentTotal)}
              {changed && (
                <>
                  <ArrowRight aria-hidden="true" className="h-4 w-4 text-slate-400" />
                  <span className="text-primary-600">{won(chosen.newTotal)}</span>
                </>
              )}
            </p>
            <span className="text-body2 font-semibold tabular-nums text-primary-700">
              {chosen?.remaining != null ? won(chosen.remaining) : bundle.remaining != null ? won(bundle.remaining) : "-"}
            </span>
          </div>
          <p className="mt-1 text-[11px] text-slate-500">
            {othersText}
            {label}만 바꿔요
          </p>
        </div>

        <div className="mt-5 flex items-center justify-between">
          <h3 className="text-body2 font-semibold text-slate-800">바꿀 수 있는 {label}</h3>
          <span className="text-[11px] text-primary-600">적합도순</span>
        </div>

        {!options && !error && (
          <p role="status" className="mt-6 text-center text-caption text-slate-400">
            후보를 불러오고 있어요
          </p>
        )}
        {error && (
          <p role="alert" className="mt-3 text-caption text-red-700">
            {error}
          </p>
        )}

        <ul className="mt-3 grid gap-2">
          {ordered.map((option) => {
            const selected = option.productId === chosen?.productId;
            const blocked = !option.selectable && !option.isCurrent;
            return (
              <li key={option.productId}>
                <button
                  type="button"
                  aria-pressed={selected}
                  disabled={blocked || saving}
                  onClick={() => setPicked(option.productId)}
                  className={`flex w-full items-center gap-3 rounded-2xl border p-3 text-left ${
                    selected ? "border-primary-300 bg-primary-50" : "border-slate-100 bg-white"
                  } ${blocked ? "opacity-60" : ""}`}
                >
                  <ProductThumbnail className={THUMB} shape="bottle" />
                  <div className="min-w-0 flex-1">
                    <p className={`truncate text-caption ${blocked ? "text-slate-500" : "text-slate-800"}`}>{option.name}</p>
                    <p className="text-body2 font-semibold tabular-nums text-slate-800">{won(option.price)}</p>
                    {option.isCurrent ? (
                      <span className="mt-0.5 inline-block rounded-md bg-primary-600 px-1.5 py-0.5 text-[11px] font-semibold text-white">
                        지금 이 제품
                      </span>
                    ) : blocked ? (
                      <p className="mt-0.5 flex items-center gap-1.5 text-[11px] tabular-nums text-slate-500">
                        <span className="rounded bg-red-50 px-1.5 py-0.5 font-semibold text-red-700">예산 초과</span>
                        총액 {won(option.newTotal)} — {won(option.overBudgetBy)} 초과
                      </p>
                    ) : (
                      <p className="mt-0.5 text-[11px] tabular-nums text-slate-500">
                        총액 {won(option.newTotal)}
                        {option.remaining != null && ` · ${won(option.remaining)} 남아요`}
                      </p>
                    )}
                  </div>
                  {option.score != null && (
                    <span className={`shrink-0 text-body2 font-semibold tabular-nums ${blocked ? "text-slate-400" : "text-primary-600"}`}>
                      {option.score}점
                    </span>
                  )}
                </button>
              </li>
            );
          })}
        </ul>

        {blockedBetter && (
          <div className="mt-4 rounded-xl bg-slate-100 p-4">
            <p className="text-caption font-semibold text-slate-700">점수가 더 높아도 못 고르는 경우가 있어요</p>
            <p className="mt-1 text-[11px] text-slate-500">한 칸을 올리면 다른 칸이 내려가요. 합계로 보셔야 해요.</p>
          </div>
        )}
      </div>

      <div className="shrink-0 border-t border-slate-100 bg-white px-5 pb-[calc(16px+env(safe-area-inset-bottom,0px))] pt-3">
        <div className="grid grid-cols-2 gap-2">
          <button type="button" onClick={onClose} className="h-12 rounded-xl border border-slate-200 text-body2 text-slate-600">
            그대로 두기
          </button>
          <button
            type="button"
            onClick={() => void confirm()}
            disabled={!changed || saving}
            className="h-12 rounded-xl bg-primary-600 text-body2 font-semibold text-white disabled:opacity-40"
          >
            {saving ? "바꾸는 중" : "이걸로 바꾸기"}
          </button>
        </div>
        {otherCount > 0 && (
          <p className="mt-2 text-center text-[11px] text-slate-400">바꿔도 다른 조합 {otherCount}개는 그대로 남아 있어요</p>
        )}
      </div>
    </div>
  );
}
