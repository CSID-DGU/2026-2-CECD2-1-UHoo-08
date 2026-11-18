import { Component, Suspense, lazy, useEffect, useState, type ReactNode } from "react";

/** 로그인 화면과 같은 3D 장면. 홈 히어로 뒤에 깐다. */
const SCENE = "https://prod.spline.design/10xOe1-aIf1GHnfd/scene.splinecode";

// 런타임이 2MB 를 넘어 첫 화면 번들에 넣지 않는다. 필요할 때만 받는다.
const Spline = lazy(() => import("@splinetool/react-spline"));

const REDUCED_MOTION = "(prefers-reduced-motion: reduce)";

function saveData(): boolean {
  const connection = (navigator as Navigator & { connection?: { saveData?: boolean } }).connection;
  return Boolean(connection?.saveData);
}

/**
 * 3D 장면만 감싸는 오류 경계. 장면을 못 받거나 그리다 실패해도 아무것도 그리지 않고 끝내,
 * 오류가 홈 화면 전체로 번지지 않게 한다. 그라데이션은 이 경계 바깥에 있어 그대로 남는다.
 */
class BackdropBoundary extends Component<{ children: ReactNode }, { failed: boolean }> {
  state = { failed: false };

  static getDerivedStateFromError() {
    return { failed: true };
  }

  render() {
    return this.state.failed ? null : this.props.children;
  }
}

/**
 * 히어로 배경.
 *
 * 그라데이션을 먼저 그리고, 홈이 다 뜬 뒤 3D 장면을 받아 그 위에 얹는다. 장면을
 * 못 받거나 가벼운 모드(동작 줄이기, 데이터 절약)면 그라데이션만 남는다.
 * 동작 줄이기는 보는 중에 바뀌어도 따라간다.
 */
export function HeroBackdrop() {
  const [show3d, setShow3d] = useState(false);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    if (saveData()) return;
    const media = window.matchMedia(REDUCED_MOTION);
    const idle = window.requestIdleCallback ?? ((fn: () => void) => window.setTimeout(fn, 800));
    const cancel = window.cancelIdleCallback ?? window.clearTimeout;
    let handle: number | null = null;

    // 홈의 다른 요청(프로필, 환경, 알림)을 먼저 보내고 나서 받는다.
    const schedule = () => {
      if (handle == null) handle = idle(() => setShow3d(true)) as number;
    };
    const update = () => {
      if (media.matches) {
        if (handle != null) cancel(handle);
        handle = null;
        setShow3d(false);
      } else {
        schedule();
      }
    };

    if (!media.matches) schedule();
    media.addEventListener("change", update);
    return () => {
      media.removeEventListener("change", update);
      if (handle != null) cancel(handle);
    };
  }, []);

  return (
    <div aria-hidden="true" className="pointer-events-none absolute inset-0 -z-10 overflow-hidden">
      <div className="absolute inset-0 bg-[linear-gradient(135deg,#9DBDE9_0%,#C5D8F0_100%)]" />
      {show3d && (
        <BackdropBoundary>
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
        </BackdropBoundary>
      )}
      {/* 왼쪽 글자가 장면 위에서도 읽히게 옅은 막을 깐다. */}
      <div className="absolute inset-0 bg-[linear-gradient(90deg,rgba(240,245,253,0.92)_0%,rgba(240,245,253,0.7)_45%,rgba(240,245,253,0)_80%)]" />
    </div>
  );
}
