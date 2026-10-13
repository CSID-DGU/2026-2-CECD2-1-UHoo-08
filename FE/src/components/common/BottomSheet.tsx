import { useEffect, useRef, type ReactNode } from "react";

/** 네이티브 dialog로 포커스 제한·Escape 닫기를 함께 처리한다. */
export function BottomSheet({
  label,
  onClose,
  children,
}: {
  label: string;
  onClose: () => void;
  children: ReactNode;
}) {
  const dialog = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const element = dialog.current;
    const overflow = document.body.style.overflow;
    element?.showModal();
    document.body.style.overflow = "hidden";
    return () => {
      element?.close();
      document.body.style.overflow = overflow;
    };
  }, []);
  return (
    <dialog
      ref={dialog}
      aria-label={label}
      onCancel={onClose}
      onClick={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
      className="fixed inset-x-0 bottom-0 top-auto m-0 mx-auto max-h-[90dvh] w-full max-w-[430px] overflow-y-auto rounded-t-3xl border-0 bg-white p-0 text-gray-500 backdrop:bg-black/40"
    >
      <div className="mx-auto mb-2 mt-3 h-1 w-10 rounded-full bg-gray-200" />
      {children}
    </dialog>
  );
}
