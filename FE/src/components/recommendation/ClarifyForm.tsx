import { useState } from "react";
import type { ClarifyField, answerClarification } from "../../api/recommendationQueryApi";

type Answers = Parameters<typeof answerClarification>[1];

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
        // 서버가 항목당 50자, 최대 10개까지 받는다.
        const items = raw
          .split(/[,\n]/)
          .map((item) => item.trim().slice(0, 50))
          .filter(Boolean)
          .slice(0, 10);
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
        className="mt-4 h-12 w-full rounded-xl bg-primary-500 text-body2 font-semibold text-white disabled:opacity-40"
      >
        {submitting ? "보내는 중" : "답하고 계속 찾기"}
      </button>
    </form>
  );
}
