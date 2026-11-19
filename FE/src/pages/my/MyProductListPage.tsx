import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { AlertTriangle, ChevronLeft, Plus, Trash2 } from "lucide-react";
import {
  deleteUserProduct,
  getAllUserProducts,
  toServerDate,
  updateUserProduct,
  type UserProductItem,
  type UserProductList,
} from "../../api/userProductApi";
import {
  getMyProducts,
  getRegisterOptions,
  updateMyProduct,
  type StorageOption,
} from "../../api/myProductApi";
import { getMyProfile } from "../../api/userApi";
import { OpenedDateInput } from "../../components/my/OpenedDateInput";
import { fromOpenedAt, toOpenedAt } from "../../components/my/openedDate";
import AppLayout from "../../layouts/AppLayout";

const TABS = [
  { id: "USING", label: "쓰는 중" },
  { id: "FINISHED", label: "다 쓴 제품" },
] as const;
type Tab = (typeof TABS)[number]["id"];

const REMAINING = [100, 75, 50, 25];

/**
 * 보유 화장품 목록과 수정 (BE /user-products).
 *
 * 교체 시기와 같이 쓰면 안 되는 제품을 목록에서 바로 보여준다.
 * 보관 위치는 BE 가 다루지 않아, 같은 행을 쓰는 AI CARE 에서 이름을 가져와 붙인다.
 */
export function MyProductListPage() {
  const navigate = useNavigate();
  const [tab, setTab] = useState<Tab>("USING");
  const [version, setVersion] = useState(0);
  // 응답을 어떤 요청(탭·버전)의 것인지와 같이 둔다. 다시 불러오는 동안 이전 목록으로
  // 수정·삭제를 시작하지 않게, 지금 요청의 응답만 쓴다.
  const requestKey = `${tab}:${version}`;
  const [list, setList] = useState<{ key: string; value: UserProductList } | null>(null);
  const [failedKey, setFailedKey] = useState<string | null>(null);
  const failed = failedKey === requestKey;
  const [editing, setEditing] = useState<string | null>(null);
  /** 삭제는 되돌릴 수 없어 한 번 더 묻는다. */
  const [confirming, setConfirming] = useState<string | null>(null);
  const [actionError, setActionError] = useState("");

  // 보관 위치 (AI CARE). 보관함이 없는 사용자는 이 줄 자체를 숨긴다.
  const [userId, setUserId] = useState<string | null>(null);
  const [storages, setStorages] = useState<StorageOption[]>([]);
  const [storageOf, setStorageOf] = useState<Record<string, { id: string | null; label: string | null }>>({});

  useEffect(() => {
    let active = true;
    const key = `${tab}:${version}`;
    // 첫 쪽이 오면 먼저 보여주고, 나머지 쪽은 이어서 받아 채운다.
    getAllUserProducts(tab, (first) => {
      if (active) setList({ key, value: first });
    })
      .then((all) => {
        if (active) setList({ key, value: all });
      })
      .catch(() => {
        if (active) setFailedKey(key);
      });
    return () => {
      active = false;
    };
  }, [tab, version]);

  useEffect(() => {
    let active = true;
    getMyProfile()
      .then(async ({ data }) => {
        const [mine, options] = await Promise.all([getMyProducts(data.id), getRegisterOptions(data.id)]);
        if (!active) return;
        setUserId(data.id);
        setStorages(options.storages);
        setStorageOf(
          Object.fromEntries(
            mine.map((item) => [item.user_product_id, { id: item.storage_node_id, label: item.storage_label }]),
          ),
        );
      })
      .catch(() => {});
    return () => {
      active = false;
    };
  }, [version]);

  const value = list?.key === requestKey ? list.value : null;
  const reload = () => {
    setEditing(null);
    setConfirming(null);
    setVersion((v) => v + 1);
  };

  async function finish(item: UserProductItem) {
    setActionError("");
    try {
      await updateUserProduct(item.userProductId, { status: "FINISHED" });
      reload();
    } catch {
      setActionError("다 쓴 제품으로 옮기지 못했어요.");
    }
  }

  async function restore(item: UserProductItem) {
    setActionError("");
    try {
      await updateUserProduct(item.userProductId, { status: "USING" });
      reload();
    } catch {
      setActionError("같은 제품을 이미 쓰는 중이라 되돌릴 수 없어요.");
    }
  }

  async function remove(id: string) {
    setActionError("");
    try {
      await deleteUserProduct(id);
      reload();
    } catch {
      setActionError("삭제하지 못했어요.");
      setConfirming(null);
    }
  }

  return (
    <AppLayout className="pb-10">
      <header className="flex items-center gap-2 px-4 pt-4 pb-2">
        <button onClick={() => navigate(-1)} type="button" aria-label="뒤로">
          <ChevronLeft className="h-6 w-6 text-gray-500" strokeWidth={1.8} />
        </button>
        <h1 className="flex-1 text-body1 text-gray-500">보유 화장품</h1>
        <button
          className="flex items-center gap-1 text-body2 text-primary-500"
          onClick={() => navigate("/my/products/new")}
          type="button"
        >
          <Plus className="h-4 w-4" strokeWidth={2} />
          등록
        </button>
      </header>

      <div className="px-4">
        <div role="tablist" aria-label="보유 화장품 상태" className="mt-1 grid grid-cols-2 gap-1 rounded-xl bg-gray-100 p-1">
          {TABS.map((item) => (
            <button
              key={item.id}
              type="button"
              role="tab"
              aria-selected={tab === item.id}
              onClick={() => {
                setTab(item.id);
                setEditing(null);
                setConfirming(null);
              }}
              className={`min-h-10 rounded-lg text-caption ${tab === item.id ? "bg-white font-semibold text-gray-500 shadow-sm" : "text-gray-400"}`}
            >
              {item.label}
            </button>
          ))}
        </div>

        {tab === "USING" && value?.conflictSummary && value.conflictSummary.avoidCount > 0 && (
          <div className="mt-3 flex items-start gap-2 rounded-xl bg-red-50 p-3">
            <AlertTriangle aria-hidden="true" className="mt-0.5 h-4 w-4 shrink-0 text-red-700" />
            <p className="text-caption text-red-700">
              {value.conflictSummary.text ?? `같이 쓰면 안 되는 조합이 ${value.conflictSummary.avoidCount}개 있어요`}
            </p>
          </div>
        )}

        {actionError && (
          <p role="alert" className="mt-3 text-caption text-[#E05A5A]">
            {actionError}
          </p>
        )}

        {failed ? (
          <Empty text="목록을 불러오지 못했어요" />
        ) : !value ? (
          <Empty text="불러오는 중이에요" />
        ) : value.items.length === 0 ? (
          <Empty text={tab === "USING" ? "아직 등록한 화장품이 없어요" : "다 쓴 제품이 없어요"} />
        ) : (
          <div className="mt-3 flex flex-col gap-2">
            {value.items.map((item) => {
              const storage = storageOf[item.userProductId];
              return (
                <div className="rounded-2xl border border-gray-100 bg-white p-3" key={item.userProductId}>
                  <div className="flex items-start gap-3">
                    {item.imageUrl ? (
                      <img src={item.imageUrl} alt="" className="h-12 w-12 shrink-0 rounded-lg bg-gray-50 object-contain p-0.5" />
                    ) : (
                      <div className="h-12 w-12 shrink-0 rounded-lg bg-gray-50" />
                    )}
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-body2 text-gray-500">{item.name}</p>
                      <p className="mt-0.5 truncate text-caption text-gray-300">{item.brand}</p>
                    </div>
                  </div>

                  <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1">
                    <Meta label="개봉일" value={item.openedAt ?? "미등록"} />
                    <Meta label="남은 양" value={item.remainingPct != null ? `${item.remainingPct}%` : "—"} />
                    {storages.length > 0 && <Meta label="보관 위치" value={storage?.label ?? "미지정"} />}
                  </div>

                  {tab === "USING" && item.replaceText && (
                    <div className="mt-2">
                      <div className="flex items-center justify-between text-[11px]">
                        <span
                          className={
                            item.replaceStatus === "EXPIRED"
                              ? "text-red-700"
                              : item.replaceStatus === "SOON"
                                ? "text-[#8A5A12]"
                                : "text-gray-400"
                          }
                        >
                          {item.replaceText}
                        </span>
                      </div>
                      <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-gray-100">
                        <div
                          className={`h-full rounded-full ${
                            item.replaceStatus === "EXPIRED"
                              ? "bg-red-400"
                              : item.replaceStatus === "SOON"
                                ? "bg-[#E8A75A]"
                                : "bg-[#9DBDE9]"
                          }`}
                          style={{ width: `${Math.min(100, Math.max(0, item.replaceProgress))}%` }}
                        />
                      </div>
                    </div>
                  )}

                  {item.conflictText && (
                    <p className="mt-2 rounded-lg bg-red-50 px-2.5 py-1.5 text-[11px] text-red-700">{item.conflictText}</p>
                  )}

                  {editing === item.userProductId ? (
                    <EditForm
                      item={item}
                      storages={storages}
                      storageId={storage?.id ?? ""}
                      userId={userId}
                      onCancel={() => setEditing(null)}
                      onSaved={reload}
                    />
                  ) : confirming === item.userProductId ? (
                    <div className="mt-3 border-t border-gray-100 pt-3">
                      <p className="text-caption text-gray-400">
                        잘못 등록한 제품만 지워주세요. 다 쓴 제품은 ‘다 썼어요’로 옮기면 기록이 남아요.
                      </p>
                      <div className="mt-2 flex gap-2">
                        <button
                          className="h-[40px] flex-1 rounded-xl border border-gray-100 text-body2 text-gray-400"
                          onClick={() => setConfirming(null)}
                          type="button"
                        >
                          취소
                        </button>
                        <button
                          className="h-[40px] flex-1 rounded-xl text-body2 text-white"
                          style={{ background: "#E05A5A" }}
                          onClick={() => void remove(item.userProductId)}
                          type="button"
                        >
                          삭제
                        </button>
                      </div>
                    </div>
                  ) : (
                    <div className="mt-3 flex gap-2">
                      {tab === "USING" ? (
                        <>
                          <button
                            className="h-[40px] flex-1 rounded-xl border border-gray-100 text-body2 text-gray-400"
                            onClick={() => setEditing(item.userProductId)}
                            type="button"
                          >
                            수정
                          </button>
                          <button
                            className="h-[40px] flex-1 rounded-xl border border-gray-100 text-body2 text-gray-500"
                            onClick={() => void finish(item)}
                            type="button"
                          >
                            다 썼어요
                          </button>
                        </>
                      ) : (
                        <button
                          className="h-[40px] flex-1 rounded-xl border border-gray-100 text-body2 text-gray-400"
                          onClick={() => void restore(item)}
                          type="button"
                        >
                          다시 쓰는 중으로
                        </button>
                      )}
                      <button
                        className="grid h-[40px] w-[48px] place-items-center rounded-xl border border-gray-100"
                        onClick={() => setConfirming(item.userProductId)}
                        type="button"
                        aria-label={`${item.name} 삭제`}
                      >
                        <Trash2 className="h-4 w-4 text-gray-300" strokeWidth={1.8} />
                      </button>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>
    </AppLayout>
  );
}

function EditForm({
  item,
  storages,
  storageId,
  userId,
  onCancel,
  onSaved,
}: {
  item: UserProductItem;
  storages: StorageOption[];
  storageId: string;
  userId: string | null;
  onCancel: () => void;
  onSaved: () => void;
}) {
  const [opened, setOpened] = useState(fromOpenedAt(item.openedAt));
  const [remaining, setRemaining] = useState(item.remainingPct ?? 100);
  // 사용자가 직접 고른 보관 위치. 고르기 전에는 늦게 도착한 최신 값(storageId)을 그대로 보여준다.
  const [pickedStorage, setPickedStorage] = useState<string | null>(null);
  const storage = pickedStorage ?? storageId;
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const openedAt = toOpenedAt(opened.year, opened.month, opened.day);
  const openedTouched = Boolean(opened.year || opened.month || opened.day);

  const save = async () => {
    // 개봉일은 비워 두면 그대로 둔다. 일부만 넣었으면 알려준다.
    if (openedTouched && !openedAt) {
      setError("개봉일의 년·월을 확인해 주세요");
      return;
    }
    setSaving(true);
    setError(null);
    try {
      await updateUserProduct(item.userProductId, {
        remainingPct: remaining,
        openedAt: openedAt ? toServerDate(openedAt) : undefined,
      });
      if (userId && pickedStorage && pickedStorage !== storageId) {
        await updateMyProduct(userId, item.userProductId, { storage_node_id: pickedStorage });
      }
      onSaved();
    } catch {
      setError("수정하지 못했어요");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="mt-3 border-t border-gray-100 pt-3">
      <p className="mb-1.5 text-caption text-gray-400">개봉일</p>
      <OpenedDateInput year={opened.year} month={opened.month} day={opened.day} onChange={setOpened} />

      <p className="mt-3 mb-1.5 text-caption text-gray-400">남은 양</p>
      <div className="grid grid-cols-4 gap-2">
        {REMAINING.map((value) => (
          <button
            key={value}
            type="button"
            aria-pressed={remaining === value}
            onClick={() => setRemaining(value)}
            className={`h-[40px] rounded-xl border text-caption ${
              remaining === value ? "border-primary-500 bg-primary-50 text-primary-600" : "border-gray-100 bg-white text-gray-400"
            }`}
          >
            {value}%
          </button>
        ))}
      </div>

      {storages.length > 0 && (
        <>
          <p className="mt-3 mb-1.5 text-caption text-gray-400">보관 위치</p>
          <div className="flex flex-wrap gap-2">
            {storages.map((s) => (
              <button
                className={`h-[40px] rounded-xl border px-3 text-body2 ${
                  storage === s.node_id ? "border-primary-500 bg-primary-50 text-primary-600" : "border-gray-100 bg-white text-gray-400"
                }`}
                key={s.node_id}
                onClick={() => setPickedStorage(s.node_id)}
                type="button"
              >
                {s.label}
              </button>
            ))}
          </div>
        </>
      )}

      {error && <p className="mt-2 text-caption text-[#E05A5A]">{error}</p>}

      <div className="mt-3 flex gap-2">
        <button
          className="h-[44px] flex-1 rounded-xl border border-gray-100 text-body2 text-gray-400"
          onClick={onCancel}
          type="button"
        >
          취소
        </button>
        <button
          className="h-[44px] flex-1 rounded-xl bg-primary-500 text-body2 text-white disabled:bg-gray-200"
          disabled={saving}
          onClick={() => void save()}
          type="button"
        >
          {saving ? "저장 중…" : "저장"}
        </button>
      </div>
    </div>
  );
}

function Meta({ label, value }: { label: string; value: string }) {
  return (
    <p className="text-caption text-gray-400">
      {label} <span className="text-gray-500">{value}</span>
    </p>
  );
}

function Empty({ text }: { text: string }) {
  return (
    <div
      className="mt-4 flex h-[120px] items-center justify-center rounded-2xl"
      style={{ background: "#F0F5FD", border: "1px dashed #C5DDF5" }}
    >
      <p className="text-caption text-gray-300">{text}</p>
    </div>
  );
}

export default MyProductListPage;
