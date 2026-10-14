import { useState } from "react";
import { PageHeader } from "../common/PageHeader";
import { PrimaryButton } from "../common/PrimaryButton";

export interface OtherProfile {
  recipient: string;
  personalColor: string;
  skinType: string;
  concerns: string[];
}

export const DEFAULT_OTHER_PROFILE: OtherProfile = {
  recipient: "엄마",
  personalColor: "뮤트 · 가을 뮤트",
  skinType: "건성",
  concerns: ["민감성", "속건조"],
};

export function OtherProfileForm({
  initial,
  onBack,
  onSubmit,
}: {
  initial: OtherProfile;
  onBack: () => void;
  onSubmit: (profile: OtherProfile) => void;
}) {
  const [profile, setProfile] = useState<OtherProfile>(() => ({
    ...initial,
    concerns: [...initial.concerns],
  }));
  const [customRecipient, setCustomRecipient] = useState(
    !["엄마", "아빠", "아이 · 아기", "친구 선물"].includes(initial.recipient),
  );
  const single = (
    field: "recipient" | "personalColor" | "skinType",
    value: string,
  ) => {
    setProfile((previous) => ({ ...previous, [field]: value }));
  };
  const chips = (
    field: "recipient" | "personalColor" | "skinType",
    values: string[],
  ) =>
    values.map((value) => (
      <button
        key={value}
        type="button"
        aria-pressed={
          field === "recipient"
            ? customRecipient
              ? value === "직접 입력"
              : profile.recipient === value
            : profile[field] === value
        }
        onClick={() => {
          if (field === "recipient") {
            setCustomRecipient(value === "직접 입력");
            single(field, value === "직접 입력" ? "" : value);
          } else single(field, value);
        }}
        className={`rounded-xl px-4 py-2.5 text-caption ${(field === "recipient" ? (customRecipient ? value === "직접 입력" : profile.recipient === value) : profile[field] === value) ? (field === "personalColor" ? "bg-gray-500 text-white" : "bg-primary-300 text-white") : "bg-gray-100 text-gray-400"}`}
      >
        {value}
      </button>
    ));
  return (
    <section className="min-h-screen px-5 pb-6 pt-10">
      <PageHeader title="쓰실 분 정보" onBack={onBack} />
      <h2 className="mt-6 text-h3 text-gray-500">누가 쓸 화장품인가요?</h2>
      <p className="mt-1 text-caption text-gray-300">
        아는 것만 골라주세요. 비워두셔도 추천은 돼요
      </p>
      <fieldset className="mt-6">
        <legend className="mb-2 text-caption text-gray-500">
          누구 건가요?
        </legend>
        <div className="flex flex-wrap gap-2">
          {chips("recipient", [
            "엄마",
            "아빠",
            "아이 · 아기",
            "친구 선물",
            "직접 입력",
          ])}
        </div>
        {customRecipient && (
          <input
            aria-label="쓰실 분 직접 입력"
            placeholder="누가 쓰실 건가요?"
            value={profile.recipient}
            onChange={(event) => single("recipient", event.target.value)}
            className="mt-3 w-full rounded-xl border border-gray-200 p-3 text-caption"
          />
        )}
      </fieldset>
      <fieldset className="mt-5">
        <legend className="mb-2 text-caption text-gray-500">퍼스널 컬러</legend>
        <div className="grid grid-cols-2 gap-2">
          {chips("personalColor", [
            "웜톤 · 봄 웜",
            "쿨톤 · 여름 쿨",
            "뮤트 · 가을 뮤트",
            "쿨톤 · 겨울 쿨",
          ])}
        </div>
        <button
          type="button"
          aria-pressed={!profile.personalColor}
          onClick={() => single("personalColor", "")}
          className={`mt-2 w-full rounded-xl py-3 text-caption ${!profile.personalColor ? "bg-primary-300 text-white" : "bg-gray-100 text-gray-300"}`}
        >
          잘 모르겠어요
        </button>
      </fieldset>
      <fieldset className="mt-5">
        <legend className="mb-2 text-caption text-gray-500">피부 타입</legend>
        <div className="flex flex-wrap gap-2">
          {chips("skinType", ["건성", "중성", "지성", "복합성", "수부지"])}
        </div>
      </fieldset>
      <fieldset className="mt-5">
        <legend className="mb-2 text-caption text-gray-500">
          피부 고민 (복수선택)
        </legend>
        <div className="flex flex-wrap gap-2">
          {["민감성", "속건조", "주름/탄력", "미백/잡티", "모공"].map(
            (concern) => {
              const selected = profile.concerns.includes(concern);
              return (
                <button
                  key={concern}
                  type="button"
                  aria-pressed={selected}
                  onClick={() =>
                    setProfile((previous) => ({
                      ...previous,
                      concerns: selected
                        ? previous.concerns.filter((item) => item !== concern)
                        : [...previous.concerns, concern],
                    }))
                  }
                  className={`rounded-xl px-4 py-2.5 text-caption ${selected ? "bg-primary-300 text-white" : "bg-gray-100 text-gray-400"}`}
                >
                  {concern}
                </button>
              );
            },
          )}
        </div>
      </fieldset>
      <PrimaryButton
        className="mt-8"
        onClick={() =>
          onSubmit({
            ...profile,
            recipient: profile.recipient.trim() || "다른 사람",
          })
        }
      >
        이 조건으로 추천받기
      </PrimaryButton>
    </section>
  );
}
