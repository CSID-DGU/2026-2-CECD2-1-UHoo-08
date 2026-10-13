import { useState } from "react";
import { BottomSheet } from "../common/BottomSheet";
import { PrimaryButton } from "../common/PrimaryButton";

const OPTIONS = ["더 저렴하게", "향 없는 걸로", "커버력 높게", "지속력 좋은", "자외선 차단", "민감성도 괜찮은"];

export function RecommendationRefinementSheet({ conditions, baseQuery, mode = "add", onClose, onApply }: {
  conditions: string[];
  baseQuery: string;
  mode?: "add" | "edit";
  onClose: () => void;
  onApply: (conditions: string[], baseQuery?: string) => void;
}) {
  const editing = mode === "edit";
  const [selected, setSelected] = useState<string[]>(editing ? conditions : []);
  const [custom, setCustom] = useState("");
  const [editedBase, setEditedBase] = useState(baseQuery);
  const additions = [...new Set([...selected, ...(custom.trim() ? [custom.trim()] : [])].map(item => item.trim()).filter(Boolean))];
  const unchanged = editing && editedBase.trim() === baseQuery && JSON.stringify(additions) === JSON.stringify(conditions);
  return <BottomSheet label={editing ? "검색 조건 수정" : "검색 조건 추가"} onClose={onClose}>
    <div className="px-5 pb-7 pt-3">
      <div className="flex items-center justify-between gap-3"><h2 className="text-body1 font-semibold">{editing ? "검색 조건을 바꿔볼까요?" : "어떤 조건을 더할까요?"}</h2><button type="button" className="h-10 w-10" aria-label="조건 창 닫기" onClick={onClose}>×</button></div>
      <p className="mt-1 text-caption text-gray-300">{editing ? "바꾼 조건으로 후보를 다시 찾아요" : "고르거나 직접 쓰거나, 둘 다 하셔도 돼요"}</p>
      {editing ? <>
        <label htmlFor="base-search-query" className="mt-4 block text-caption font-semibold">처음 입력한 요청</label>
        <textarea id="base-search-query" value={editedBase} onChange={event => setEditedBase(event.target.value)} rows={2} className="mt-2 w-full rounded-xl border border-gray-200 p-3 text-caption outline-primary-500" />
        <p className="mt-4 text-caption font-semibold">추가한 조건 수정·삭제</p>
        {!selected.length && <p className="mt-2 text-[11px] text-gray-300">아직 추가한 조건이 없어요. 아래에서 더할 수 있어요.</p>}
        <div className="mt-2 grid gap-2">{selected.map((condition, index) => <div key={index} className="flex gap-2">
          <input aria-label={`추가 조건 ${index + 1}`} value={condition} onChange={event => setSelected(previous => previous.map((item, position) => position === index ? event.target.value : item))} className="min-w-0 flex-1 rounded-lg border border-gray-200 p-2 text-caption outline-primary-500" />
          <button type="button" aria-label={`추가 조건 ${index + 1} 삭제`} onClick={() => setSelected(previous => previous.filter((_, position) => position !== index))} className="min-h-10 px-2 text-[11px] text-gray-400">삭제</button>
        </div>)}</div>
      </> : <>
        <p className="mt-4 text-[11px] text-gray-300">지금 조건</p>
        <div className="mt-2 flex flex-wrap gap-1.5">{[baseQuery, ...conditions].map(condition => <span key={condition} className="max-w-full break-words rounded-md bg-gray-100 px-2 py-1 text-[11px] text-gray-400">{condition}</span>)}</div>
      </>}
      <fieldset className="mt-5"><legend className="mb-2 w-full text-caption font-semibold">골라서 더하기 <span className="float-right text-[11px] font-normal text-gray-300">복수 선택돼요</span></legend>
        <div className="grid grid-cols-2 gap-2">{OPTIONS.map(option => <button type="button" key={option} disabled={!editing && conditions.includes(option)} aria-pressed={selected.includes(option)} onClick={() => setSelected(previous => previous.includes(option) ? previous.filter(item => item !== option) : [...previous, option])} className={`min-h-11 rounded-xl px-2 py-3 text-caption disabled:opacity-40 ${selected.includes(option) ? "bg-primary-300 text-white" : "bg-gray-100 text-gray-500"}`}>{option}</button>)}</div>
      </fieldset>
      <label className="mt-5 block text-caption font-semibold" htmlFor="custom-refinement">직접 쓰기</label>
      <input id="custom-refinement" value={custom} maxLength={100} onChange={event => setCustom(event.target.value)} placeholder="예) 팩트 말고 쿠션만 보여줘" className="mt-2 w-full rounded-xl border border-gray-200 px-3 py-3 text-caption outline-primary-500" />
      {!editing && <p role="status" className="mt-3 rounded-xl bg-primary-50 px-4 py-3 text-[11px] font-semibold text-primary-600">고른 조건 {selected.length}개 · 직접 쓴 조건 {custom.trim() ? 1 : 0}개</p>}
      <PrimaryButton disabled={editing ? !editedBase.trim() || unchanged : !additions.length} className="mt-4 disabled:opacity-40" onClick={() => onApply(additions, editing ? editedBase.trim() : undefined)}>{editing ? "수정한 조건으로 다시 검색" : `조건 ${additions.length}개 추가하기`}</PrimaryButton>
    </div>
  </BottomSheet>;
}
