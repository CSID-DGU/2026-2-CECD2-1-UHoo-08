import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { ChevronRight, Droplets, Sun, Wind } from "lucide-react";
import { getMyProfile } from "../../api/userApi";
import { getMyProducts, type MyProduct } from "../../api/myProductApi";
import { RecentlyViewed } from "./RecentlyViewed";
import { care } from "../../lib/careBase";
import type { EnvironmentResponse } from "../../kiosk/lib/types";

export function HomeOverview() {
  const navigate = useNavigate();
  const [environment, setEnvironment] = useState<EnvironmentResponse | null>(
    null,
  );
  const [products, setProducts] = useState<MyProduct[] | null>(null);
  const [environmentState, setEnvironmentState] = useState("loading");
  const [productsState, setProductsState] = useState("loading");
  const [attempt, setAttempt] = useState(0);

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
        className="rounded-2xl border border-[#9DBDE9] bg-white p-3"
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
            <p className="mt-0.5 text-[11px] text-gray-300">
              {outdoor?.region || "생활 환경"}
              {timestamp ? ` · ${timestamp} 관측` : " · 최근 측정값"}
            </p>
          </div>
          <span className="rounded-md bg-primary-50 px-2 py-1 text-[10px] text-primary-600">
            현재 환경 ›
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
            <div className="mt-2 grid grid-cols-3 gap-2">
              {stats.map(({ label, value, unit, Icon }) => (
                <div
                  key={label}
                  className="rounded-xl bg-primary-50 px-1 py-2 text-center"
                >
                  <Icon
                    className="mx-auto mb-1 h-4 w-4 text-[#9DBDE9]"
                    aria-hidden="true"
                  />
                  <p className="text-[10px] text-gray-400">{label}</p>
                  <p className="mt-0.5 text-base font-bold text-gray-500">
                    {value == null ? (
                      "미측정"
                    ) : (
                      <>
                        {value}
                        <span className="ml-0.5 text-[10px] font-normal">
                          {unit}
                        </span>
                      </>
                    )}
                  </p>
                </div>
              ))}
            </div>
            <div className="mt-3 border-t border-dashed border-[#E5EDF8] pt-3">
              <p className="text-[11px] font-semibold text-gray-500">
                환경에 맞춰 루틴 살펴보기
              </p>
              <div className="mt-2 flex items-center justify-between gap-2">
                <span className="text-[10px] text-gray-300">
                  측정 환경을 참고해 제품을 확인해요
                </span>
                <button
                  type="button"
                  className="shrink-0 py-1 text-[11px] text-primary-600"
                  onClick={() => navigate("/recommendation/care")}
                >
                  제품 보기 ›
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
        <div className="mt-2 rounded-2xl border border-gray-100 bg-gray-50 px-4 py-5 text-center">
          <p className="text-[11px] text-gray-300">
            아직 집계된 인기 제품 정보가 없어요.
          </p>
        </div>
      </section>
    </div>
  );
}
