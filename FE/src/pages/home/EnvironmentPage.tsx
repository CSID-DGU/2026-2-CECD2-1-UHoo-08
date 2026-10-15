import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { ChevronLeft } from "lucide-react";
import { getMyProfile } from "../../api/userApi";
import { care } from "../../lib/careBase";
import type { EnvironmentResponse } from "../../kiosk/lib/types";
import AppLayout from "../../layouts/AppLayout";
import { BottomNav } from "../../components/common/BottomNav";

export function EnvironmentPage() {
  const navigate = useNavigate();
  const [data, setData] = useState<EnvironmentResponse | null>(null);
  const [failed, setFailed] = useState(false);
  const [attempt, setAttempt] = useState(0);
  const [tab, setTab] = useState(0);
  useEffect(() => {
    let active = true;
    setFailed(false);
    getMyProfile().then(({ data: profile }) => care.get<EnvironmentResponse>(`/api/care/environment?user_id=${encodeURIComponent(profile.id)}`))
      .then(value => { if (active) setData(value); })
      .catch(() => { if (active) setFailed(true); });
    return () => { active = false; };
  }, [attempt]);
  const weather = data?.outdoor;
  const metrics = [
    { label: "자외선", title: "자외선 지수", value: weather?.uv_index, unit: "" },
    { label: "미세먼지", title: "초미세먼지 농도", value: weather?.pm25, unit: "㎍/㎥" },
    { label: "습도", title: "실외 습도", value: weather?.humidity, unit: "%" },
    { label: "기온", title: "실외 기온", value: weather?.temperature, unit: "℃" },
  ];
  const metric = metrics[tab];
  const observed = weather?.observed_at ? new Date(weather.observed_at) : null;
  return <AppLayout>
    <div className="min-h-screen bg-white px-5 pb-44">
      <header className="relative flex h-16 items-center justify-center">
        <button type="button" onClick={() => navigate(-1)} aria-label="뒤로가기" className="absolute left-0 grid h-10 w-10 place-items-center"><ChevronLeft className="h-5 w-5" /></button>
        <h1 className="text-sm font-semibold">요즘 지내는 환경</h1>
      </header>
      <h2 className="mt-2 text-lg font-bold text-gray-500">{weather?.region || "생활 환경"}</h2>
      <p className="mt-1 text-[11px] text-gray-300">{observed && Number.isFinite(observed.getTime()) ? `${observed.toLocaleString("ko-KR")} 관측` : "최근 측정 환경"}</p>
      <div className="mt-4 grid grid-cols-4 gap-1" role="tablist" aria-label="환경 항목">
        {metrics.map((item, index) => <button key={item.label} id={`environment-tab-${index}`} aria-controls="environment-metric" role="tab" aria-selected={tab === index} tabIndex={tab === index ? 0 : -1}
          onKeyDown={event => { const next = event.key === "ArrowRight" ? (index + 1) % 4 : event.key === "ArrowLeft" ? (index + 3) % 4 : event.key === "Home" ? 0 : event.key === "End" ? 3 : null; if (next != null) { event.preventDefault(); setTab(next); document.getElementById(`environment-tab-${next}`)?.focus(); } }}
          onClick={() => setTab(index)} className={`rounded-lg py-2.5 text-xs ${tab === index ? "bg-[#9DBDE9] font-semibold text-[#203D66]" : "bg-gray-100 text-gray-400"}`}>{item.label}</button>)}
      </div>
      <section id="environment-metric" role="tabpanel" aria-labelledby={`environment-tab-${tab}`} className="mt-3 rounded-2xl border border-[#E5EDF8] p-4">
        <p className="text-xs text-gray-300">{metric.title}</p>
        <p className="mt-2 text-2xl font-bold text-gray-500">{failed ? "확인 불가" : !data ? "불러오는 중" : metric.value == null ? "미측정" : `${metric.value}${metric.unit}`}</p>
        <div className="mt-4 rounded-xl bg-[#F0F5FD] px-3 py-6 text-center text-xs leading-5 text-gray-300">최근 4주 추이는 아직 제공되지 않아요.<br />현재 관측값을 먼저 확인해 주세요.</div>
        {weather?.source && <p className="mt-2 text-[10px] text-gray-300">출처: {weather.source}</p>}
        {failed && <button type="button" onClick={() => setAttempt(value => value + 1)} className="mt-2 py-2 text-xs text-primary-600">다시 불러오기</button>}
      </section>
      {data?.brief.headline && <section className="mt-4 rounded-xl bg-[#FFF4E6] p-4">
        <h2 className="text-xs font-semibold text-[#956022]">{data.brief.headline}</h2>
        {data.brief.lines.map((line, index) => <p key={index} className="mt-1 text-xs leading-5 text-[#956022]">{line}</p>)}
      </section>}
      {Boolean(data?.indoor.length) && <section className="mt-5">
        <h2 className="text-sm font-semibold text-gray-500">내 생활 공간</h2>
        <div className="mt-2 divide-y divide-gray-100 rounded-xl border border-gray-100 px-3">
          {data?.indoor.map(node => <div key={node.node_id} className="flex items-center justify-between gap-3 py-3">
            <div><p className="text-xs font-medium">{node.label}</p><p className="mt-1 text-[11px] text-gray-300">{node.online ? `온도 ${node.temperature ?? "—"}℃ · 습도 ${node.humidity ?? "—"}%` : "센서 연결을 확인해 주세요"}</p></div>
            <span className={`rounded-md px-2 py-1 text-[10px] ${node.online ? "bg-[#E6F4ED] text-[#318457]" : "bg-gray-100 text-gray-300"}`}>{node.online ? "측정 중" : "연결 안 됨"}</span>
          </div>)}
        </div>
      </section>}
      <div className="fixed bottom-[88px] left-1/2 z-20 w-full max-w-[430px] -translate-x-1/2 px-5">
        <button type="button" onClick={() => navigate("/recommendation/care")} className="w-full rounded-xl bg-[#9DBDE9] px-4 py-3.5 text-sm font-semibold text-[#203D66] shadow-sm">환경에 맞는 제품 보기</button>
      </div>
    </div>
    <BottomNav />
  </AppLayout>;
}
