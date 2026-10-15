import { useLocation, useNavigate } from "react-router-dom";

const HomeIcon = ({ active }: { active: boolean }) => (
  <svg fill="none" height="24" viewBox="0 0 24 24" width="24" xmlns="http://www.w3.org/2000/svg">
    <path
      d="M3 9.5L12 3L21 9.5V20C21 20.5523 20.5523 21 20 21H15V15H9V21H4C3.44772 21 3 20.5523 3 20V9.5Z"
      fill={active ? "currentColor" : "none"}
      stroke="currentColor"
      strokeLinecap="round"
      strokeLinejoin="round"
      strokeWidth="1.8"
    />
  </svg>
);

const SearchIcon = ({ active }: { active: boolean }) => (
  <svg fill="none" height="24" viewBox="0 0 24 24" width="24" xmlns="http://www.w3.org/2000/svg">
    <circle
      cx="11"
      cy="11"
      fill={active ? "currentColor" : "none"}
      opacity={active ? 0.2 : 1}
      r="7"
      stroke="currentColor"
      strokeWidth="1.8"
    />
    <path d="M16.5 16.5L21 21" stroke="currentColor" strokeLinecap="round" strokeWidth="1.8" />
  </svg>
);

const UserIcon = ({ active }: { active: boolean }) => (
  <svg fill="none" height="24" viewBox="0 0 24 24" width="24" xmlns="http://www.w3.org/2000/svg">
    <circle
      cx="12"
      cy="8"
      fill={active ? "currentColor" : "none"}
      opacity={active ? 0.3 : 1}
      r="4"
      stroke="currentColor"
      strokeWidth="1.8"
    />
    <path
      d="M4 20C4 16.6863 7.58172 14 12 14C16.4183 14 20 16.6863 20 20"
      stroke="currentColor"
      strokeLinecap="round"
      strokeWidth="1.8"
    />
  </svg>
);

export function BottomNav({ compactSearch = false }: { compactSearch?: boolean }) {
  const navigate = useNavigate();
  const { pathname } = useLocation();

  const homeActive = pathname === "/home";
  const myActive = pathname === "/my";
  const centerActive = pathname.startsWith("/search");

  return (
    <nav aria-label="하단 내비게이션" className="fixed bottom-0 left-1/2 z-40 grid min-h-[72px] w-full max-w-[430px] -translate-x-1/2 grid-cols-3 items-center border-t border-gray-200 bg-white px-4 shadow-[0_-2px_12px_rgba(0,0,0,0.04)]" style={{ paddingBottom: "env(safe-area-inset-bottom, 0px)", height: "calc(72px + env(safe-area-inset-bottom, 0px))" }}>
      <button
        className={`mx-auto flex flex-col items-center gap-1 ${homeActive ? "text-primary-500" : "text-gray-300"}`}
        onClick={() => navigate("/home")}
        type="button"
      >
        <HomeIcon active={homeActive} />
        <span className="text-[10px] leading-none">홈</span>
      </button>

      <button
        className={compactSearch ? "mx-auto flex flex-col items-center gap-1 text-primary-600" : `mx-auto grid h-14 w-14 cursor-pointer place-items-center rounded-full ${centerActive ? "bg-primary-600" : "bg-primary-500"} text-white`}
        onClick={() => navigate("/search")}
        type="button"
        aria-label="제품 검색과 질문"
      >
        {compactSearch ? <><span className="grid h-[42px] w-[42px] place-items-center rounded-full bg-[#9DBDE9] text-[#203D66]"><SearchIcon active={false} /></span><span className="text-[10px] leading-none">검색</span></> : <SearchIcon active={false} />}
      </button>

      <button
        className={`mx-auto flex flex-col items-center gap-1 ${myActive ? "text-primary-500" : "text-gray-300"}`}
        onClick={() => navigate("/my")}
        type="button"
      >
        <UserIcon active={myActive} />
        <span className="text-[10px] leading-none">마이페이지</span>
      </button>
    </nav>
  );
}
