import { Fingerprint, Sparkles } from "lucide-react";

export function MatchingAnimation({
  phase = "analyze",
  paused = false,
}: {
  phase?: "search" | "analyze" | "compose";
  paused?: boolean;
}) {
  return (
    <div
      className={`matching-scene mx-auto phase-${phase}${paused ? " matching-paused" : ""}`}
      aria-hidden="true"
    >
      <div className="matching-halo" />
      <svg className="matching-connections" viewBox="0 0 280 230" fill="none">
        <path
          d="M228 57Q180 52 140 111M140 194V132"
          stroke="#9DBDE9"
          strokeWidth="1.5"
          strokeDasharray="3 6"
        />
        <circle cx="140" cy="111" r="79" stroke="#9DBDE9" strokeOpacity=".2" />
        <circle
          className="matching-ring"
          cx="140"
          cy="111"
          r="61"
          stroke="#9DBDE9"
          strokeOpacity=".3"
        />
      </svg>
      <div className="matching-product matching-product-left">
        <span className="matching-mini-bottle" />
        <i />
        <i />
      </div>
      <div className="matching-product matching-product-right">
        <span className="matching-mini-jar" />
        <i />
        <i />
      </div>
      <div className="matching-main-card">
        <div className="matching-bottle">
          <span />
          <i />
          <b />
        </div>
        <div className="matching-scan" />
        <div className="matching-result-lines">
          <i />
          <i />
        </div>
      </div>
      <span className="matching-node matching-node-skin">
        <Fingerprint strokeWidth={1.7} />
      </span>
      <span className="matching-node matching-node-result">
        <Sparkles strokeWidth={1.7} />
      </span>
      <span className="matching-speck matching-speck-one" />
      <span className="matching-speck matching-speck-two" />
      <div className="matching-ground" />
    </div>
  );
}
