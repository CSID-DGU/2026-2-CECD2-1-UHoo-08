import { useEffect, useState } from "react";
import { ArrowLeftRight, Check, Wallet } from "lucide-react";
import {
  apiErrorCode,
  getBundleSlotOptions,
  swapBundleProduct,
  type Bundle,
  type BundleSlot,
  type BundleSlotOptions,
} from "../../api/recommendationQueryApi";
import { BottomSheet } from "../common/BottomSheet";
import { ProductThumbnail } from "../common/ProductThumbnail";

const won = (value: number | null | undefined) =>
  value == null ? "가격 정보 없음" : `${value.toLocaleString("ko-KR")}원`;

/**
 * 예산 세트(S6) 결과. 조합을 고르고, 칸마다 다른 제품으로 바꿀 수 있다.
 *
 * 교체 후보와 바꿨을 때의 합계는 서버가 계산한다(예산을 넘는 후보는 고를 수 없게 표시).
 * 바꾸면 서버가 다시 계산한 조합으로 화면을 맞춘다.
 */
export function BundleResult({
  jobId,
  bundles,
  onChange,
}: {
  jobId: string;
  bundles: Bundle[];
  onChange: (bundle: Bundle) => void;
}) {
  const [active, setActive] = useState(bundles[0]?.index ?? 1);
  const [editing, setEditing] = useState<BundleSlot | null>(null);
  const bundle = bundles.find((b) => b.index === active) ?? bundles[0];
  if (!bundle) return null;

  const over = bundle.remaining != null && bundle.remaining < 0;

  return (
    <section className="mt-5" aria-label="예산 세트">
      <div className="flex items-center gap-2">
        <span className="grid h-7 w-7 place-items-center rounded-lg bg-surface-tint text-primary-800">
          <Wallet aria-hidden="true" className="h-4 w-4" strokeWidth={1.9} />
        </span>
        <h2 className="text-base font-semibold text-slate-800">예산 안에서 고른 세트</h2>
      </div>

      {/* 조합 고르기 */}
      <div role="tablist" aria-label="세트 조합" className="mt-3 grid gap-1 rounded-xl bg-surface-tint p-1" style={{ gridTemplateColumns: `repeat(${bundles.length}, minmax(0, 1fr))` }}>
        {bundles.map((b) => (
          <button
            key={b.index}
            type="button"
            role="tab"
            aria-selected={b.index === active}
            onClick={() => setActive(b.index)}
            className={`min-h-12 rounded-lg px-1 text-center ${b.index === active ? "bg-white shadow-sm" : ""}`}
          >
            <span className={`block text-xs font-semibold ${b.index === active ? "text-primary-900" : "text-slate-500"}`}>{b.label}</span>
            <span className="block text-[11px] tabular-nums text-slate-400">{won(b.total)}</span>
          </button>
        ))}
      </div>

      {/* 합계 */}
      <div className={`mt-3 rounded-2xl p-4 ${over ? "bg-red-50" : "bg-primary-50"}`}>
        <div className="flex items-end justify-between gap-2">
          <div>
            <p className="text-[11px] text-slate-500">합계</p>
            <p className="text-xl font-bold tabular-nums text-slate-800">{won(bundle.total)}</p>
          </div>
          <div className="text-right">
            <p className="text-[11px] text-slate-500">세트 적합도</p>
            <p className="text-base font-semibold tabular-nums text-primary-600">{bundle.totalScore}점</p>
          </div>
        </div>
        {bundle.remaining != null && (
          <p className={`mt-2 text-xs ${over ? "font-semibold text-red-700" : "text-slate-600"}`}>
            {over
              ? `예산보다 ${won(-bundle.remaining)} 넘어요`
              : `예산에서 ${won(bundle.remaining)} 남아요`}
          </p>
        )}
      </div>

      {/* 칸별 제품 */}
      <ol className="mt-3 grid gap-2">
        {bundle.slots.map((slot) => (
          <li key={slot.slotKey} className="flex items-center gap-3 rounded-2xl border border-slate-100 bg-white p-3">
            <ProductThumbnail className="h-12 w-12 shrink-0 rounded-xl bg-surface-tint" shape="bottle" />
            <div className="min-w-0 flex-1">
              <p className="text-[11px] font-semibold text-primary-600">{slot.label ?? slot.slotKey}</p>
              <p className="truncate text-caption text-slate-800">{slot.name}</p>
              <p className="mt-0.5 flex gap-2 text-[11px] tabular-nums text-slate-500">
                <span>{won(slot.price)}</span>
                {slot.score != null && <span>{slot.score}점</span>}
              </p>
            </div>
            <button
              type="button"
              onClick={() => setEditing(slot)}
              className="flex min-h-9 shrink-0 items-center gap-1 rounded-lg border border-slate-200 px-2.5 text-[11px] text-slate-600"
            >
              <ArrowLeftRight aria-hidden="true" className="h-3.5 w-3.5" /> 바꾸기
            </button>
          </li>
        ))}
      </ol>

      {editing && (
        <SwapSheet
          jobId={jobId}
          bundleIndex={bundle.index}
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

function SwapSheet({
  jobId,
  bundleIndex,
  slot,
  onClose,
  onSwapped,
}: {
  jobId: string;
  bundleIndex: number;
  slot: BundleSlot;
  onClose: () => void;
  onSwapped: (bundle: Bundle) => void;
}) {
  const [options, setOptions] = useState<BundleSlotOptions | null>(null);
  const [error, setError] = useState("");
  const [saving, setSaving] = useState<string | null>(null);

  // 시트가 열리면 이 칸의 후보를 받는다.
  useEffect(() => {
    let active = true;
    getBundleSlotOptions(jobId, bundleIndex, slot.slotKey)
      .then(({ data }) => {
        if (active) setOptions(Array.isArray(data?.options) ? data : { budget: null, currentTotal: 0, options: [] });
      })
      .catch(() => {
        if (active) setError("바꿀 후보를 불러오지 못했어요.");
      });
    return () => {
      active = false;
    };
  }, [jobId, bundleIndex, slot.slotKey]);

  async function pick(productId: string) {
    setSaving(productId);
    setError("");
    try {
      const { data } = await swapBundleProduct(jobId, bundleIndex, { slotKey: slot.slotKey, productId });
      onSwapped(data.bundle);
    } catch (e) {
      setError(apiErrorCode(e) === "BUNDLE_OVER_BUDGET" ? "이 제품으로 바꾸면 예산을 넘어요." : "바꾸지 못했어요. 다시 시도해주세요.");
    } finally {
      setSaving(null);
    }
  }

  return (
    <BottomSheet label={`${slot.label ?? "제품"} 바꾸기`} onClose={onClose}>
      <div className="px-5 pb-6 pt-3">
        <div className="flex items-center justify-between">
          <h2 className="text-body1 font-semibold text-slate-800">{slot.label ?? "제품"} 바꾸기</h2>
          <button type="button" aria-label="닫기" onClick={onClose} className="h-10 w-10 text-slate-400">
            ×
          </button>
        </div>
        {options?.budget != null && (
          <p className="mt-1 flex flex-wrap gap-x-3 text-caption text-slate-500">
            <span>예산 {won(options.budget)}</span>
            <span>지금 합계 {won(options.currentTotal)}</span>
          </p>
        )}
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
        {options && (
          <ul className="mt-4 grid gap-2">
            {options.options.map((option) => {
              const disabled = option.current || !option.selectable || saving != null;
              return (
                <li key={option.productId}>
                  <button
                    type="button"
                    disabled={disabled}
                    onClick={() => void pick(option.productId)}
                    className={`flex w-full items-center gap-3 rounded-2xl border p-3 text-left ${
                      option.current ? "border-primary-300 bg-primary-50" : "border-slate-100 bg-white"
                    } ${!option.selectable && !option.current ? "opacity-50" : ""}`}
                  >
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-caption font-medium text-slate-800">{option.name}</p>
                      <p className="mt-0.5 flex gap-2 text-[11px] tabular-nums text-slate-500">
                        <span>{won(option.price)}</span>
                        {option.score != null && <span>{option.score}점</span>}
                      </p>
                      <p className={`mt-0.5 text-[11px] tabular-nums ${option.selectable ? "text-slate-500" : "text-red-700"}`}>
                        {option.selectable
                          ? `바꾸면 합계 ${won(option.newTotal)}`
                          : `예산보다 ${won(option.overBudgetBy)} 넘어요`}
                      </p>
                    </div>
                    {option.current ? (
                      <span className="flex shrink-0 items-center gap-1 text-[11px] font-semibold text-primary-600">
                        <Check aria-hidden="true" className="h-3.5 w-3.5" /> 지금 제품
                      </span>
                    ) : (
                      option.selectable && (
                        <span className="shrink-0 text-[11px] font-semibold text-primary-600">
                          {saving === option.productId ? "바꾸는 중" : "선택"}
                        </span>
                      )
                    )}
                  </button>
                </li>
              );
            })}
          </ul>
        )}
      </div>
    </BottomSheet>
  );
}
