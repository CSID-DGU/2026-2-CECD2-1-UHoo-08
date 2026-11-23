import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { ChevronRight, Droplets, Sun, Wind } from "lucide-react";
import { getMyProfile } from "../../api/userApi";
import { getMyProducts, type MyProduct } from "../../api/myProductApi";
import { RecentlyViewed } from "./RecentlyViewed";
import { care } from "../../lib/careBase";
import type { EnvironmentResponse } from "../../kiosk/lib/types";
import {
  getHomeEnvironmentRecommendation,
  getRoutineCheck,
  getTrendProducts,
  type EnvironmentRecommendation,
  type RoutineCheck,
  type TrendProducts,
} from "../../api/homeApi";
import { apiErrorCode } from "../../api/recommendationQueryApi";
import { ProductThumbnail } from "../common/ProductThumbnail";

export function HomeOverview() {
  const navigate = useNavigate();
  const [environment, setEnvironment] = useState<EnvironmentResponse | null>(
    null,
  );
  const [products, setProducts] = useState<MyProduct[] | null>(null);
  const [environmentState, setEnvironmentState] = useState("loading");
  const [productsState, setProductsState] = useState("loading");
  const [attempt, setAttempt] = useState(0);
  // BE 홈 카드. 실패해도 홈은 그대로 보이게 각각 따로 받는다.
  const [envReco, setEnvReco] = useState<EnvironmentRecommendation | "no-region" | null>(null);
  const [routine, setRoutine] = useState<RoutineCheck | null>(null);
  // null: 불러오는 중, "error": 실패. 빈 목록은 성공했지만 집계가 없다는 뜻이다.
  const [trends, setTrends] = useState<TrendProducts | "error" | null>(null);
  const [trendAttempt, setTrendAttempt] = useState(0);

  useEffect(() => {
    let active = true;
    getHomeEnvironmentRecommendation()
      .then(({ data }) => { if (active) setEnvReco(data); })
      .catch((error) => { if (active && apiErrorCode(error) === "REGION_NOT_SET") setEnvReco("no-region"); });
    getRoutineCheck()
      .then(({ data }) => { if (active) setRoutine(data); })
      .catch(() => {});
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    let active = true;
    getTrendProducts()
      .then(({ data }) => {
        if (active) setTrends(Array.isArray(data?.items) ? data : "error");
      })
      .catch(() => {
        if (active) setTrends("error");
      });
    return () => {
      active = false;
    };
  }, [trendAttempt]);

  useEffect(() => {
    let active = true;
    setEnvironmentState("loading");
    setProductsState("loading");
    getMyProfile()
      .then(({ data }) => {
        if (!active) return;
        void care
          .get<EnvironmentResponse>(
            `/api/care/environment?user_id=${encodeURIComponent(data.id)}`,
          )
          .then((value) => {
            if (active) {
              setEnvironment(value);
              setEnvironmentState("ready");
            }
          })
          .catch(() => {
            if (active) setEnvironmentState("error");
          });
        void getMyProducts(data.id)
          .then((value) => {
            if (active) {
              setProducts(value);
              setProductsState("ready");
            }
          })
          .catch(() => {
            if (active) setProductsState("error");
          });
      })
      .catch(() => {
        if (active) {
          setEnvironmentState("error");
          setProductsState("error");
        }
      });
    return () => {
      active = false;
    };
  }, [attempt]);

  const outdoor = environment?.outdoor;
  const measuredAt = outdoor?.observed_at
    ? new Date(outdoor.observed_at)
    : null;
  const timestamp =
    measuredAt && Number.isFinite(measuredAt.getTime())
      ? measuredAt.toLocaleString("ko-KR", {
          month: "numeric",
          day: "numeric",
          hour: "2-digit",
          minute: "2-digit",
        })
      : null;
  const stats = [
    { label: "자외선 지수", value: outdoor?.uv_index, unit: "", Icon: Sun },
    { label: "초미세먼지", value: outdoor?.pm25, unit: "㎍/㎥", Icon: Wind },
    { label: "실외 습도", value: outdoor?.humidity, unit: "%", Icon: Droplets },
  ];

  return (
    <div className="mt-5 space-y-3">
      <section
        className="rounded-2xl border border-primary-200 bg-white p-3"
        aria-labelledby="home-environment"
      >
        <button
          type="button"
          onClick={() => navigate("/environment")}
          aria-label="요즘 지내는 환경 자세히 보기"
          className="flex w-full items-start justify-between gap-2 text-left"
        >
          <div>
            <h2
              id="home-environment"
              className="text-sm font-semibold text-primary-600"
            >
              요즘 지내는 환경
            </h2>
            <p className="mt-0.5 flex gap-2 text-[11px] text-gray-300">
              <span>{outdoor?.region || "생활 환경"}</span>
              <span>{timestamp ? `${timestamp} 관측` : "최근 측정값"}</span>
            </p>
          </div>
          <span className="flex items-center gap-0.5 rounded-md bg-primary-50 px-2 py-1 text-[11px] text-primary-600">
            현재 환경 <ChevronRight aria-hidden="true" className="h-3 w-3" />
          </span>
        </button>
        {environmentState === "loading" ? (
          <p
            role="status"
            className="py-6 text-center text-[11px] text-gray-300"
          >
            환경 정보를 불러오고 있어요
          </p>
        ) : environmentState === "error" ? (
          <div className="py-4 text-center text-[11px] text-gray-300">
            <p>환경 정보를 불러오지 못했어요.</p>
            <button
              type="button"
              className="mt-2 p-2 text-primary-600"
              onClick={() => setAttempt((value) => value + 1)}
            >
              다시 불러오기
            </button>
          </div>
        ) : (
          <>
            <div className="mt-2 grid grid-cols-3 divide-x divide-line-tint">
              {stats.map(({ label, value, unit, Icon }) => (
                <div
                  key={label}
                  className="px-1 py-2 text-center"
                >
                  <Icon
                    className="mx-auto mb-1 h-4 w-4 text-primary-200"
                    aria-hidden="true"
                  />
                  <p className="text-[11px] text-gray-400">{label}</p>
                  <p className="mt-0.5 text-base font-bold text-gray-500">
                    {value == null ? (
                      "미측정"
                    ) : (
                      <>
                        {value}
                        <span className="ml-0.5 text-[11px] font-normal">
                          {unit}
                        </span>
                      </>
                    )}
                  </p>
                </div>
              ))}
            </div>
            <div className="mt-3 border-t border-dashed border-line-tint pt-3">
              <p className="text-[11px] font-semibold text-gray-500">
                환경에 맞춰 루틴 살펴보기
              </p>
              <EnvRecoSummary value={envReco} onSetRegion={() => navigate("/environment")} />
              <div className="mt-2 flex items-center justify-between gap-2">
                <span className="text-[11px] text-gray-300">
                  측정 환경을 참고해 제품을 확인해요
                </span>
                <button
                  type="button"
                  className="flex shrink-0 items-center gap-0.5 py-1 text-[11px] text-primary-600"
                  onClick={() => navigate("/recommendation/care")}
                >
                  제품 보기 <ChevronRight aria-hidden="true" className="h-3 w-3" />
                </button>
              </div>
            </div>{" "}
          </>
        )}
      </section>

      <section
        className="rounded-2xl border border-gray-100 bg-white p-3"
        aria-labelledby="home-routine"
      >
        <div className="flex items-center justify-between gap-2">
          <h2 id="home-routine" className="text-sm font-semibold text-gray-500">
            내 루틴 점검
          </h2>
          {productsState === "ready" && (
            <span className="text-[11px] text-gray-400">
              등록한 제품 {products?.length ?? 0}개
            </span>
          )}
        </div>
        {routine?.checked ? (
          <RoutineSummary routine={routine} />
        ) : (
        <p
          className="mt-2 text-xs leading-relaxed text-gray-400"
          role={productsState === "loading" ? "status" : undefined}
        >
          {productsState === "loading"
            ? "등록한 제품을 불러오고 있어요"
            : productsState === "error"
              ? "등록한 제품을 불러오지 못했어요."
              : products?.length
                ? "쓰고 있는 제품과 개봉일을 확인해 보세요."
                : "쓰고 있는 제품을 등록해 루틴을 모아보세요."}
        </p>
        )}
        <button
          type="button"
          onClick={() => navigate("/my/products")}
          className="mt-3 flex w-full items-center justify-between rounded-xl bg-primary-50 p-3 text-xs font-medium text-primary-600"
        >
          내 제품 관리 <ChevronRight className="h-4 w-4" />
        </button>
      </section>

      <RecentlyViewed />
      <section className="pt-2" aria-labelledby="home-trending">
        <h2 id="home-trending" className="text-sm font-semibold text-gray-500">
          요즘 뜨는 제품
        </h2>
        {trends === null ? (
          <p role="status" className="mt-2 rounded-2xl bg-gray-50 px-4 py-5 text-center text-[11px] text-gray-300">
            인기 제품을 불러오고 있어요
          </p>
        ) : trends === "error" ? (
          <div className="mt-2 rounded-2xl bg-gray-50 px-4 py-4 text-center text-[11px] text-gray-300">
            <p>인기 제품을 불러오지 못했어요.</p>
            <button
              type="button"
              className="mt-1 p-2 text-primary-600"
              onClick={() => {
                setTrends(null);
                setTrendAttempt((value) => value + 1);
              }}
            >
              다시 불러오기
            </button>
          </div>
        ) : trends.items.length ? (
          <ul className="-mx-5 mt-2 flex gap-3 overflow-x-auto px-5 pb-1 scrollbar-none">
            {trends.items.map((item) => (
              <li key={item.productId} className="w-[112px] shrink-0">
                <button
                  type="button"
                  onClick={() => navigate(`/product/${item.productId}`)}
                  className="block w-full text-left"
                >
                  <div className="relative grid aspect-square place-items-center overflow-hidden rounded-xl bg-surface-tint">
                    <span className="absolute left-2 top-1.5 text-[11px] font-semibold text-slate-500">{item.rank}</span>
                    {item.imageUrl ? (
                      <img src={item.imageUrl} alt="" loading="lazy" className="h-full w-full object-contain p-2" />
                    ) : (
                      <ProductThumbnail className="h-full w-full bg-surface-tint" />
                    )}
                  </div>
                  <p className="mt-1.5 truncate text-[11px] text-gray-400">{item.brand}</p>
                  <p className="line-clamp-2 text-[11px] font-medium leading-4 text-gray-500">{item.name}</p>
                  {item.interestChangePct != null && item.interestChangePct > 0 && (
                    <p className="mt-0.5 text-[11px] text-primary-600">관심 {item.interestChangePct}% ↑</p>
                  )}
                </button>
              </li>
            ))}
          </ul>
        ) : (
          <div className="mt-2 rounded-2xl border border-gray-100 bg-gray-50 px-4 py-5 text-center">
            <p className="text-[11px] text-gray-300">
              아직 집계된 인기 제품 정보가 없어요.
            </p>
          </div>
        )}
      </section>
    </div>
  );
}

/** 환경이 요구하는데 지금 루틴에 빠진 조건과, 그걸 채울 추천 제품 몇 개. */
function EnvRecoSummary({
  value,
  onSetRegion,
}: {
  value: EnvironmentRecommendation | "no-region" | null;
  onSetRegion: () => void;
}) {
  if (value === null) return null;
  if (value === "no-region")
    return (
      <button type="button" onClick={onSetRegion} className="mt-1.5 flex items-center gap-0.5 text-[11px] text-primary-600">
        지역을 설정하면 필요한 제품을 골라드려요 <ChevronRight aria-hidden="true" className="h-3 w-3" />
      </button>
    );
  if (value.state === "NOT_READY") return null;
  if (value.state === "FULLY_COVERED")
    return <p className="mt-1.5 text-[11px] text-ok-700">지금 쓰는 제품으로 충분해요</p>;
  const items = value.result?.items.slice(0, 3) ?? [];
  return (
    <div className="mt-1.5">
      {value.missingConditions.length > 0 && (
        <div className="flex flex-wrap gap-1">
          {value.missingConditions.map((condition) => (
            <span key={condition.key} className="rounded-md bg-warn-50 px-1.5 py-0.5 text-[11px] text-warn-600">
              {condition.label} 필요
            </span>
          ))}
        </div>
      )}
      {items.length > 0 && (
        <p className="mt-1 truncate text-[11px] text-gray-400">
          추천: {items.map((item) => item.name).join(", ")}
        </p>
      )}
    </div>
  );
}

/** 쓰는 제품끼리의 궁합 점검 결과. 같이 쓰면 안 되는 쌍을 먼저 보여준다. */
function RoutineSummary({ routine }: { routine: RoutineCheck }) {
  const worst =
    routine.pairs.find((pair) => pair.level === "AVOID") ??
    routine.pairs.find((pair) => pair.level === "SEPARATE");
  return (
    <div className="mt-2">
      <div className="grid grid-cols-3 divide-x divide-gray-100 text-center">
        {[
          { label: "괜찮아요", value: routine.counts.ok, tone: "text-ok-700" },
          { label: "시간 나눠요", value: routine.counts.separate, tone: "text-warn-600" },
          { label: "같이 쓰지 마요", value: routine.counts.avoid, tone: "text-red-700" },
        ].map((item) => (
          <div key={item.label} className="py-1.5">
            <p className={`text-sm font-bold ${item.tone}`}>{item.value}</p>
            <p className="text-[11px] text-gray-400">{item.label}</p>
          </div>
        ))}
      </div>
      {worst && (
        <p className="mt-2 text-[11px] leading-5 text-gray-500">
          <span className="block font-semibold">
            {worst.a.name} + {worst.b.name}
          </span>
          {worst.title && <span className="block">{worst.title}</span>}
        </p>
      )}
      {routine.uncomparedCount > 0 && (
        <p className="mt-1 text-[11px] text-gray-300">
          성분 정보가 없어 {routine.uncomparedCount}개는 비교하지 못했어요
        </p>
      )}
    </div>
  );
}
