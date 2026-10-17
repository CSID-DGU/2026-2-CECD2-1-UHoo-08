import { useState } from "react";

import { Search } from "lucide-react";

type SearchFieldProps = {
  className?: string;
  value?: string;
  placeholder?: string;
  editable?: boolean;
  variant?: "filled" | "outlined";
  onClick?: () => void;
  onClear?: () => void;
  onSubmit?: (value: string) => void;
  onChange?: (value: string) => void;
};

export function SearchField({
  className = "",
  editable = false,
  onClear,
  onClick,
  onSubmit,
  onChange,
  placeholder,
  value = "",
  variant = "filled",
}: SearchFieldProps) {
  const [inputValue, setInputValue] = useState(value);

  const colorClass =
    variant === "outlined"
      ? "border border-primary-500 bg-primary-50"
      : "bg-primary-50 border border-primary-300 focus-within:border-primary-600 focus-within:ring-2 focus-within:ring-primary-100";

  const SearchIcon = (
    <Search aria-hidden="true" className="h-5 w-5 shrink-0 text-primary-700" strokeWidth={2} />
  );

  if (editable) {
    return (
      <div className={`flex h-12 w-full items-center gap-3 rounded-xl px-4 ${colorClass} ${className}`}>
        <input
          aria-label="화장품 검색"
          className="min-w-0 flex-1 bg-transparent text-body2 font-medium text-gray-500 outline-none placeholder:text-gray-400"
          onChange={(e) => { setInputValue(e.target.value); onChange?.(e.target.value); }}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.nativeEvent.isComposing && inputValue.trim() && onSubmit) {
              e.preventDefault();
              onSubmit(inputValue.trim());
            }
          }}
          placeholder={placeholder}
          value={inputValue}
        />
        {inputValue && (
          <button
            type="button"
            aria-label="검색어 지우기"
            className="grid h-6 w-6 shrink-0 cursor-pointer place-items-center rounded-full bg-gray-200 text-gray-300"
            onClick={() => { setInputValue(""); onChange?.(""); }}
          >
            ×
          </button>
        )}
        <button type="button" aria-label="검색하기" onClick={() => { if (inputValue.trim()) onSubmit?.(inputValue.trim()); }} className="grid h-7 w-7 shrink-0 place-items-center">
          {SearchIcon}
        </button>
      </div>
    );
  }

  return (
    <button
      className={`flex h-12 w-full items-center gap-3 rounded-xl px-4 text-left text-body2 ${colorClass}`}
      onClick={onClick}
      type="button"
    >
      <span key={placeholder || value} className="min-w-0 flex-1 truncate text-gray-400 motion-safe:animate-[fadeInUp_0.3s_ease]">
        {placeholder || value}
      </span>
      {onClear && (
        <span
          className="grid h-6 w-6 shrink-0 place-items-center rounded-full bg-gray-200 text-gray-300"
          onClick={(e) => {
            e.stopPropagation();
            onClear();
          }}
          role="button"
          tabIndex={0}
        >
          ×
        </span>
      )}
      {SearchIcon}
    </button>
  );
}
