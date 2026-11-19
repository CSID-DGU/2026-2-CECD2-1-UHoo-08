import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { aiRecognizeProduct } from "../../api/productApi";
import { fileToBase64, supportsWebNfc } from "../../lib/fileToBase64";
import { withDeadline } from "../../lib/searchAnalysis";

/** AI 서버의 사진 인식 제한 시간(60초)과 맞춘다. */
const RECOGNIZE_TIMEOUT_MS = 60_000;

/**
 * 검색 화면의 사진·NFC 로 찾기.
 *
 * 인식은 기존 기능을 그대로 쓴다. 사진은 AI 인식(/ai/internal/recognize), NFC 는
 * NFC 조회 화면이다. 다른 점은 끝나는 곳이다. 검색에서 찾았으면 추천 흐름이 아니라
 * 제품 상세로 보낸다(next: "detail"). 맞는지는 상세에서 판단한다.
 *
 * 숨은 파일 입력(inputs)을 화면 어딘가에 그려야 카메라·앨범이 열린다.
 */
export function useProductLens(after: "detail" | "recommend" = "detail") {
  // 인식 확인 화면에 넘길 다음 행선지. 추천 흐름이면 비워 둔다(확인 화면의 기본 동작).
  const next = after === "detail" ? "detail" : undefined;
  const navigate = useNavigate();
  const cameraRef = useRef<HTMLInputElement>(null);
  const albumRef = useRef<HTMLInputElement>(null);
  const [recognizing, setRecognizing] = useState(false);
  const [error, setError] = useState("");
  const nfcSupported = supportsWebNfc();

  // 화면을 떠났거나 새 인식을 시작하면 이전 요청의 응답은 버린다.
  const attempt = useRef(0);
  useEffect(() => {
    return () => {
      attempt.current += 1;
    };
  }, []);

  async function recognize(file: File) {
    const current = ++attempt.current;
    setRecognizing(true);
    setError("");
    try {
      const base64 = await fileToBase64(file);
      // 인식이 멈춰도 로딩에 갇히지 않게 시간을 끊는다.
      const res = await withDeadline(aiRecognizeProduct("IMAGE", base64), RECOGNIZE_TIMEOUT_MS);
      if (current !== attempt.current) return;
      // 제품을 못 찾았으면 확인 화면으로 넘기지 않고 여기서 다시 찍게 한다.
      if (!res?.productId) throw new Error("NOT_FOUND");
      navigate("/product/recognize", {
        state: {
          result: {
            productId: res.productId,
            name: res.name ?? "",
            brand: res.brand ?? "",
            imageUrl: null,
          },
          next,
        },
      });
    } catch (error) {
      if (current !== attempt.current) return;
      setError(
        error instanceof Error && error.message === "TIMEOUT"
          ? "인식이 오래 걸려 멈췄어요. 잠시 후 다시 시도해주세요."
          : "사진에서 제품을 찾지 못했어요. 제품 이름이 잘 보이게 다시 찍어주세요.",
      );
    } finally {
      if (current === attempt.current) setRecognizing(false);
    }
  }

  function onFile(event: React.ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    event.target.value = ""; // 같은 사진을 다시 골라도 열리게 비운다.
    if (file) void recognize(file);
  }

  const inputs = (
    <>
      <input
        ref={cameraRef}
        type="file"
        accept="image/*"
        capture="environment"
        className="hidden"
        onChange={onFile}
      />
      <input ref={albumRef} type="file" accept="image/*" className="hidden" onChange={onFile} />
    </>
  );

  return {
    inputs,
    recognizing,
    error,
    clearError: () => setError(""),
    nfcSupported,
    openCamera: () => cameraRef.current?.click(),
    openAlbum: () => albumRef.current?.click(),
    openNfc: () => navigate("/recommendation/nfc-scan", { state: { next } }),
  };
}
