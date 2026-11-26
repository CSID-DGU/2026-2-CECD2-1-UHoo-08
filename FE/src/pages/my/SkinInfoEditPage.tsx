import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Droplets } from "lucide-react";
import {
  CONCERN_LABEL,
  PERSONAL_COLOR_LABEL,
  SKIN_TYPE_LABEL,
  getMyProfile,
  updateSkinProfileByLabel,
} from "../../api/userApi";
import { PageHeader } from "../../components/common/PageHeader";
import { PrimaryButton } from "../../components/common/PrimaryButton";
import AppLayout from "../../layouts/AppLayout";
import { personalColors, skinConcerns, skinTypes } from "../../data/profileOptions";

const glass = {
  background: "color-mix(in srgb, var(--color-white) 68%, transparent)",
  backdropFilter: "blur(14px)",
  WebkitBackdropFilter: "blur(14px)",
  border: "1px solid color-mix(in srgb, var(--color-white) 90%, transparent)",
};

function SectionCard({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="mt-4 rounded-2xl p-5" style={glass}>
      <h2 className="mb-4 text-body2 font-semibold text-primary-600">{title}</h2>
      {children}
    </div>
  );
}

export function SkinInfoEditPage() {
  const navigate = useNavigate();
  const [skinType, setSkinType] = useState("지성");
  const [color, setColor] = useState("잘 모르겠어요");
  const [selected, setSelected] = useState<string[]>([]);
  const [notes, setNotes] = useState<string[]>([]);
  const [noteInput, setNoteInput] = useState("");
  const [showInput, setShowInput] = useState(false);
  const [loading, setLoading] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    getMyProfile()
      .then((res) => {
        const skin = res.data.skinProfile;
        if (!skin) return;
        if (skin.skinType) {
          const label = SKIN_TYPE_LABEL[skin.skinType];
          if (label) setSkinType(label);
        }
        if (skin.personalColor) {
          const label = PERSONAL_COLOR_LABEL[skin.personalColor];
          if (label) setColor(label);
        }
        if (skin.skinConcerns?.length) {
          setSelected(
            skin.skinConcerns.map((c) => CONCERN_LABEL[c]).filter(Boolean) as string[],
          );
        }
        if (skin.notes?.length) setNotes(skin.notes);
      })
      .catch(() => {});
  }, []);

  useEffect(() => {
    if (showInput) inputRef.current?.focus();
  }, [showInput]);

  function toggleConcern(concern: string) {
    setSelected((cur) =>
      cur.includes(concern) ? cur.filter((c) => c !== concern) : [...cur, concern],
    );
  }

  function addNote() {
    const trimmed = noteInput.trim();
    if (trimmed) setNotes((cur) => [...cur, trimmed]);
    setNoteInput("");
    setShowInput(false);
  }

  async function handleSave() {
    setLoading(true);
    try {
      await updateSkinProfileByLabel(color, skinType, selected, notes);
      navigate("/my");
    } catch {
      // silent
    } finally {
      setLoading(false);
    }
  }

  return (
    <AppLayout>
      <div
        className="flex h-screen flex-col overflow-hidden"
        style={{ background: "linear-gradient(160deg, var(--color-surface-tint) 0%, var(--color-white) 55%, var(--color-line-tint) 100%)" }}
      >
        <div className="flex-1 overflow-y-auto scrollbar-none">
        <section className="flex flex-col px-5 pb-8 pt-10">
          <PageHeader title="" onBack={() => navigate(-1)} />

          {/* 헤더 카드 */}
          <div
            className="mt-2 flex items-center gap-4 rounded-2xl px-5 py-5"
            style={{
              background: "linear-gradient(135deg, color-mix(in srgb, var(--color-primary-500) 18%, transparent), color-mix(in srgb, var(--color-primary-300) 12%, transparent))",
              backdropFilter: "blur(16px)",
              WebkitBackdropFilter: "blur(16px)",
              border: "1px solid color-mix(in srgb, var(--color-white) 85%, transparent)",
            }}
          >
            <div
              className="flex h-12 w-12 shrink-0 items-center justify-center rounded-full"
              style={{ background: "linear-gradient(135deg, var(--color-primary-400), var(--color-primary-700))" }}
            >
              <Droplets className="h-6 w-6 text-white" strokeWidth={1.8} />
            </div>
            <div>
              <h1 className="text-h3 text-gray-500">피부 정보 수정</h1>
              <p className="mt-0.5 text-caption text-gray-300">맞춤 추천을 위해 정확히 입력해주세요</p>
            </div>
          </div>

          {/* 피부 타입 */}
          <SectionCard title="피부 타입">
            <div className="flex flex-wrap gap-2">
              {skinTypes.map((type) => (
                <button
                  key={type}
                  className="h-10 rounded-xl px-5 text-body2 transition-colors"
                  style={
                    skinType === type
                      ? {
                          background: "linear-gradient(135deg, var(--color-primary-500), var(--color-primary-700))",
                          color: "white",
                        }
                      : { background: "color-mix(in srgb, var(--color-white) 70%, transparent)", color: "var(--color-gray-300)", border: "1px solid color-mix(in srgb, var(--color-gray-200) 50%, transparent)" }
                  }
                  onClick={() => setSkinType(type)}
                  type="button"
                >
                  {type}
                </button>
              ))}
            </div>
          </SectionCard>

          {/* 퍼스널 컬러 */}
          <SectionCard title="퍼스널 컬러">
            <div className="grid grid-cols-2 gap-2">
              {personalColors.map((item) => (
                <button
                  key={item}
                  className={`h-[52px] whitespace-pre-line rounded-xl text-body2 transition-colors ${
                    item === "잘 모르겠어요" ? "col-span-2" : ""
                  }`}
                  style={
                    color === item
                      ? {
                          background: "linear-gradient(135deg, var(--color-gray-400), var(--color-gray-500))",
                          color: "white",
                        }
                      : { background: "color-mix(in srgb, var(--color-white) 70%, transparent)", color: "var(--color-gray-300)", border: "1px solid color-mix(in srgb, var(--color-gray-200) 50%, transparent)" }
                  }
                  onClick={() => setColor(item)}
                  type="button"
                >
                  {item}
                </button>
              ))}
            </div>
          </SectionCard>

          {/* 피부 고민 */}
          <SectionCard title="피부 고민 (복수 선택)">
            <div className="flex flex-wrap gap-2">
              {skinConcerns.map((concern) => (
                <button
                  key={concern}
                  className="h-9 rounded-full px-4 text-body2 transition-colors"
                  style={
                    selected.includes(concern)
                      ? {
                          background: "linear-gradient(135deg, var(--color-primary-400), var(--color-primary-600))",
                          color: "white",
                        }
                      : { background: "color-mix(in srgb, var(--color-white) 70%, transparent)", color: "var(--color-gray-300)", border: "1px solid color-mix(in srgb, var(--color-gray-200) 50%, transparent)" }
                  }
                  onClick={() => toggleConcern(concern)}
                  type="button"
                >
                  {concern}
                </button>
              ))}
            </div>
          </SectionCard>

          {/* 특이사항 */}
          <SectionCard title="특이사항">
            <div className="grid gap-2">
              {notes.map((note, idx) => (
                <div
                  key={idx}
                  className="flex items-center justify-between rounded-xl px-4 py-3"
                  style={{ background: "color-mix(in srgb, var(--color-primary-50) 80%, transparent)", border: "1px solid color-mix(in srgb, var(--color-primary-300) 40%, transparent)" }}
                >
                  <p className="flex-1 text-body2 text-gray-500">{note}</p>
                  <button
                    className="ml-3 text-caption text-gray-300"
                    onClick={() => setNotes((cur) => cur.filter((_, i) => i !== idx))}
                    type="button"
                    aria-label="삭제"
                  >
                    ✕
                  </button>
                </div>
              ))}
            </div>

            {showInput ? (
              <div className="mt-3 flex gap-2">
                <input
                  ref={inputRef}
                  className="h-10 flex-1 rounded-xl border border-gray-200 bg-white/80 px-3 text-body2 outline-none focus:border-primary-500"
                  placeholder="특이사항을 입력해주세요"
                  value={noteInput}
                  onChange={(e) => setNoteInput(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && addNote()}
                />
                <button
                  className="h-10 rounded-xl px-4 text-caption text-white"
                  style={{ background: "linear-gradient(135deg, var(--color-primary-500), var(--color-primary-700))" }}
                  onClick={addNote}
                  type="button"
                >
                  확인
                </button>
              </div>
            ) : (
              <button
                className="mt-3 w-full py-2 text-body2 text-primary-500"
                onClick={() => setShowInput(true)}
                type="button"
              >
                + 추가하기
              </button>
            )}
          </SectionCard>

          <div className="mt-6">
            <PrimaryButton disabled={loading} onClick={handleSave}>
              {loading ? "저장 중..." : "정보 저장하기"}
            </PrimaryButton>
          </div>
        </section>
        </div>
      </div>
    </AppLayout>
  );
}
