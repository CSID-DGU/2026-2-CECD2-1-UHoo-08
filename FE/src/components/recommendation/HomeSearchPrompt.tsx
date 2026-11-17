import { useEffect, useState } from "react";
import { SearchField } from "../common/SearchField";

const prompts = [
  "제품명이나 궁금한 점을 입력하세요",
  "가성비 좋은 수분크림 어때요?",
  "내 피부에 맞는 쿠션을 찾아볼까요?",
  "이 쿠션, 내 피부에 잘 맞을까요?",
  "5만원으로 스킨·로션을 골라볼까요?",
];

/**
 * 홈 검색창. 여기서 바로 입력하지 않고 누르면 검색 화면으로 간다.
 * 검색 화면에서 최근 검색어와 예시를 함께 보여주기 위해서다.
 */
export function HomeSearchPrompt({ onOpen }: { onOpen: () => void }) {
  const [index, setIndex] = useState(0);
  useEffect(() => {
    const media = window.matchMedia("(prefers-reduced-motion: reduce)");
    let timer: number | undefined;
    const update = () => {
      window.clearInterval(timer);
      if (!media.matches) {
        timer = window.setInterval(() => setIndex(value => (value + 1) % prompts.length), 3500);
      }
    };
    update();
    media.addEventListener("change", update);
    return () => {
      window.clearInterval(timer);
      media.removeEventListener("change", update);
    };
  }, []);
  return <SearchField placeholder={prompts[index]} onClick={onOpen} />;
}
