import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Check, ChevronLeft, MapPin } from "lucide-react";
import { getMyProfile } from "../../api/userApi";
import {
  getEnvironmentDaily,
  getEnvironmentSummary,
  type EnvMetric,
  type EnvironmentDaily,
  type EnvironmentSummary,
} from "../../api/homeApi";
import { apiErrorCode } from "../../api/recommendationQueryApi";
import { care } from "../../lib/careBase";
import type { EnvironmentResponse } from "../../kiosk/lib/types";
import AppLayout from "../../layouts/AppLayout";
import { BottomNav } from "../../components/common/BottomNav";
import { RegionSheet } from "../../components/home/RegionSheet";

type SummaryState = "loading" | "ready" | "no-region" | "error";

export function EnvironmentPage() {
  const navigate = useNavigate();
  const [data, setData] = useState<EnvironmentResponse | null>(null);
  const [failed, setFailed] = useState(false);
  const [attempt, setAttempt] = useState(0);
  const [tab, setTab] = useState(0);

  // 최근 4주 (BE). 지역이 없으면 지역부터 고르게 한다.
  const [summary, setSummary] = useState<EnvironmentSummary | null>(null);
  const [summaryState, setSummaryState] = useState<SummaryState>("loading");
  const [daily, setDaily] = useState<Partial<Record<EnvMetric, EnvironmentDaily>>>({});
  const [dailyFailed, setDailyFailed] = useState<Partial<Record<EnvMetric, true>>>({});
  const [regionOpen, setRegionOpen] = useState(false);
  const [regionVersion, setRegionVersion] = useState(0);

  useEffect(() => {
    let active = true;
    getMyProfile().then(({ data: profile }) => care.get<EnvironmentResponse>(`/api/care/environment?user_id=${encodeURIComponent(profile.id)}`))
      .then(value => { if (active) setData(value); })
      .catch(() => { if (active) setFailed(true); });
    return () => { active = false; };
  }, [attempt]);

  useEffect(() => {
    let active = true;
    getEnvironmentSummary()
      .then(({ data: value }) => {
        if (!active) return;
        setSummary(value);
        setSummaryState("ready");
      })
      .catch(error => {
        if (!active) return;
        setSummaryState(apiErrorCode(error) === "REGION_NOT_SET" ? "no-region" : "error");
      });
    return () => { active = false; };
  }, [regionVersion]);

  const weather = data?.outdoor;
  const metrics: { label: string; title: string; value: number | null | undefined; unit: string; key: EnvMetric }[] = [
    { label: "자외선", title: "자외선 지수", value: weather?.uv_index, unit: "", key: "UV" },
    { label: "미세먼지", title: "초미세먼지 농도", value: weather?.pm25, unit: "㎍/㎥", key: "PM" },
    { label: "습도", title: "실외 습도", value: weather?.humidity, unit: "%", key: "HUMIDITY" },
    { label: "기온", title: "실외 기온", value: weather?.temperature, unit: "℃", key: "TEMP" },
  ];
  const metric = metrics[tab];
  const trend = daily[metric.key];

  // 고른 지표의 4주 추이를 처음 볼 때 한 번 받아 둔다.
  useEffect(() => {
    if (summaryState !== "ready" || daily[metric.key] || dailyFailed[metric.key]) return;
    let active = true;
    getEnvironmentDaily(metric.key)
      .then(({ data: value }) => { if (active) setDaily(previous => ({ ...previous, [metric.key]: value })); })
      .catch(() => { if (active) setDailyFailed(previous => ({ ...previous, [metric.key]: true })); });
    return () => { active = false; };
  }, [summaryState, metric.key, daily, dailyFailed]);

  const observed = weather?.observed_at ? new Date(weather.observed_at) : null;
  const regionName = summary?.regionName || weather?.region || "생활 환경";

  return <AppLayout>
    <div className="min-h-screen bg-white px-5 pb-44">
      <header className="relative flex h-16 items-center justify-center">
        <button type="button" onClick={() => navigate(-1)} aria-label="뒤로가기" className="absolute left-0 grid h-10 w-10 place-items-center"><ChevronLeft className="h-5 w-5" /></button>
        <h1 className="text-sm font-semibold">요즘 지내는 환경</h1>
      </header>
      <div className="mt-2 flex items-start justify-between gap-3">
        <div>
          <h2 className="text-lg font-bold text-gray-500">{regionName}</h2>
          <p className="mt-1 text-[11px] text-gray-300">{observed && Number.isFinite(observed.getTime()) ? `${observed.toLocaleString("ko-KR")} 관측` : "최근 측정 환경"}</p>
        </div>
        {summaryState !== "loading" && <button type="button" onClick={() => setRegionOpen(true)} className="flex min-h-9 shrink-0 items-center gap-1 rounded-lg bg-primary-50 px-2.5 text-[11px] text-primary-600">
          <MapPin aria-hidden="true" className="h-3.5 w-3.5" /> {summaryState === "no-region" ? "지역 설정" : "지역 변경"}
        </button>}
      </div>

      {summaryState === "no-region" && <section className="mt-4 rounded-2xl border border-[#9DBDE9] bg-[#F2F6FC] p-4">
        <p className="text-sm font-semibold text-[#203D66]">지역을 설정해 주세요</p>
        <p className="mt-1 text-xs leading-5 text-slate-600">지역을 알려주시면 최근 4주 자외선·미세먼지·습도와, 그 환경에 필요한 제품을 정리해 드려요.</p>
        <button type="button" onClick={() => setRegionOpen(true)} className="mt-3 min-h-10 rounded-lg bg-[#9DBDE9] px-4 text-xs font-semibold text-[#203D66]">지역 고르기</button>
      </section>}

      <div className="mt-4 grid grid-cols-4 gap-1" role="tablist" aria-label="환경 항목">
        {metrics.map((item, index) => <button key={item.label} id={`environment-tab-${index}`} aria-controls="environment-metric" role="tab" aria-selected={tab === index} tabIndex={tab === index ? 0 : -1}
          onKeyDown={event => { const next = event.key === "ArrowRight" ? (index + 1) % 4 : event.key === "ArrowLeft" ? (index + 3) % 4 : event.key === "Home" ? 0 : event.key === "End" ? 3 : null; if (next != null) { event.preventDefault(); setTab(next); document.getElementById(`environment-tab-${next}`)?.focus(); } }}
          onClick={() => setTab(index)} className={`rounded-lg py-2.5 text-xs ${tab === index ? "bg-[#9DBDE9] font-semibold text-[#203D66]" : "bg-gray-100 text-gray-400"}`}>{item.label}</button>)}
      </div>
      <section id="environment-metric" role="tabpanel" aria-labelledby={`environment-tab-${tab}`} className="mt-3 rounded-2xl border border-[#E5EDF8] p-4">
        {/* 지금 값은 AI CARE 관측 지역 기준이라, 위의 설정 지역과 다를 수 있어 따로 밝힌다. */}
        <p className="text-xs text-gray-300">지금 {metric.title}{weather?.region ? ` · ${weather.region} 관측` : ""}</p>
        <p className="mt-2 text-2xl font-bold text-gray-500">{failed ? "확인 불가" : !data ? "불러오는 중" : metric.value == null ? "미측정" : `${metric.value}${metric.unit}`}</p>
        {summaryState === "ready" ? (
          trend ? <TrendChart trend={trend} />
            : dailyFailed[metric.key] ? <p className="mt-4 rounded-xl bg-[#F0F5FD] px-3 py-6 text-center text-xs text-gray-300">최근 4주 추이를 불러오지 못했어요.</p>
              : <p role="status" className="mt-4 rounded-xl bg-[#F0F5FD] px-3 py-6 text-center text-xs text-gray-300">최근 4주 추이를 불러오고 있어요</p>
        ) : summaryState === "no-region" ? (
          <p className="mt-4 rounded-xl bg-[#F0F5FD] px-3 py-6 text-center text-xs leading-5 text-gray-300">지역을 설정하면 최근 4주 추이를 볼 수 있어요.</p>
        ) : summaryState === "error" ? (
          <p className="mt-4 rounded-xl bg-[#F0F5FD] px-3 py-6 text-center text-xs text-gray-300">최근 4주 추이를 불러오지 못했어요.</p>
        ) : null}
        {weather?.source && <p className="mt-2 text-[10px] text-gray-300">현재 값 출처: {weather.source}</p>}
        {failed && <button type="button" onClick={() => { setFailed(false); setAttempt(value => value + 1); }} className="mt-2 py-2 text-xs text-primary-600">다시 불러오기</button>}
      </section>

      {summaryState === "ready" && summary && <SummarySection summary={summary} />}

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
    {regionOpen && <RegionSheet
      onClose={() => setRegionOpen(false)}
      onSaved={() => {
        setRegionOpen(false);
        setSummaryState("loading");
        setDaily({});
        setDailyFailed({});
        setRegionVersion(value => value + 1);
      }}
    />}
  </AppLayout>;
}

/** 날짜별 막대 그래프. 기준을 넘은 날은 진하게, 기록이 없는 날은 빈 칸으로 둔다. */
function TrendChart({ trend }: { trend: EnvironmentDaily }) {
  const values = trend.days.map(day => day.value).filter((value): value is number => value != null);
  const max = Math.max(...values, trend.threshold ?? 0, 1);
  const min = Math.min(0, ...values);
  const span = max - min || 1;
  const thresholdPct = trend.threshold != null ? ((trend.threshold - min) / span) * 100 : null;
  const first = trend.days[0]?.date;
  const last = trend.days[trend.days.length - 1]?.date;
  return <div className="mt-4">
    {trend.headline && <p className="text-sm font-semibold text-slate-800">{trend.headline}</p>}
    {trend.subText && <p className="mt-0.5 text-[11px] text-slate-500">{trend.subText}</p>}
    <div className="relative mt-3 flex h-28 items-end gap-[2px]" role="img" aria-label={`최근 ${trend.days.length}일 ${trend.label} 추이`}>
      {thresholdPct != null && <div className="pointer-events-none absolute inset-x-0 border-t border-dashed border-[#E08A3C]" style={{ bottom: `${thresholdPct}%` }} />}
      {trend.days.map(day => <div key={day.date} className="flex h-full flex-1 items-end" title={`${day.date} ${day.value ?? "기록 없음"}`}>
        {day.value == null
          ? <div className="h-1 w-full rounded-sm bg-slate-100" />
          : <div className={`w-full rounded-sm ${day.exceeded ? "bg-[#5B8FD9]" : "bg-[#C5D8F0]"}`} style={{ height: `${Math.max(3, ((day.value - min) / span) * 100)}%` }} />}
      </div>)}
    </div>
    <div className="mt-1 flex justify-between text-[10px] text-slate-400">
      <span>{first?.slice(5).replace("-", ".")}</span>
      {trend.threshold != null && <span className="text-[#C06F2A]">점선: 기준 {trend.threshold}</span>}
      <span>{last?.slice(5).replace("-", ".")}</span>
    </div>
  </div>;
}

/** 4주 누적 요약과, 그 환경이 요구하는 제품 조건을 지금 루틴이 채우는지. */
function SummarySection({ summary }: { summary: EnvironmentSummary }) {
  const stats = [
    { label: "자외선 높은 날", value: summary.stats ? `${summary.stats.uvHighDays}일` : "—" },
    { label: "미세먼지 나쁜 날", value: summary.stats ? `${summary.stats.dustBadDays}일` : "—" },
    { label: "평균 습도", value: summary.stats?.avgHumidity != null ? `${summary.stats.avgHumidity}%` : "—" },
  ];
  return <section className="mt-5" aria-labelledby="environment-summary-title">
    <h2 id="environment-summary-title" className="text-sm font-semibold text-gray-500">최근 4주 정리</h2>
    <p className="mt-0.5 text-[11px] text-gray-300">{summary.periodStart.slice(5).replace("-", ".")} ~ {summary.periodEnd.slice(5).replace("-", ".")} · 기록 {summary.dayCount}일</p>
    <div className="mt-2 grid grid-cols-3 gap-2">
      {stats.map(item => <div key={item.label} className="rounded-xl bg-primary-50 px-1 py-2.5 text-center">
        <p className="text-[10px] text-gray-400">{item.label}</p>
        <p className="mt-0.5 text-base font-bold text-gray-500">{item.value}</p>
      </div>)}
    </div>
    {summary.seasonChange && <div className="mt-3 rounded-xl bg-[#FFF4E6] p-3">
      <p className="text-xs font-semibold text-[#956022]">{summary.seasonChange.title}</p>
      <p className="mt-1 text-[11px] leading-5 text-[#956022]">{summary.seasonChange.message}</p>
    </div>}
    <div className="mt-3 rounded-xl border border-gray-100 p-3">
      <p className="text-xs font-semibold text-gray-500">이 환경에 필요한 것</p>
      {!summary.recommendationAvailable || !summary.conditions.length
        ? <p className="mt-2 text-[11px] leading-5 text-gray-300">아직 분석 전이에요. 하루 한 번 정리돼요.</p>
        : <ul className="mt-2 grid gap-2">
          {summary.conditions.map(condition => <li key={condition.key} className="flex items-start gap-2">
            <span className={`mt-0.5 grid h-4 w-4 shrink-0 place-items-center rounded-full ${condition.covered ? "bg-[#E6F4ED] text-[#318457]" : "bg-[#FFF4E6] text-[#C06F2A]"}`}>
              {condition.covered ? <Check aria-hidden="true" className="h-3 w-3" /> : <span className="text-[10px] font-bold">!</span>}
            </span>
            <span className="min-w-0 text-[11px] leading-5 text-gray-500">
              <span className="font-semibold">{condition.label}</span>
              {condition.basis && <span className="text-gray-400"> · {condition.basis}</span>}
              <span className="block text-gray-400">{condition.covered ? `${condition.coveredBy ?? "보유 제품"}로 채우고 있어요` : "지금 쓰는 제품에는 없어요"}</span>
            </span>
          </li>)}
        </ul>}
    </div>
  </section>;
}
