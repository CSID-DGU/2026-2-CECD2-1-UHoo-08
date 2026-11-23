import { useEffect, useState } from "react";
import { ChevronRight } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { getTrackings, updateAlertSettings } from "../../api/priceTrackingApi";
import { clearTokens } from "../../lib/auth";
import { PageHeader } from "../../components/common/PageHeader";
import AppLayout from "../../layouts/AppLayout";

function Toggle({ on, onToggle, disabled, label }: { on: boolean; onToggle: () => void; disabled?: boolean; label: string }) {
  return (
    <button
      className={`relative h-6 w-11 shrink-0 rounded-full transition-colors disabled:opacity-40 ${on ? "bg-primary-500" : "bg-gray-200"}`}
      onClick={onToggle}
      type="button"
      aria-pressed={on}
      aria-label={label}
      disabled={disabled}
    >
      <span
        className={`absolute left-0 top-0.5 h-5 w-5 rounded-full bg-white transition-transform motion-reduce:transition-none ${
          on ? "translate-x-5" : "translate-x-0.5"
        }`}
      />
    </button>
  );
}

function SettingRow({
  label,
  desc,
  on,
  onToggle,
  disabled,
  badge,
}: {
  label: string;
  desc?: string;
  on: boolean;
  onToggle: () => void;
  disabled?: boolean;
  badge?: string;
}) {
  return (
    <div className="flex items-center justify-between gap-3 py-4">
      <div>
        <p className="text-body2 text-gray-500">
          {label}
          {badge && <span className="ml-1.5 rounded bg-gray-100 px-1.5 py-0.5 text-[11px] text-gray-400">{badge}</span>}
        </p>
        {desc && <p className="mt-0.5 text-caption text-gray-300">{desc}</p>}
      </div>
      <Toggle on={on} onToggle={onToggle} disabled={disabled} label={label} />
    </div>
  );
}

type AlertSettings = { targetPriceAlert: boolean; weeklyReport: boolean };

export function SettingsPage() {
  const navigate = useNavigate();
  // 가격 알림과 주간 리포트는 가격 추적 설정(BE)에 저장한다. 불러오기 전에는 막아 둔다.
  const [alerts, setAlerts] = useState<AlertSettings | null>(null);
  const [alertError, setAlertError] = useState("");
  // 저장 중에는 토글을 막는다. 두 요청이 겹치면 실패 복원이 다른 요청의 결과를 덮는다.
  const [savingAlert, setSavingAlert] = useState(false);

  useEffect(() => {
    let active = true;
    getTrackings()
      .then(({ data }) => {
        if (!active) return;
        const settings = data?.alertSettings;
        if (
          typeof settings?.targetPriceAlert !== "boolean" ||
          typeof settings?.weeklyReport !== "boolean"
        ) {
          setAlertError("알림 설정을 불러오지 못했어요.");
          return;
        }
        setAlerts({ targetPriceAlert: settings.targetPriceAlert, weeklyReport: settings.weeklyReport });
      })
      .catch(() => {
        if (active) setAlertError("알림 설정을 불러오지 못했어요.");
      });
    return () => {
      active = false;
    };
  }, []);

  async function changeAlert(key: keyof AlertSettings) {
    if (!alerts || savingAlert) return;
    const previous = alerts;
    const next = { ...alerts, [key]: !alerts[key] };
    setAlerts(next); // 먼저 바꿔 보여주고, 실패하면 되돌린다.
    setAlertError("");
    setSavingAlert(true);
    try {
      await updateAlertSettings(next.targetPriceAlert, next.weeklyReport);
    } catch {
      setAlerts(previous);
      setAlertError("알림 설정을 저장하지 못했어요. 다시 시도해주세요.");
    } finally {
      setSavingAlert(false);
    }
  }

  function handleLogout() {
    clearTokens();
    navigate("/", { replace: true });
  }

  return (
    <AppLayout>
      <div className="flex h-screen flex-col overflow-hidden">
        <div className="flex-1 overflow-y-auto scrollbar-none">
        <section className="px-6 pb-8 pt-10">
        <PageHeader title="앱 설정 및 고객센터" onBack={() => navigate(-1)} />

        {/* 알림 설정 */}
        <div className="mt-6">
          <h2 className="text-body1 text-gray-500">알림 설정</h2>
          <div className="mt-3 divide-y divide-gray-100 rounded-xl border border-gray-200 bg-white px-4">
            <SettingRow
              label="가격 변동 알림"
              desc="추적 중인 상품이 목표가에 닿으면 알려드려요"
              on={alerts?.targetPriceAlert ?? false}
              disabled={!alerts || savingAlert}
              onToggle={() => void changeAlert("targetPriceAlert")}
            />
            <SettingRow
              label="주간 리포트"
              desc="추적 중인 상품 가격을 매주 정리해 드려요"
              on={alerts?.weeklyReport ?? false}
              disabled={!alerts || savingAlert}
              onToggle={() => void changeAlert("weeklyReport")}
            />
            <SettingRow
              label="AI 추천 알림"
              desc="맞춤 제품 추천 소식을 알려드려요"
              badge="준비 중"
              on={false}
              disabled
              onToggle={() => {}}
            />
            <SettingRow
              label="리뷰 요청"
              desc="사용한 제품에 대한 리뷰를 남겨주세요"
              badge="준비 중"
              on={false}
              disabled
              onToggle={() => {}}
            />
          </div>
          {alertError && (
            <p role="alert" className="mt-2 text-caption text-red-700">
              {alertError}
            </p>
          )}
        </div>

        {/* 고객센터 */}
        <div className="mt-6">
          <h2 className="text-body1 text-gray-500">고객센터</h2>
          <div className="mt-3 divide-y divide-gray-100 rounded-xl border border-gray-200 bg-white">
            {[
              { label: "자주 묻는 질문" },
              { label: "1:1 문의" },
              { label: "서비스 이용약관" },
              { label: "개인정보 처리방침" },
            ].map((item) => (
              <button
                className="flex w-full items-center justify-between px-4 py-4 text-left"
                key={item.label}
                type="button"
              >
                <span className="text-body2 text-gray-500">{item.label}</span>
                <ChevronRight aria-hidden="true" className="h-4 w-4 text-gray-300" />
              </button>
            ))}
          </div>
        </div>

        {/* 앱 정보 */}
        <div className="mt-6">
          <h2 className="text-body1 text-gray-500">앱 정보</h2>
          <div className="mt-3 divide-y divide-gray-100 rounded-xl border border-gray-200 bg-white">
            <div className="flex items-center justify-between px-4 py-4">
              <span className="text-body2 text-gray-500">버전</span>
              <span className="text-body2 text-gray-300">1.0.0</span>
            </div>
          </div>
        </div>

        <button
          className="mt-8 w-full rounded-xl border border-red-100 bg-red-50 py-4 text-body2 text-red-500"
          onClick={handleLogout}
          type="button"
        >
          로그아웃
        </button>
        </section>
        </div>
      </div>
    </AppLayout>
  );
}
