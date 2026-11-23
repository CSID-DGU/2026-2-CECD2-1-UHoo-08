import { useNavigate } from "react-router-dom";
import { Heart } from "lucide-react";

interface WishlistButtonProps {
  className?: string;
  style?: React.CSSProperties;
  iconColor?: string;
}

export function WishlistButton({
  className,
  style,
  iconColor = "white",
}: WishlistButtonProps) {
  const navigate = useNavigate();
  return (
    <button
      className={`relative flex h-10 w-10 items-center justify-center rounded-full ${className ?? ""}`}
      style={style}
      onClick={() => navigate("/wishlist")}
      type="button"
      aria-label="찜한 제품"
    >
      <Heart aria-hidden="true" className="h-5 w-5" color={iconColor} strokeWidth={1.8} />
    </button>
  );
}
