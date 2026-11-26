import { useState } from "react";
import { REGION_CODES, updateRegion } from "../../api/homeApi";
import { BottomSheet } from "../common/BottomSheet";
import { PrimaryButton } from "../common/PrimaryButton";

/**
 * 생활 환경을 계산할 지역 고르기.
 *
 * 환경 데이터가 시·도 단위라 시·도를 고르고, 화면에 보여 줄 이름(예: 고양시 덕양구)은
 * 원하면 따로 적는다. 비워 두면 시·도 이름을 그대로 쓴다.
 */
export function RegionSheet({
  initialCode,
  onClose,
  onSaved,
}: {
  initialCode?: string;
  onClose: () => void;
  onSaved: (regionName: string) => void;
}) {
  const [code, setCode] = useState(initialCode ?? "");
  const [name, setName] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  async function save() {
    if (!code) return;
    setSaving(true);
    setError("");
    try {
      const display = name.trim().slice(0, 50) || code;
      const { data } = await updateRegion(code, display);
      onSaved(data?.regionName ?? display);
    } catch {
      setError("지역을 저장하지 못했어요. 다시 시도해주세요.");
    } finally {
      setSaving(false);
    }
  }

  // 저장하는 동안에는 닫지 않는다. 닫히면 저장 결과를 받을 곳이 없어진다.
  const close = () => {
    if (!saving) onClose();
  };

  return (
    <BottomSheet label="지역 설정" onClose={close}>
      <div className="px-5 pb-6 pt-3">
        <div className="flex items-center justify-between">
          <h2 className="text-body1 font-semibold text-slate-800">어디에서 지내세요?</h2>
          <button type="button" aria-label="닫기" onClick={close} disabled={saving} className="h-10 w-10 text-slate-400 disabled:opacity-40">
            ×
          </button>
        </div>
        <p className="mt-1 text-caption text-slate-500">
          지역의 자외선, 미세먼지, 습도로 요즘 필요한 제품을 알려드려요
        </p>
        <fieldset className="mt-4">
          <legend className="mb-2 text-caption font-semibold text-slate-700">시·도</legend>
          <div className="grid grid-cols-4 gap-1.5">
            {REGION_CODES.map((region) => (
              <button
                key={region}
                type="button"
                aria-pressed={code === region}
                onClick={() => setCode(region)}
                className={`min-h-10 rounded-lg text-caption ${code === region ? "bg-primary-200 font-semibold text-primary-900" : "bg-slate-100 text-slate-600"}`}
              >
                {region === "전남광주" ? "광주·전남" : region}
              </button>
            ))}
          </div>
        </fieldset>
        <label htmlFor="region-name" className="mt-4 block text-caption font-semibold text-slate-700">
          보여줄 이름 <span className="font-normal text-slate-400">(선택)</span>
        </label>
        <input
          id="region-name"
          value={name}
          maxLength={50}
          onChange={(event) => setName(event.target.value)}
          placeholder={code ? `예) ${code === "경기" ? "고양시 덕양구" : `${code} 집`}` : "먼저 시·도를 골라주세요"}
          className="mt-2 w-full rounded-xl border border-slate-200 px-3 py-3 text-caption outline-primary-500"
        />
        {error && (
          <p role="alert" className="mt-3 text-[11px] text-red-700">
            {error}
          </p>
        )}
        <PrimaryButton className="mt-4 disabled:opacity-40" disabled={!code || saving} onClick={() => void save()}>
          {saving ? "저장하는 중" : "이 지역으로 설정"}
        </PrimaryButton>
      </div>
    </BottomSheet>
  );
}
