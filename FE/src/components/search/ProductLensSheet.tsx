import { Camera, ImageIcon, Nfc } from "lucide-react";
import { BottomSheet } from "../common/BottomSheet";

/** 검색창 카메라 버튼을 누르면 뜨는 시트. 사진 찍기, 앨범, NFC 중 하나를 고른다. */
export function ProductLensSheet({
  nfcSupported,
  onCamera,
  onAlbum,
  onNfc,
  onClose,
}: {
  nfcSupported: boolean;
  onCamera: () => void;
  onAlbum: () => void;
  onNfc: () => void;
  onClose: () => void;
}) {
  const options = [
    { label: "사진 찍기", desc: "제품 이름이 보이게 찍어주세요", icon: Camera, onClick: onCamera, disabled: false },
    { label: "앨범에서 고르기", desc: "캡처한 사진도 괜찮아요", icon: ImageIcon, onClick: onAlbum, disabled: false },
    {
      label: "NFC 태그 찍기",
      desc: nfcSupported ? "매장 진열대의 태그에 휴대폰을 대세요" : "안드로이드 크롬에서만 쓸 수 있어요",
      icon: Nfc,
      onClick: onNfc,
      disabled: !nfcSupported,
    },
  ];
  return (
    <BottomSheet label="사진이나 NFC로 제품 찾기" onClose={onClose}>
      <div className="px-5 pb-6 pt-3">
        <div className="flex items-center justify-between">
          <h2 className="text-body1 font-semibold text-slate-800">제품을 찍어서 찾기</h2>
          <button type="button" aria-label="닫기" onClick={onClose} className="h-10 w-10 text-slate-400">
            ×
          </button>
        </div>
        <div className="mt-3 grid gap-2">
          {options.map(({ label, desc, icon: Icon, onClick, disabled }) => (
            <button
              key={label}
              type="button"
              disabled={disabled}
              onClick={() => {
                onClose();
                onClick();
              }}
              className="flex items-center gap-3 rounded-2xl border border-slate-100 p-3.5 text-left disabled:opacity-45"
            >
              <span className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-primary-50 text-primary-600">
                <Icon aria-hidden="true" className="h-5 w-5" />
              </span>
              <span className="min-w-0 flex-1">
                <span className="block text-caption font-semibold text-slate-800">{label}</span>
                <span className="mt-0.5 block text-[11px] text-slate-500">{desc}</span>
              </span>
            </button>
          ))}
        </div>
      </div>
    </BottomSheet>
  );
}
