import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { recognizeProduct } from "../../api/productApi";
import { apiErrorCode } from "../../api/recommendationQueryApi";
import { fileToBase64, supportsWebNfc } from "../../lib/fileToBase64";
import { withDeadline } from "../../lib/searchAnalysis";

/** BE 는 AI 호출을 30초에서 끊는다. 그 응답을 받을 여유만 두고 끊는다. */
const RECOGNIZE_TIMEOUT_MS = 35_000;

/**
 * 검색 화면의 사진·NFC 로 찾기.
 *
 * 인식은 기존 기능을 그대로 쓴다. 사진은 BE 제품 인식(POST /products/recognize), NFC 는
 * NFC 조회 화면이다. AI 서버 내부 API(/ai/internal/recognize)를 직접 부르면 로컬에서는
 * Vite 프록시 덕에 되지만 배포에서는 Spring 으로 가서 실패한다. 온보딩 사진 등록,
 * NFC 화면과 같은 BE 경로를 쓴다.
 *
 * 다른 점은 끝나는 곳이다. 검색에서 찾았으면 추천 흐름이 아니라
 * 제품 상세로 보낸다(next: "detail"). 맞는지는 상세에서 판단한다.
 *
 * 숨은 파일 입력(inputs)을 화면 어딘가에 그려야 카메라·앨범이 열린다.
 */
/**
 * 실패 이유별 문구. 찍은 사진 탓(결과 없음)과 서버 탓(오류, 시간 초과)을 나눠,
 * 서버가 멈췄는데 사용자가 같은 사진을 계속 다시 찍게 만들지 않는다.
 */
function recognizeErrorMessage(error: unknown): string {
  if (error instanceof Error && error.message === "NOT_FOUND") {
    return "사진에서 제품을 찾지 못했어요. 제품 이름이 잘 보이게 다시 찍어주세요.";
  }
  if (error instanceof Error && error.message === "TIMEOUT") {
    return "인식이 오래 걸려 멈췄어요. 잠시 후 다시 시도해주세요.";
  }
  if (apiErrorCode(error) === "VALIDATION_ERROR") {
    return "사진을 읽지 못했어요. 다른 사진으로 다시 시도해주세요.";
  }
  // AI_SERVER_ERROR(AI 호출 실패·30초 초과), 네트워크 오류 등
  return "인식 서버에 문제가 생겼어요. 잠시 후 다시 시도해주세요.";
}

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
      const { data: res } = await withDeadline(recognizeProduct("IMAGE", base64), RECOGNIZE_TIMEOUT_MS);
      if (current !== attempt.current) return;
      // 제품을 못 찾았으면 서버는 200 에 productId 를 비워 준다. 확인 화면으로 넘기지 않고 다시 찍게 한다.
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
      setError(recognizeErrorMessage(error));
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
