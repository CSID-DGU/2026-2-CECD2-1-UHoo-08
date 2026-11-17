import { Suspense, lazy, useEffect, useState } from "react";

/** 로그인 화면과 같은 3D 장면. 홈 히어로 뒤에 깐다. */
const SCENE = "https://prod.spline.design/10xOe1-aIf1GHnfd/scene.splinecode";

// 런타임이 2MB 를 넘어 첫 화면 번들에 넣지 않는다. 필요할 때만 받는다.
const Spline = lazy(() => import("@splinetool/react-spline"));

/** 데이터 절약 모드나 동작 줄이기를 켠 사용자에게는 3D 를 띄우지 않는다. */
function prefersLite(): boolean {
  const connection = (navigator as Navigator & { connection?: { saveData?: boolean } }).connection;
  return (
    window.matchMedia("(prefers-reduced-motion: reduce)").matches ||
    Boolean(connection?.saveData)
  );
}

/**
 * 히어로 배경.
 *
 * 그라데이션을 먼저 그리고, 홈이 다 뜬 뒤 3D 장면을 받아 그 위에 얹는다. 장면을
 * 못 받거나 가벼운 모드면 그라데이션만 남는다. 어느 쪽이든 글자는 그 위에 있다.
 */
export function HeroBackdrop() {
  const [show3d, setShow3d] = useState(false);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    if (prefersLite()) return;
    // 홈의 다른 요청(프로필, 환경, 알림)을 먼저 보내고 나서 받는다.
    const idle = window.requestIdleCallback ?? ((fn: () => void) => window.setTimeout(fn, 800));
    const cancel = window.cancelIdleCallback ?? window.clearTimeout;
    const handle = idle(() => setShow3d(true));
    return () => cancel(handle as number);
  }, []);

  return (
    <div aria-hidden="true" className="pointer-events-none absolute inset-0 -z-10 overflow-hidden">
      <div className="absolute inset-0 bg-[linear-gradient(135deg,#9DBDE9_0%,#C5D8F0_100%)]" />
      {show3d && (
        <Suspense fallback={null}>
          <Spline
            scene={SCENE}
            onLoad={() => setLoaded(true)}
            style={{
              position: "absolute",
              top: 0,
              left: 0,
              width: "100%",
              // 장면 아래쪽 로고가 보이지 않게 영역 밖으로 조금 내린다(로그인 화면과 같은 방법).
              height: "calc(100% + 60px)",
              opacity: loaded ? 1 : 0,
              transition: "opacity 800ms ease",
            }}
          />
        </Suspense>
      )}
      {/* 왼쪽 글자가 장면 위에서도 읽히게 옅은 막을 깐다. */}
      <div className="absolute inset-0 bg-[linear-gradient(90deg,rgba(240,245,253,0.92)_0%,rgba(240,245,253,0.7)_45%,rgba(240,245,253,0)_80%)]" />
    </div>
  );
}
