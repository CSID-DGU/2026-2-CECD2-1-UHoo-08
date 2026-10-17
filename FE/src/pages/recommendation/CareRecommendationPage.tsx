import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { ChevronLeft, Package, Thermometer } from "lucide-react";
import { type CareRecoFull, getCareRecommendations } from "../../api/careRecoApi";
import { getMyProfile } from "../../api/userApi";
import { BottomNav } from "../../components/common/BottomNav";
import AppLayout from "../../layouts/AppLayout";

export function CareRecommendationPage() {
  const navigate = useNavigate();
  const [data, setData] = useState<CareRecoFull | null>(null);
  const [failed, setFailed] = useState(false);
  const [attempt, setAttempt] = useState(0);
  const [selected, setSelected] = useState<string | null>(null);
  useEffect(() => {
    let active = true;
    setFailed(false);
    getMyProfile().then(res => getCareRecommendations(res.data.id))
      .then(value => { if (active) setData(value); })
      .catch(() => { if (active) setFailed(true); });
    return () => { active = false; };
  }, [attempt]);
  const groups = data?.groups.filter(group => selected == null || selected === group.key) ?? [];
  const count = new Set(groups.flatMap(group => group.items.map(item => item.product_id))).size;
  return <AppLayout>
    <div className="min-h-screen bg-white px-5 pb-28">
      <header className="relative flex h-16 items-center justify-center">
        <button onClick={() => navigate(-1)} type="button" aria-label="뒤로가기" className="absolute left-0 grid h-10 w-10 place-items-center"><ChevronLeft className="h-5 w-5" /></button>
        <h1 className="text-sm font-semibold text-gray-500">환경 기반 추천</h1>
      </header>
      <section className="mt-2 rounded-xl border border-[#9DBDE9] bg-[#F0F5FD] p-3">
        <p className="text-xs font-semibold text-primary-600">측정 환경을 참고해 골랐어요</p>
        <p className="mt-2 text-xs leading-5 text-gray-400">{data?.context || "환경 정보가 있는 제품부터 안내해 드려요."}</p>
      </section>
      {failed ? <div className="mt-5 rounded-xl bg-[#F0F5FD] p-5 text-center">
        <p className="text-xs text-gray-300">추천을 불러오지 못했어요.</p>
        <button type="button" onClick={() => setAttempt(value => value + 1)} className="mt-3 rounded-lg bg-[#9DBDE9] px-4 py-2 text-xs text-[#203D66]">다시 불러오기</button>
      </div> : !data ? <p role="status" className="py-10 text-center text-xs text-gray-300">환경을 확인하는 중이에요</p> : data.groups.length === 0 ? <div className="mt-5 rounded-xl bg-[#F0F5FD] p-5 text-center">
        <Thermometer className="mx-auto h-6 w-6 text-[#9DBDE9]" /><p className="mt-2 text-xs text-gray-300">아직 추천할 제품이 없어요.</p>
      </div> : <>
        <p className="mt-4 text-xs font-medium text-gray-400">관심 있는 환경 조건을 골라보세요</p>
        <div className="mt-2 flex flex-wrap gap-1.5">
          {[{ key: null, title: "전체" }, ...data.groups].map(group => <button type="button" key={group.key ?? "all"} aria-pressed={selected === group.key} onClick={() => setSelected(group.key)} className={`rounded-md px-2.5 py-1.5 text-[11px] ${selected === group.key ? "bg-[#9DBDE9] font-semibold text-[#203D66]" : "bg-[#F0F5FD] text-primary-600"}`}>{group.title}</button>)}
        </div>
        <div className="mt-5 flex items-center justify-between"><h2 className="text-xs font-medium text-gray-500">환경을 참고해 고른 제품이에요</h2><span className="text-[11px] text-gray-300">총 {count}개 제품</span></div>
        {groups.map(group => <section className="mt-3" key={group.key}>
          <h3 className="text-xs font-semibold text-primary-600">{group.title}</h3>
          {group.note && <p className="mt-1 text-[11px] leading-4 text-gray-300">{group.note}</p>}
          <div className="mt-2 grid grid-cols-2 items-start gap-3">
            {group.items.map(item => <button className="overflow-hidden rounded-2xl border border-[#E5EDF8] bg-white text-left" key={item.product_id} onClick={() => navigate(`/product/${item.product_id}`)} type="button">
              <div className="grid aspect-square place-items-center bg-[#F0F5FD] p-3">
                {item.image_url ? <img src={item.image_url} alt="" className="h-full w-full object-contain" /> : <Package className="h-14 w-14 text-[#9DBDE9]" strokeWidth={1.2} />}
              </div>
              <div className="p-3">
                <p className="line-clamp-2 text-xs font-semibold text-gray-500">{item.name}</p>
                <p className="mt-1 truncate text-[10px] text-gray-300">{item.brand}</p>
                {item.price != null && <p className="mt-1.5 text-sm font-semibold text-gray-500">{item.price.toLocaleString()}원</p>}
                <p className="mt-2 line-clamp-3 text-[10px] leading-4 text-primary-600">{item.reason}</p>
              </div>
            </button>)}
          </div>
        </section>)}
      </>}
    </div>
    <BottomNav />
  </AppLayout>;
}
export default CareRecommendationPage;
