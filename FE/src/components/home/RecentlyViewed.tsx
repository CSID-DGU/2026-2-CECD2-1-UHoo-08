import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Package } from "lucide-react";
import { getRecentlyViewed, type ProductSearchItem } from "../../api/productApi";
import { getViewedProducts } from "../../lib/localHistory";

export function RecentlyViewed() {
  const navigate = useNavigate();
  const [items, setItems] = useState<ProductSearchItem[]>(() => getViewedProducts().map(item => ({ ...item, id: item.productId, category: "" })));
  const [state, setState] = useState("loading");
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    let active = true;
    setState("loading");
    getRecentlyViewed(10).then(response => {
      if (active) { setItems(response.data.products); setState("ready"); }
    }).catch(() => { if (active) setState("error"); });
    return () => { active = false; };
  }, [attempt]);
  return <section className="mt-6" aria-labelledby="recently-viewed-title">
    <h2 id="recently-viewed-title" className="text-sm font-semibold text-gray-500">최근 본 상품</h2>
    {items.length > 0 ? <div className="mt-3 flex gap-2 overflow-x-auto pb-2 scrollbar-none">
      {items.map(item => <button type="button" key={item.id} onClick={() => navigate(`/product/${item.id}`)} className="w-[calc((100%-16px)/3)] min-w-[96px] shrink-0 text-left">
        <div className="grid aspect-square place-items-center overflow-hidden rounded-xl border border-[#E5EDF8] bg-[#F0F5FD]">
          {item.imageUrl ? <img src={item.imageUrl} alt="" className="h-full w-full object-contain" /> : <Package className="h-9 w-9 text-[#9DBDE9]" strokeWidth={1.4} />}
        </div>
        <p className="mt-2 line-clamp-2 text-xs font-medium text-gray-500">{item.name}</p>
        <p className="mt-0.5 truncate text-[10px] text-gray-300">{item.brand}</p>
        {item.originalPrice != null && <p className="mt-1 text-xs font-semibold text-gray-500">{item.originalPrice.toLocaleString()}원</p>}
      </button>)}
    </div> : <div className="mt-2 rounded-xl bg-[#F0F5FD] p-4 text-center text-xs text-gray-300">
      <p role="status">{state === "loading" ? "최근 본 상품을 불러오고 있어요" : state === "error" ? "최근 본 상품을 불러오지 못했어요" : "살펴본 상품이 여기에 모여요"}</p>
      {state === "error" && <button type="button" className="mt-2 p-2 text-primary-600" onClick={() => setAttempt(value => value + 1)}>다시 불러오기</button>}
    </div>}
  </section>;
}
