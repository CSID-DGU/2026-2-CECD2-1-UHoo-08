import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { getUnreadCount } from "../../api/notificationApi";
import { getTrackings } from "../../api/priceTrackingApi";
import { getCareRecommendations, type CareRecoFull } from "../../api/careRecoApi";
import { getMyProfile } from "../../api/userApi";
import { Bell, Thermometer, TrendingUp } from "lucide-react";
import { BottomNav } from "../../components/common/BottomNav";
import { WishlistButton } from "../../components/common/WishlistButton";
import AppLayout from "../../layouts/AppLayout";
import { HomeHero } from "../../components/recommendation/HomeHero";
import { HomeSearchPrompt } from "../../components/recommendation/HomeSearchPrompt";

import { HomeOverview } from "../../components/home/HomeOverview";

export function HomePage() {
  const navigate = useNavigate();
  const [hasUnread, setHasUnread] = useState(false);
  const [trackingCount, setTrackingCount] = useState<number | null>(null);
  const [careReco, setCareReco] = useState<CareRecoFull | null>(null);

  useEffect(() => {
    let active = true;
    getMyProfile()
      .then(({ data }) => getCareRecommendations(data.id))
      .then((value) => {
        if (active) setCareReco(value);
      })
      .catch(() => {
        if (active) setCareReco(null);
      });
    return () => { active = false; };
  }, []);

  useEffect(() => {
    getUnreadCount()
      .then((count) => setHasUnread(count > 0))
      .catch(() => setHasUnread(false));

    getTrackings()
      .then((res) => setTrackingCount(res.data?.summary?.totalTracking ?? 0))
      .catch(() => setTrackingCount(0));
  }, []);

  function handleSearch(query: string) {
    if (!query) return;
    navigate("/search", { state: { query } });
  }

  return (
    <AppLayout>
      {/* 전체 뷰포트 고정 레이아웃 */}
      <div className="flex h-screen flex-col overflow-hidden">
        {/* 스크롤 영역 */}
        <div className="flex-1 overflow-y-auto scrollbar-none">
          <div className="pb-44">
            <header className="flex items-center justify-between px-5 pb-5 pt-6">
              <p className="text-h2 text-black">화담</p>
              <div className="flex items-center gap-2">
                <WishlistButton />
                <button
                  className="relative grid h-10 w-10 place-items-center rounded-xl bg-primary-50"
                  onClick={() => navigate("/notifications")}
                  type="button"
                  aria-label="알림"
                >
                  <Bell
                    className="h-5 w-5 text-primary-600"
                    strokeWidth={1.8}
                  />
                  {hasUnread && (
                    <span className="absolute right-1 top-1 h-2 w-2 rounded-full bg-primary-500" />
                  )}
                </button>
              </div>
            </header>
            <div className="px-5">
              <div className="mb-4">
                <HomeSearchPrompt onSubmit={handleSearch} />
              </div>

              <HomeHero
                onSearch={handleSearch}
                onEvaluate={() => navigate("/recommendation/lookup")}
              />

              <HomeOverview />
              {/* 화담 CARE 추천.
                  키오스크 QR로 넘어온 사용자가 "전체 추천"을 기대하는 자리다.
                  다른 추천과 달리 근거가 센서 측정값이라, 제목 아래에 그
                  숫자를 그대로 둔다. 근거를 감추면 그냥 또 하나의 추천 목록이
                  되어 버린다. */}
              {careReco && careReco.groups.some((group) => group.items.length > 0) && (
                <section className="mt-4 rounded-2xl border border-[#9DBDE9] p-3" aria-labelledby="home-care-title">
                  <div className="mb-2 flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <span
                        className="grid h-7 w-7 place-items-center rounded-full"
                        style={{
                          background: "linear-gradient(135deg, #DBE6F8, #9DBFEE)",
                        }}
                      >
                        <Thermometer
                          className="h-4 w-4 text-primary-600"
                          strokeWidth={1.8}
                        />
                      </span>
                      <div>
                        <p className="text-[10px] font-semibold text-primary-600">화담 CARE · 키오스크 환경 기반</p>
                        <h2 id="home-care-title" className="text-body1 text-gray-500">
                          오늘의 환경 맞춤 추천
                        </h2>
                        {careReco?.context && (
                          <p className="text-caption text-gray-300">
                            {careReco.context}
                          </p>
                        )}
                      </div>
                    </div>
                    <button
                      className="shrink-0 text-body2 text-primary-500"
                      onClick={() => navigate("/recommendation/care")}
                      type="button"
                    >
                      더보기
                    </button>
                  </div>

                  <div className="flex gap-3 overflow-x-auto pb-1 scrollbar-none">
                    {careReco.groups
                      .flatMap((g) => g.items)
                      .slice(0, 6)
                      .map((item) => (
                        <button
                          className="min-w-[154px] rounded-2xl border border-gray-100 bg-white p-3 text-left"
                          key={item.product_id}
                          onClick={() => navigate(`/product/${item.product_id}`)}
                          type="button"
                        >
                          <div className="h-[94px] overflow-hidden rounded-xl bg-primary-50">
                            {item.image_url && (
                              <img
                                src={item.image_url}
                                alt={item.name}
                                className="h-full w-full object-cover"
                              />
                            )}
                          </div>
                          <p className="mt-3 truncate text-body2 text-gray-500">
                            {item.name}
                          </p>
                          {/* 왜 골랐는지. 가로 카드라 두 줄까지만 보인다. */}
                          <p className="mt-1 line-clamp-2 text-caption leading-[1.4] text-primary-600">
                            {item.reason}
                          </p>
                          {item.price != null && (
                            <p className="mt-2 text-caption text-gray-300">
                              {item.price.toLocaleString()}원
                            </p>
                          )}
                        </button>
                      ))}
                  </div>
                </section>
              )}
              {/* 가격 추적 플로팅 바 — 고정 */}
              {trackingCount !== null && (
                <div className="mt-5 w-full">
                  <button
                    className="relative flex w-full items-center gap-3 overflow-hidden rounded-2xl px-5 py-4"
                    style={{
                      background:
                        "linear-gradient(135deg, rgba(91,143,217,0.18) 0%, rgba(155,191,238,0.14) 100%)",
                      backdropFilter: "blur(20px)",
                      WebkitBackdropFilter: "blur(20px)",
                      border: "1px solid rgba(255,255,255,0.75)",
                    }}
                    onClick={() => navigate("/favorites")}
                    type="button"
                  >
                    <span
                      className="pointer-events-none absolute inset-x-0 top-0 h-px"
                      style={{
                        background:
                          "linear-gradient(90deg, transparent, rgba(255,255,255,0.9), transparent)",
                      }}
                    />
                    <span
                      className="grid h-10 w-10 shrink-0 place-items-center rounded-xl"
                      style={{
                        background:
                          "linear-gradient(135deg, rgba(91,143,217,0.35), rgba(53,101,181,0.25))",
                        border: "1px solid rgba(255,255,255,0.6)",
                      }}
                    >
                      <TrendingUp
                        className="h-5 w-5 text-primary-600"
                        strokeWidth={1.8}
                      />
                    </span>
                    <div className="flex-1 text-left">
                      <p className="text-caption font-semibold text-primary-600">
                        가격 추적
                      </p>
                      <p className="text-body2 text-gray-400">
                        {trackingCount > 0
                          ? `${trackingCount}개 제품 모니터링 중이에요`
                          : "지금 바로 가격 추적을 시작해보세요"}
                      </p>
                    </div>
                    <span
                      className="flex h-7 w-7 items-center justify-center rounded-full text-body2 text-primary-500"
                      style={{
                        background: "rgba(255,255,255,0.55)",
                        border: "1px solid rgba(91,143,217,0.2)",
                      }}
                    >
                      ›
                    </span>
                  </button>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* 하단 네비게이션 — 고정 */}
      <BottomNav />
    </AppLayout>
  );
}
