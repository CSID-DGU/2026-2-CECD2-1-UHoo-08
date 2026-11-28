import { useEffect, useState } from "react";
import type { ClarifyField, answerClarification } from "../../api/recommendationQueryApi";
import { CONCERN_LABEL, SKIN_TYPE_LABEL, getMyProfile } from "../../api/userApi";

type Answers = Parameters<typeof answerClarification>[1];

const DEFAULT_BUDGET_PRESETS = [30000, 50000, 100000];
const COUNT_WORD = ["", "한", "두", "세", "네", "다섯"];

/** 구성 예시. 누르면 알아듣는 단계를 그대로 채운다 */
const STEP_EXAMPLES = [
  { phrase: "아침에 쓸 기초 세트", steps: ["스킨", "로션", "선크림"] },
  { phrase: "여드름 관리용 3종", steps: ["클렌저", "토너", "진정 앰플"] },
];

/** "토너, 세럼\n크림" → ["토너", "세럼", "크림"]. 서버가 항목당 50자, 최대 10개까지 받는다 */
const splitSteps = (raw: string) =>
  raw
    .split(/[,\n]/)
    .map((item) => item.trim().slice(0, 50))
    .filter(Boolean)
    .slice(0, 10);

/**
 * 되묻기(NEEDS_CLARIFICATION) 답변 폼.
 *
 * 서버가 물어본 항목(fields)만 그린다. 항목이 없으면 자유 답변 하나만 받는다.
 * 되묻기는 한 번까지라, 답이 모자라도 서버가 그대로 진행한다.
 */
export function ClarifyForm({
  message,
  fields,
  submitting,
  error,
  onSubmit,
}: {
  message: string;
  fields: ClarifyField[];
  submitting: boolean;
  error?: string;
  onSubmit: (answers: Answers) => void;
}) {
  const [values, setValues] = useState<Record<string, string>>({});
  const [text, setText] = useState("");
  const set = (key: string, value: string) =>
    setValues((previous) => ({ ...previous, [key]: value }));

  function build(): Answers {
    const answers: Answers = {};
    for (const field of fields) {
      const raw = (values[field.key] ?? "").trim();
      if (!raw) continue;
      if (field.inputType === "AMOUNT") {
        const amount = Number(raw.replace(/[^\d]/g, ""));
        if (amount > 0) answers.budget = amount;
      } else if (field.inputType === "TEXT_LIST") {
        const items = splitSteps(raw);
        if (items.length) answers.bundleSteps = items;
      } else if (field.key === "category") {
        answers.category = raw.slice(0, 50);
      } else if (field.key === "baseProduct" || field.inputType === "PRODUCT") {
        answers.baseProduct = raw.slice(0, 200);
      }
    }
    if (text.trim()) answers.text = text.trim().slice(0, 500);
    return answers;
  }

  const answers = build();
  const empty = Object.keys(answers).length === 0;

  // 예산 세트에서 예산이나 구성을 물을 때는 세트 전용 화면으로 묻는다
  if (fields.some((field) => field.inputType === "AMOUNT" || field.inputType === "TEXT_LIST")) {
    return (
      <BundleClarify
        fields={fields}
        values={values}
        set={set}
        submitting={submitting}
        error={error}
        empty={empty}
        onSubmit={() => onSubmit(answers)}
      />
    );
  }

  return (
    <form
      className="mt-5 rounded-xl border border-primary-100 bg-primary-50 p-4"
      onSubmit={(event) => {
        event.preventDefault();
        if (!empty && !submitting) onSubmit(answers);
      }}
    >
      <h2 className="text-body2 font-semibold text-slate-800">조금만 더 알려주세요</h2>
      <p className="mt-1 text-caption leading-5 text-gray-500">{message}</p>
      {fields.map((field) => (
        <div key={field.key} className="mt-4">
          <label htmlFor={`clarify-${field.key}`} className="block text-caption font-semibold text-gray-500">
            {field.label}
          </label>
          {field.inputType === "AMOUNT" && field.presets && field.presets.length > 0 && (
            <div className="mt-2 flex flex-wrap gap-1.5">
              {field.presets.map((preset) => (
                <button
                  key={preset}
                  type="button"
                  aria-pressed={values[field.key] === String(preset)}
                  onClick={() => set(field.key, String(preset))}
                  className={`min-h-9 rounded-lg px-3 text-[11px] ${values[field.key] === String(preset) ? "bg-primary-300 text-white" : "bg-white text-gray-500"}`}
                >
                  {preset.toLocaleString("ko-KR")}원
                </button>
              ))}
            </div>
          )}
          <input
            id={`clarify-${field.key}`}
            inputMode={field.inputType === "AMOUNT" ? "numeric" : undefined}
            value={values[field.key] ?? ""}
            onChange={(event) => set(field.key, event.target.value)}
            placeholder={
              field.inputType === "AMOUNT"
                ? "예) 30000"
                : field.inputType === "TEXT_LIST"
                  ? "쉼표로 나눠 적어주세요. 예) 토너, 세럼, 크림"
                  : field.inputType === "PRODUCT"
                    ? "제품 이름"
                    : ""
            }
            className="mt-2 w-full rounded-xl border border-gray-200 bg-white px-3 py-3 text-caption outline-primary-500"
          />
        </div>
      ))}
      <label htmlFor="clarify-text" className="mt-4 block text-caption font-semibold text-gray-500">
        {fields.length ? "더 하고 싶은 말 (선택)" : "답변"}
      </label>
      <input
        id="clarify-text"
        value={text}
        maxLength={500}
        onChange={(event) => setText(event.target.value)}
        className="mt-2 w-full rounded-xl border border-gray-200 bg-white px-3 py-3 text-caption outline-primary-500"
      />
      {error && (
        <p role="alert" className="mt-3 text-[11px] leading-4 text-red-700">
          {error}
        </p>
      )}
      <button
        type="submit"
        disabled={empty || submitting}
        className="mt-4 h-12 w-full rounded-xl bg-primary-600 text-body2 font-semibold text-white disabled:opacity-40"
      >
        {submitting ? "보내는 중" : "답하고 계속 찾기"}
      </button>
    </form>
  );
}

/** 예산 세트 되묻기. 예산은 칩이나 직접 입력, 구성은 쉼표로 나눠 자유롭게 */
function BundleClarify({
  fields,
  values,
  set,
  submitting,
  error,
  empty,
  onSubmit,
}: {
  fields: ClarifyField[];
  values: Record<string, string>;
  set: (key: string, value: string) => void;
  submitting: boolean;
  error?: string;
  empty: boolean;
  onSubmit: () => void;
}) {
  const [skin, setSkin] = useState<string | null>(null);

  // 피부 정보는 다시 묻지 않고 프로필에서 가져온다는 것을 알려준다
  useEffect(() => {
    let active = true;
    getMyProfile()
      .then(({ data }) => {
        const profile = data?.skinProfile;
        const parts = [
          profile?.skinType ? SKIN_TYPE_LABEL[profile.skinType] ?? null : null,
          ...(profile?.skinConcerns ?? []).slice(0, 1).map((c) => CONCERN_LABEL[c] ?? null),
        ].filter(Boolean);
        if (active && parts.length) setSkin(parts.join(" · "));
      })
      .catch(() => {});
    return () => {
      active = false;
    };
  }, []);

  const asked = fields.filter((field) => field.inputType === "AMOUNT" || field.inputType === "TEXT_LIST").length;

  return (
    <form
      className="mt-5"
      onSubmit={(event) => {
        event.preventDefault();
        if (!empty && !submitting) onSubmit();
      }}
    >
      <div className="flex items-start gap-3">
        <span aria-hidden="true" className="grid h-9 w-9 shrink-0 place-items-center rounded-lg bg-primary-100 text-body2 font-bold text-primary-600">
          ?
        </span>
        <div>
          <h2 className="whitespace-pre-line text-lg font-bold leading-7 text-slate-800">
            {`${COUNT_WORD[asked] ?? asked} 가지만 알려주시면\n바로 찾아드릴게요`}
          </h2>
          <p className="mt-1 text-caption text-slate-500">한 번만 여쭤보고 그다음부터는 묻지 않아요</p>
        </div>
      </div>

      {fields.map((field) => {
        const value = values[field.key] ?? "";
        if (field.inputType === "AMOUNT") {
          const presets = field.presets?.length ? field.presets : DEFAULT_BUDGET_PRESETS;
          return (
            <fieldset key={field.key} className="mt-6">
              <legend className="text-body2 font-semibold text-slate-800">예산은 얼마로 볼까요?</legend>
              <div className="mt-3 flex flex-wrap gap-2">
                {presets.map((preset) => {
                  const selected = value === String(preset);
                  return (
                    <button
                      key={preset}
                      type="button"
                      aria-pressed={selected}
                      onClick={() => set(field.key, String(preset))}
                      className={`min-h-11 rounded-xl px-4 text-body2 ${selected ? "bg-primary-300 font-semibold text-white" : "bg-slate-100 text-slate-700"}`}
                    >
                      {preset % 10000 === 0 ? `${preset / 10000}만원` : `${preset.toLocaleString("ko-KR")}원`}
                    </button>
                  );
                })}
              </div>
              <label className="mt-3 flex items-center rounded-xl border border-slate-200 px-4 focus-within:border-primary-400">
                <span className="sr-only">예산 직접 입력</span>
                <input
                  inputMode="numeric"
                  value={presets.includes(Number(value)) ? "" : value}
                  onChange={(event) => set(field.key, event.target.value.replace(/[^\d]/g, ""))}
                  placeholder="직접 입력"
                  className="h-12 min-w-0 flex-1 bg-transparent text-body2 outline-none"
                />
                <span className="text-caption text-slate-400">원</span>
              </label>
            </fieldset>
          );
        }
        if (field.inputType === "TEXT_LIST") {
          const count = splitSteps(value).length;
          return (
            <div key={field.key} className="mt-6">
              <label htmlFor={`clarify-${field.key}`} className="block text-body2 font-semibold text-slate-800">
                어떤 화장품으로 구성할까요?
              </label>
              <p className="mt-1 text-[11px] text-slate-500">쉼표로 나눠서 자유롭게 적어주세요</p>
              <div className="relative mt-3">
                <textarea
                  id={`clarify-${field.key}`}
                  value={value}
                  rows={4}
                  onChange={(event) => set(field.key, event.target.value)}
                  placeholder="예) 토너, 세럼, 크림"
                  className="w-full resize-none rounded-xl border border-primary-300 px-4 pb-8 pt-3 text-body2 outline-primary-500"
                />
                {count > 0 && (
                  <span className="absolute bottom-3 right-4 text-[11px] text-primary-600">{count}개 입력됨</span>
                )}
              </div>
              <p className="mt-4 text-[11px] text-slate-500">이렇게 적어도 돼요</p>
              <ul className="mt-2 grid gap-2">
                {STEP_EXAMPLES.map((example) => (
                  <li key={example.phrase}>
                    <button
                      type="button"
                      onClick={() => set(field.key, example.steps.join(", "))}
                      className="w-full rounded-xl bg-slate-100 px-4 py-3 text-left"
                    >
                      <span className="block text-caption font-semibold text-slate-700">“{example.phrase}”</span>
                      <span className="block text-[11px] text-slate-500">{example.steps.join(" · ")}으로 알아들어요</span>
                    </button>
                  </li>
                ))}
              </ul>
            </div>
          );
        }
        return (
          <div key={field.key} className="mt-6">
            <label htmlFor={`clarify-${field.key}`} className="block text-body2 font-semibold text-slate-800">
              {field.label}
            </label>
            <input
              id={`clarify-${field.key}`}
              value={value}
              onChange={(event) => set(field.key, event.target.value)}
              className="mt-2 w-full rounded-xl border border-slate-200 px-4 py-3 text-body2 outline-primary-500"
            />
          </div>
        );
      })}

      {skin && (
        <p className="mt-5 rounded-xl bg-primary-50 px-4 py-3 text-[11px] text-primary-700">
          피부 정보는 프로필에서 가져왔어요 · {skin}
        </p>
      )}
      {error && (
        <p role="alert" className="mt-3 text-[11px] leading-4 text-red-700">
          {error}
        </p>
      )}
      <button
        type="submit"
        disabled={empty || submitting}
        className="mt-5 h-12 w-full rounded-xl bg-primary-600 text-body2 font-semibold text-white disabled:opacity-40"
      >
        {submitting ? "보내는 중" : "이대로 찾아보기"}
      </button>
    </form>
  );
}
