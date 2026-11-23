import { useEffect, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { AlertTriangle, Nfc } from "lucide-react";
import { recognizeProduct } from "../../api/productApi";
import { PageHeader } from "../../components/common/PageHeader";
import AppLayout from "../../layouts/AppLayout";

type ScanState = "idle" | "scanning" | "reading" | "error";

/** Web NFC 의 NDEFRecord 중 여기서 쓰는 값. */
interface NfcRecord {
  recordType: string;
  /** text 레코드의 문자 인코딩. 없으면 utf-8 */
  encoding?: string;
  data?: DataView;
}

/**
 * 레코드 본문을 문자열로 바꾼다. Web NFC 레코드에는 toText() 가 없어 data 를 직접 디코딩한다.
 * text 레코드는 레코드의 encoding 을, url 레코드는 utf-8 을 쓴다.
 */
function decodeRecord(record: NfcRecord): string {
  if (!record.data) throw new Error("EMPTY_RECORD");
  const encoding = record.recordType === "text" ? record.encoding || "utf-8" : "utf-8";
  const text = new TextDecoder(encoding).decode(record.data).trim();
  if (!text) throw new Error("EMPTY_RECORD");
  return text;
}

export function NfcScanPage() {
  const navigate = useNavigate();
  const { pathname, state: routeState } = useLocation() as {
    pathname: string;
    // 검색에서 왔으면 "detail". 인식 확인 화면에 그대로 넘겨 제품 상세로 보낸다.
    state: { next?: "detail" } | null;
  };
  const isDemo = pathname.endsWith("/demo");

  const [state, setState] = useState<ScanState>(isDemo ? "scanning" : "idle");
  const [errorMsg, setErrorMsg] = useState("");

  async function startNfcScan() {
    if (isDemo) {
      setState("scanning");
      return;
    }

    if (!("NDEFReader" in window)) {
      setErrorMsg("이 기기는 NFC를 지원하지 않아요.");
      setState("error");
      return;
    }

    setState("scanning");
    try {
      // @ts-expect-error - NDEFReader is experimental
      const reader = new window.NDEFReader();
      await reader.scan();

      reader.onreading = async (event: { message: { records: NfcRecord[] } }) => {
        setState("reading");
        const record = event.message.records.find(
          (r) => r.recordType === "url" || r.recordType === "text",
        );
        if (!record) {
          setErrorMsg("인식된 제품 정보가 없어요.");
          setState("error");
          return;
        }
        try {
          const nfcData = decodeRecord(record);
          const res = await recognizeProduct("NFC", nfcData);
          navigate("/product/recognize", {
            state: { result: res.data, next: routeState?.next },
          });
        } catch {
          setErrorMsg("제품 조회에 실패했어요.");
          setState("error");
        }
      };

      reader.onreadingerror = () => {
        setErrorMsg("NFC 태그를 읽을 수 없어요. 다시 시도해주세요.");
        setState("error");
      };
    } catch {
      setErrorMsg("NFC 스캔을 시작할 수 없어요. 권한을 확인해주세요.");
      setState("error");
    }
  }

  useEffect(() => {
    startNfcScan();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <AppLayout>
      <div className="flex h-screen flex-col overflow-hidden">
        <div className="flex-1 overflow-y-auto scrollbar-none">
          <section className="flex flex-col items-center px-6 pb-8 pt-10">
            <div className="w-full">
              <PageHeader title="NFC 태그 조회" onBack={() => navigate(-1)} />
            </div>

            {isDemo && (
              <div className="mt-4 w-full rounded-xl bg-primary-50 px-4 py-2">
                <p className="text-caption text-primary-500">데모 모드라 실제 NFC 태그는 읽지 않아요</p>
              </div>
            )}

            <div className="mt-14 flex flex-1 flex-col items-center justify-center text-center">
              {state !== "error" ? (
                <>
                  <div className="relative flex h-40 w-40 items-center justify-center">
                    <div
                      className={`absolute inset-0 rounded-full border-4 border-primary-300 ${
                        state === "scanning" ? "opacity-30 motion-safe:animate-ping" : "opacity-0"
                      }`}
                    />
                    <div
                      className="flex h-28 w-28 items-center justify-center rounded-full"
                      style={{
                        background: "linear-gradient(135deg, var(--color-primary-100), var(--color-primary-300))",
                      }}
                    >
                      <Nfc aria-hidden="true" className="h-12 w-12 text-primary-600" strokeWidth={1.8} />
                    </div>
                  </div>
                  <h2 className="mt-8 text-h3 text-gray-500">
                    {state === "idle" && "NFC 스캔 준비 중..."}
                    {state === "scanning" && "제품 태그를 가져다 대세요"}
                    {state === "reading" && "제품 정보를 읽는 중..."}
                  </h2>
                  <p className="mt-3 text-body2 text-gray-300">
                    {state === "scanning"
                      ? "스마트폰 후면을 제품 NFC 태그에 가까이 대주세요"
                      : "잠시만 기다려주세요"}
                  </p>
                </>
              ) : (
                <>
                  <div
                    className="flex h-28 w-28 items-center justify-center rounded-full"
                    style={{ background: "var(--color-red-50)" }}
                  >
                    <AlertTriangle className="h-12 w-12 text-red-400" strokeWidth={1.5} />
                  </div>
                  <h2 className="mt-8 text-h3 text-gray-500">스캔 실패</h2>
                  <p className="mt-3 text-body2 text-gray-300">{errorMsg}</p>
                  <button
                    className="mt-8 h-12 rounded-xl bg-primary-500 px-8 text-body2 text-white"
                    onClick={() => {
                      setState("idle");
                      setErrorMsg("");
                      startNfcScan();
                    }}
                    type="button"
                  >
                    다시 시도
                  </button>
                </>
              )}
            </div>
          </section>
        </div>
      </div>
    </AppLayout>
  );
}
