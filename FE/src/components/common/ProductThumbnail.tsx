type ProductThumbnailProps = {
  className?: string;
  green?: boolean;
  size?: "sm" | "md" | "lg" | "wide";
  shape?: "bottle" | "cushion" | "triple";
};

const sizeClass = {
  sm: "h-10 w-10",
  md: "h-11 w-11",
  lg: "h-14 w-14",
  wide: "h-[68px] w-[108px]",
};

export function ProductThumbnail({
  className = "",
  green = false,
  size = "md",
  shape,
}: ProductThumbnailProps) {
  if (shape) {
    const bottle = (key: number) => (
      <div key={key} className="flex flex-col items-center">
        <span className="h-3 w-3 rounded-t-sm bg-primary-300" />
        <span className="flex h-16 w-7 items-center justify-center rounded-md border border-primary-100 bg-white">
          <span className="h-4 w-4 rounded-sm bg-primary-100" />
        </span>
      </div>
    );
    return (
      <div
        aria-hidden="true"
        className={`flex items-center justify-center rounded-xl bg-primary-50 ${className}`}
      >
        {shape === "cushion" ? (
          <div className="flex flex-col items-center">
            <span className="mb-1 h-2 w-5 rounded-sm bg-primary-300" />
            <span className="grid h-20 w-20 place-items-center rounded-full border-[6px] border-primary-100 bg-white">
              <span className="h-14 w-14 rounded-full border-[5px] border-primary-50" />
            </span>
          </div>
        ) : (
          <div className="flex items-center gap-2">
            {shape === "triple" ? [0, 1, 2].map(bottle) : bottle(0)}
          </div>
        )}
      </div>
    );
  }
  return (
    <div
      className={`flex items-center justify-center rounded-xl bg-gray-100 ${className}`}
    >
      <div
        className={`rounded-md ${green ? "bg-primary-100" : "bg-gray-200"} ${sizeClass[size]}`}
      />
    </div>
  );
}
