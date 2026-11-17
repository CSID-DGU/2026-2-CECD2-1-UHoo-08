import { useEffect, useState } from "react";
import { AlertTriangle, Clock } from "lucide-react";
import { getProductCompatibility, type ProductCompatibility } from "../../api/homeApi";

/**
 * 이 제품을 지금 쓰는 보유 제품과 같이 써도 되는지.
 *
 * 괜찮으면(OK) 아무것도 그리지 않는다. 판정 규칙이 아직 준비 중이라 OK 가 실제 판정이
 * 아닐 수 있어서, "같이 써도 괜찮아요"라고 단정하지 않는다.
 */
export function CompatibilityNotice({ productId }: { productId: string }) {
  const [result, setResult] = useState<{ id: string; value: ProductCompatibility } | null>(null);

  useEffect(() => {
    let active = true;
    getProductCompatibility(productId)
      .then(({ data }) => {
        if (active) setResult({ id: productId, value: data });
      })
      .catch(() => {});
    return () => {
      active = false;
    };
  }, [productId]);

  const value = result?.id === productId ? result.value : null;
  if (!value || value.level === "OK" || !value.pairs.length) return null;

  const avoid = value.level === "AVOID";
  return (
    <section
      aria-labelledby="compatibility-title"
      className={`mt-6 rounded-2xl p-4 ${avoid ? "bg-red-50" : "bg-[#FFF4E6]"}`}
    >
      <div className="flex items-center gap-2">
        {avoid ? (
          <AlertTriangle aria-hidden="true" className="h-4 w-4 text-red-700" />
        ) : (
          <Clock aria-hidden="true" className="h-4 w-4 text-[#C06F2A]" />
        )}
        <h2 id="compatibility-title" className={`text-sm font-semibold ${avoid ? "text-red-700" : "text-[#956022]"}`}>
          {value.bannerText ?? (avoid ? "쓰는 제품과 같이 쓰지 마세요" : "쓰는 제품과 시간을 나눠 쓰세요")}
        </h2>
      </div>
      <ul className="mt-3 grid gap-2">
        {value.pairs.map((pair) => (
          <li key={`${pair.userProductId}-${pair.ingredientA}-${pair.ingredientB}`} className="rounded-xl bg-white/70 p-3">
            <p className="text-xs font-semibold text-gray-500">
              {pair.userProductName} · {pair.title}
            </p>
            <p className="mt-1 text-[11px] leading-5 text-gray-400">
              {pair.ingredientA} + {pair.ingredientB}. {pair.reason}
            </p>
            {pair.schedule?.tip && <p className="mt-1 text-[11px] text-gray-500">{pair.schedule.tip}</p>}
          </li>
        ))}
      </ul>
      {value.basis.length > 0 && (
        <p className="mt-2 text-[10px] leading-4 text-gray-400">{value.basis.join(" · ")}</p>
      )}
    </section>
  );
}
