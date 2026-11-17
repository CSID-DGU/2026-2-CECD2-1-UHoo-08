import { useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { aiRecognizeProduct } from "../../api/productApi";
import { fileToBase64, supportsWebNfc } from "../../lib/fileToBase64";

/**
 * 검색 화면의 사진·NFC 로 찾기.
 *
 * 인식은 기존 기능을 그대로 쓴다. 사진은 AI 인식(/ai/internal/recognize), NFC 는
 * NFC 조회 화면이다. 다른 점은 끝나는 곳이다. 검색에서 찾았으면 추천 흐름이 아니라
 * 제품 상세로 보낸다(next: "detail"). 맞는지는 상세에서 판단한다.
 *
 * 숨은 파일 입력(inputs)을 화면 어딘가에 그려야 카메라·앨범이 열린다.
 */
export function useProductLens() {
  const navigate = useNavigate();
  const cameraRef = useRef<HTMLInputElement>(null);
  const albumRef = useRef<HTMLInputElement>(null);
  const [recognizing, setRecognizing] = useState(false);
  const [error, setError] = useState("");
  const nfcSupported = supportsWebNfc();

  async function recognize(file: File) {
    setRecognizing(true);
    setError("");
    try {
      const base64 = await fileToBase64(file);
      const res = await aiRecognizeProduct("IMAGE", base64);
      navigate("/product/recognize", {
        state: {
          result: {
            productId: res.productId ?? "",
            name: res.name ?? "",
            brand: res.brand ?? "",
            imageUrl: null,
          },
          next: "detail",
        },
      });
    } catch {
      setError("사진에서 제품을 찾지 못했어요. 제품 이름이 잘 보이게 다시 찍어주세요.");
    } finally {
      setRecognizing(false);
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
    openNfc: () => navigate("/recommendation/nfc-scan", { state: { next: "detail" } }),
  };
}
