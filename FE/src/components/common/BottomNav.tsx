import { useLocation, useNavigate } from "react-router-dom";
import { House, Search, User } from "lucide-react";

export function BottomNav({ compactSearch = false }: { compactSearch?: boolean }) {
  const navigate = useNavigate();
  const { pathname } = useLocation();

  const homeActive = pathname === "/home";
  const myActive = pathname === "/my";
  const centerActive = pathname.startsWith("/search");

  return (
    <nav aria-label="하단 내비게이션" className="fixed bottom-0 left-1/2 z-40 grid min-h-[72px] w-full max-w-[430px] -translate-x-1/2 grid-cols-3 items-center border-t border-gray-200 bg-white px-4 shadow-nav" style={{ paddingBottom: "env(safe-area-inset-bottom, 0px)", height: "calc(72px + env(safe-area-inset-bottom, 0px))" }}>
      <button
        className={`mx-auto flex flex-col items-center gap-1 ${homeActive ? "text-primary-500" : "text-gray-300"}`}
        onClick={() => navigate("/home")}
        type="button"
      >
        <House aria-hidden="true" className="h-6 w-6" strokeWidth={1.8} fill={homeActive ? "currentColor" : "none"} />
        <span className="text-[11px] leading-none">홈</span>
      </button>

      <button
        className={compactSearch ? "mx-auto flex flex-col items-center gap-1 text-primary-600" : `mx-auto grid h-14 w-14 cursor-pointer place-items-center rounded-full ${centerActive ? "bg-primary-600" : "bg-primary-500"} text-white`}
        onClick={() => navigate("/search")}
        type="button"
        aria-label="제품 검색과 질문"
      >
        {compactSearch ? <><span className="grid h-[42px] w-[42px] place-items-center rounded-full bg-primary-200 text-primary-900"><Search aria-hidden="true" className="h-6 w-6" strokeWidth={1.8} /></span><span className="text-[11px] leading-none">검색</span></> : <Search aria-hidden="true" className="h-6 w-6" strokeWidth={1.8} />}
      </button>

      <button
        className={`mx-auto flex flex-col items-center gap-1 ${myActive ? "text-primary-500" : "text-gray-300"}`}
        onClick={() => navigate("/my")}
        type="button"
      >
        <User aria-hidden="true" className="h-6 w-6" strokeWidth={1.8} fill={myActive ? "currentColor" : "none"} />
        <span className="text-[11px] leading-none">마이페이지</span>
      </button>
    </nav>
  );
}
