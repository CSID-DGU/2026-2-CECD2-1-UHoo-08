/** 사진 파일을 data URL 접두사를 뗀 base64 문자열로 바꾼다. 제품 인식 API 가 이 모양을 받는다. */
export function fileToBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      const result = reader.result as string;
      resolve(result.split(",")[1] ?? result);
    };
    reader.onerror = reject;
    reader.readAsDataURL(file);
  });
}

/** 이 기기 브라우저가 웹 NFC 를 읽을 수 있는지. 지금은 안드로이드 크롬만 된다. */
export function supportsWebNfc(): boolean {
  return typeof window !== "undefined" && "NDEFReader" in window;
}
