import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { ChevronLeft, Search } from "lucide-react";
import { OpenedDateInput } from "../../components/my/OpenedDateInput";
import { toOpenedAt } from "../../components/my/openedDate";
import { searchProducts, type ProductSearchItem } from "../../api/productApi";
import {
  createUserProduct,
  toServerDate,
  type UserProductCreated,
} from "../../api/userProductApi";
import {
  getRegisterOptions,
  updateMyProduct,
  type StorageOption,
} from "../../api/myProductApi";
import { apiErrorCode } from "../../api/recommendationQueryApi";
import { getMyProfile } from "../../api/userApi";
import AppLayout from "../../layouts/AppLayout";

/** 남은 양. 처음 등록할 때는 대부분 새 제품이라 100을 기본으로 둔다. */
const REMAINING = [
  { value: 100, label: "새 제품" },
  { value: 75, label: "많이" },
  { value: 50, label: "반쯤" },
  { value: 25, label: "조금" },
];

/**
 * 보유 화장품 등록 (BE /user-products).
 *
 * 제품만 고르면 등록할 수 있다. 개봉일은 모르면 건너뛸 수 있다. 모르는 값을 억지로
 * 받으면 아무 날짜나 넣게 되고, 그 날짜가 교체 시기를 통째로 틀리게 만든다.
 * 건너뛰면 서버가 오늘로 기록하므로, 그 사실을 화면에 밝힌다.
 *
 * 보관 위치는 BE 가 받지 않아, 등록 직후 AI CARE 수정 API 로 같은 행에 넣는다.
 */
export function MyProductRegisterPage() {
  const navigate = useNavigate();
  const [userId, setUserId] = useState<string | null>(null);
  const [storages, setStorages] = useState<StorageOption[]>([]);

  const [keyword, setKeyword] = useState("");
  const [results, setResults] = useState<ProductSearchItem[] | null>(null);
  const [searching, setSearching] = useState(false);
  const [picked, setPicked] = useState<ProductSearchItem | null>(null);

  // 년·월을 넣거나, 모르면 건너뛴다. 일은 선택.
  const [opened, setOpened] = useState({ year: "", month: "", day: "" });
  const [skipOpened, setSkipOpened] = useState(false);
  const [remaining, setRemaining] = useState(100);
  const [storage, setStorage] = useState("");

  const openedAt = toOpenedAt(opened.year, opened.month, opened.day);
  const openedReady = skipOpened || Boolean(openedAt);

  const [saving, setSaving] = useState(false);
  const [done, setDone] = useState<(UserProductCreated & { storageFailed: boolean }) | null>(null);
  const [failed, setFailed] = useState<string | null>(null);

  useEffect(() => {
    getMyProfile()
      .then((res) => {
        setUserId(res.data.id);
        return getRegisterOptions(res.data.id);
      })
      .then((r) => {
        setStorages(r.storages);
        // 화장품은 대개 화장대에 둔다. 매번 고르게 하지 않는다.
        setStorage(r.storages.find((x) => x.default)?.node_id ?? "");
      })
      .catch(() => setStorages([]));
  }, []);

  const search = async () => {
    const q = keyword.trim();
    if (!q) return;
    setSearching(true);
    setFailed(null);
    try {
      const { data } = await searchProducts(q);
      setResults(data?.products ?? []);
    } catch {
      setFailed("제품을 찾지 못했어요");
    } finally {
      setSearching(false);
    }
  };

  const submit = async () => {
    if (!picked || !openedReady) return;
    setSaving(true);
    setFailed(null);
    try {
      const { data } = await createUserProduct({
        productId: picked.id,
        openedAt: !skipOpened && openedAt ? toServerDate(openedAt) : undefined,
        remainingPct: remaining,
        source: "MANUAL",
      });
      // 보관 위치는 같은 행에 AI CARE 로 넣는다. 실패해도 등록은 된 상태다.
      let storageFailed = false;
      if (storage && userId) {
        await updateMyProduct(userId, data.userProductId, { storage_node_id: storage }).catch(() => {
          storageFailed = true;
        });
      }
      setDone({ ...data, storageFailed });
    } catch (error) {
      setFailed(
        apiErrorCode(error) === "ALREADY_REGISTERED"
          ? "이미 쓰는 중으로 등록된 제품이에요"
          : "등록하지 못했어요. 다시 시도해주세요.",
      );
    } finally {
      setSaving(false);
    }
  };

  function reset() {
    setDone(null);
    setPicked(null);
    setResults(null);
    setKeyword("");
    setOpened({ year: "", month: "", day: "" });
    setSkipOpened(false);
    setRemaining(100);
    // 기본 보관 위치는 유지한다. 비우면 두 번째 제품부터 화장대가 풀린 채로 등록된다.
    setStorage(storages.find((x) => x.default)?.node_id ?? "");
  }

  if (done) {
    return (
      <AppLayout className="pb-10">
        <Header onBack={() => navigate(-1)} title="등록 완료" />
        <div className="px-4">
          <div className="mt-4 rounded-2xl border border-gray-100 bg-white p-4">
            <p className="text-body1 text-gray-500">{done.name}</p>
            <p className="mt-1 text-caption text-gray-300">보유 화장품에 등록했어요</p>
            {skipOpened && (
              <p className="mt-2 text-caption text-gray-400">
                개봉일은 오늘로 기록됐어요. 정확한 날짜가 생각나면 목록에서 고칠 수 있어요.
              </p>
            )}
            {done.storageFailed && (
              <p className="mt-2 text-caption text-[#8A5A12]">
                보관 위치는 저장하지 못했어요. 목록에서 다시 지정해 주세요.
              </p>
            )}
          </div>

          {done.conflicts.length > 0 && (
            <div className="mt-3 flex flex-col gap-2">
              {done.conflicts.map((conflict) => (
                <div
                  key={conflict.userProductId}
                  className={`rounded-xl p-3 ${conflict.level === "AVOID" ? "bg-red-50" : "bg-[#FDF3E7]"}`}
                >
                  <p className={`text-body2 ${conflict.level === "AVOID" ? "text-red-700" : "text-[#8A5A12]"}`}>
                    {conflict.name}와 {conflict.level === "AVOID" ? "같이 쓰지 마세요" : "시간을 나눠 쓰세요"}
                  </p>
                  {conflict.advice && <p className="mt-0.5 text-caption text-gray-400">{conflict.advice}</p>}
                </div>
              ))}
            </div>
          )}

          <div className="mt-4 flex gap-2">
            <button
              className="h-[52px] flex-1 rounded-2xl border border-gray-100 text-body1 text-gray-500"
              onClick={() => navigate("/my/products", { replace: true })}
              type="button"
            >
              목록 보기
            </button>
            <button
              className="h-[52px] flex-1 rounded-2xl bg-primary-500 text-body1 text-white"
              onClick={reset}
              type="button"
            >
              더 등록하기
            </button>
          </div>
        </div>
      </AppLayout>
    );
  }

  return (
    <AppLayout className="pb-10">
      <Header onBack={() => navigate(-1)} title="보유 화장품 등록" />

      <div className="px-4">
        {/* 1. 제품 고르기 — 유일한 필수 항목 */}
        <div className="mt-3 flex gap-2">
          <div className="flex flex-1 items-center gap-2 rounded-2xl border border-gray-100 bg-white px-3">
            <Search className="h-4 w-4 shrink-0 text-gray-300" strokeWidth={1.8} />
            <input
              className="h-[48px] w-full text-body2 text-gray-500 outline-none"
              placeholder="제품명 또는 브랜드"
              value={keyword}
              onChange={(e) => setKeyword(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && !e.nativeEvent.isComposing && void search()}
            />
          </div>
          <button
            className="h-[48px] shrink-0 rounded-2xl bg-primary-500 px-4 text-body2 text-white disabled:bg-gray-200"
            disabled={searching || !keyword.trim()}
            onClick={() => void search()}
            type="button"
          >
            {searching ? "검색 중" : "검색"}
          </button>
        </div>

        {picked ? (
          <div className="mt-3 flex items-center gap-3 rounded-2xl border border-primary-300 bg-primary-50 p-3">
            {picked.imageUrl && (
              <img src={picked.imageUrl} alt="" className="h-11 w-11 shrink-0 rounded-lg bg-white object-contain p-0.5" />
            )}
            <div className="min-w-0 flex-1">
              <p className="truncate text-body2 text-gray-500">{picked.name}</p>
              <p className="truncate text-caption text-gray-300">{picked.brand}</p>
            </div>
            <button
              className="shrink-0 text-caption text-primary-500"
              onClick={() => setPicked(null)}
              type="button"
            >
              변경
            </button>
          </div>
        ) : results ? (
          <div className="mt-3 flex flex-col gap-2">
            {results.length === 0 && (
              <p className="text-caption text-gray-300">검색 결과가 없어요</p>
            )}
            {results.map((p) => (
              <button
                className="flex items-center gap-3 rounded-2xl border border-gray-100 bg-white p-3 text-left"
                key={p.id}
                onClick={() => setPicked(p)}
                type="button"
              >
                {p.imageUrl && (
                  <img src={p.imageUrl} alt="" className="h-11 w-11 shrink-0 rounded-lg bg-gray-50 object-contain p-0.5" />
                )}
                <div className="min-w-0 flex-1">
                  <p className="truncate text-body2 text-gray-500">{p.name}</p>
                  <p className="truncate text-caption text-gray-300">
                    {p.brand}
                    {p.originalPrice != null && ` · ${p.originalPrice.toLocaleString()}원`}
                  </p>
                </div>
              </button>
            ))}
          </div>
        ) : null}

        {/* 2. 선택 항목 — 제품을 고른 뒤에만 묻는다 */}
        {picked && (
          <div className="mt-5">
            <Field label="개봉일">
              {!skipOpened && (
                <OpenedDateInput
                  year={opened.year}
                  month={opened.month}
                  day={opened.day}
                  onChange={setOpened}
                />
              )}
              <label className="mt-2 flex min-h-10 cursor-pointer items-center gap-2 text-caption text-gray-500">
                <input
                  type="checkbox"
                  checked={skipOpened}
                  onChange={(e) => setSkipOpened(e.target.checked)}
                  className="h-4 w-4 accent-primary-500"
                />
                개봉일을 몰라요 (건너뛰기)
              </label>
              {skipOpened && (
                <p className="text-[11px] text-gray-300">
                  오늘 날짜로 기록돼요. 나중에 목록에서 고칠 수 있어요.
                </p>
              )}
            </Field>

            <Field label="남은 양">
              <div className="grid grid-cols-4 gap-2">
                {REMAINING.map((option) => (
                  <button
                    key={option.value}
                    type="button"
                    aria-pressed={remaining === option.value}
                    onClick={() => setRemaining(option.value)}
                    className={`h-[44px] rounded-2xl border text-caption ${
                      remaining === option.value
                        ? "border-primary-500 bg-primary-50 text-primary-600"
                        : "border-gray-100 bg-white text-gray-400"
                    }`}
                  >
                    {option.label}
                  </button>
                ))}
              </div>
            </Field>

            {storages.length > 0 && (
              <Field label="보관 위치 (선택)">
                <div className="flex flex-wrap gap-2">
                  {storages.map((s) => (
                    <button
                      className={`h-[44px] rounded-2xl border px-4 text-body2 ${
                        storage === s.node_id
                          ? "border-primary-500 bg-primary-50 text-primary-600"
                          : "border-gray-100 bg-white text-gray-400"
                      }`}
                      key={s.node_id}
                      onClick={() => setStorage(storage === s.node_id ? "" : s.node_id)}
                      type="button"
                    >
                      {s.label}
                    </button>
                  ))}
                </div>
              </Field>
            )}
          </div>
        )}

        {failed && <p className="mt-3 text-caption text-[#E05A5A]">{failed}</p>}

        <button
          className="mt-5 h-[52px] w-full rounded-2xl bg-primary-500 text-body1 text-white disabled:bg-gray-200 disabled:text-gray-300"
          disabled={!picked || !openedReady || saving}
          onClick={() => void submit()}
          type="button"
        >
          {saving
            ? "등록하는 중…"
            : !picked
              ? "제품을 먼저 골라주세요"
              : !openedReady
                ? "개봉일을 넣거나 건너뛰어 주세요"
                : "등록하기"}
        </button>
      </div>
    </AppLayout>
  );
}

function Header({ onBack, title }: { onBack: () => void; title: string }) {
  return (
    <header className="flex items-center gap-2 px-4 pt-4 pb-2">
      <button onClick={onBack} type="button" aria-label="뒤로">
        <ChevronLeft className="h-6 w-6 text-gray-500" strokeWidth={1.8} />
      </button>
      <h1 className="text-body1 text-gray-500">{title}</h1>
    </header>
  );
}

function Field({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div className="mt-3">
      <p className="mb-1.5 text-caption text-gray-400">{label}</p>
      {children}
    </div>
  );
}

export default MyProductRegisterPage;
