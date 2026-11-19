"""
product_features.feature_json을 카테고리별 자연어 문장으로 변환.

product_embeddings.feature_vec을 생성하기 위해 사용된다.
리뷰 어휘와 정합성을 맞추기 위해 한국어 자연 표현을 사용한다.
null 필드는 문장에서 자동 제외.

제품 종류는 표준 이름으로 바꿔 적는다(rules/product_types.py). 질의 문장도 표준 이름을
쓰므로 같은 종류가 같은 글자로 들어간다. 경계가 모호한 상품은 종류가 목록이라 둘 다 적는다.
목록에 없는 종류는 그대로 적는다. 비교에는 못 쓰지만 문장 검색에는 도움이 된다.

허용값 (스키마 기준):
  coverage : 가벼운 | 중간 | 높음
  finish   : 매트 | 세미매트 | 글로우 | 촉촉
  skin_type: 건성 | 지성 | 복합 | 민감
  texture  : 가벼운 | 중간 | 진한
  personal_color: 웜톤 | 쿨톤 | 뉴트럴
  lasting_power : 낮음 | 중간 | 높음
  waterproof    : true | false
"""
from typing import Any, Dict, List

from rules.product_types import MAX_TYPES, canonical


def build_product_text(category: str, feature_json: Dict[str, Any]) -> str:
    """카테고리별 자연어 변환 분기."""
    if category == "base":
        return _build_base(feature_json)
    elif category == "sun":
        return _build_sun(feature_json)
    elif category == "lip":
        return _build_lip(feature_json)
    elif category == "skincare":
        return _build_skincare(feature_json)
    elif category == "eye":
        return _build_eye(feature_json)
    elif category == "cheek":
        return _build_cheek(feature_json)
    raise ValueError(f"알 수 없는 카테고리: {category}")


def _종류(f: Dict[str, Any]) -> str:
    """제품 종류 문구. 종류가 여럿이면 쉼표로 잇는다. 예: "립세럼, 틴트" """
    값 = f.get("product_type")
    이름들: List[str] = []
    for 하나 in 값 if isinstance(값, list) else [값]:
        if isinstance(하나, str) and 하나.strip():
            이름 = canonical(하나) or 하나.strip()
            if 이름 not in 이름들:
                이름들.append(이름)
    return ", ".join(이름들[:MAX_TYPES])


def _build_base(f: Dict[str, Any]) -> str:
    parts = []
    종류 = _종류(f)
    if 종류:
        parts.append(f"{종류} 제품")
    if f.get("coverage"):
        parts.append(f"커버력이 {f['coverage']}")
    if f.get("finish"):
        parts.append(f"{f['finish']} 마무리감")
    if f.get("skin_type"):
        parts.append(f"{f['skin_type']} 피부에 적합")
    if f.get("skin_concern"):
        concerns = "·".join(f["skin_concern"])
        parts.append(f"{concerns} 고민에 효과적")
    if f.get("personal_color"):
        parts.append(f"{f['personal_color']}에 어울림")
    if f.get("lasting_power"):
        parts.append(f"지속력 {f['lasting_power']}")
    if f.get("spf"):
        parts.append(f"자외선 차단 {f['spf']}")
    return ". ".join(parts) + "." if parts else ""


def _build_sun(f: Dict[str, Any]) -> str:
    parts = []
    종류 = _종류(f)
    if 종류:
        parts.append(f"{종류} 제품")
    if f.get("spf"):
        parts.append(f"{f['spf']}")
    if f.get("pa"):
        parts.append(f"{f['pa']}")
    if f.get("finish"):
        parts.append(f"{f['finish']} 마무리감")
    if f.get("skin_type"):
        parts.append(f"{f['skin_type']} 피부에 적합")
    if f.get("skin_concern"):
        concerns = "·".join(f["skin_concern"])
        parts.append(f"{concerns}에 도움")
    if f.get("lasting_power"):
        parts.append(f"지속력 {f['lasting_power']}")
    if f.get("white_cast") is not None:
        parts.append(f"백탁 {'있음' if f['white_cast'] else '없음'}")
    return ". ".join(parts) + "." if parts else ""


def _build_lip(f: Dict[str, Any]) -> str:
    parts = []
    종류 = _종류(f)
    if 종류:
        parts.append(f"{종류} 제품")
    if f.get("finish"):
        parts.append(f"{f['finish']} 마무리감")
    if f.get("personal_color"):
        parts.append(f"{f['personal_color']}에 어울림")
    if f.get("lasting_power"):
        parts.append(f"지속력 {f['lasting_power']}")
    if f.get("moisturizing") is not None:
        parts.append(f"보습력 {'있음' if f['moisturizing'] else '없음'}")
    if f.get("skin_concern"):
        concerns = "·".join(f["skin_concern"])
        parts.append(f"{concerns}에 도움")
    return ". ".join(parts) + "." if parts else ""


def _build_skincare(f: Dict[str, Any]) -> str:
    parts = []
    종류 = _종류(f)
    if 종류:
        parts.append(f"{종류} 제품")
    if f.get("texture"):
        parts.append(f"{f['texture']} 제형")
    if f.get("skin_type"):
        parts.append(f"{f['skin_type']} 피부에 적합")
    if f.get("skin_concern"):
        concerns = "·".join(f["skin_concern"])
        parts.append(f"{concerns}에 효과적")
    if f.get("key_ingredient"):
        ings = "·".join(f["key_ingredient"])
        parts.append(f"주요 성분 {ings}")
    if f.get("fragrance_free") is not None:
        parts.append(f"{'무향 제품' if f['fragrance_free'] else '무향 아님'}")
    return ". ".join(parts) + "." if parts else ""


def _build_eye(f: Dict[str, Any]) -> str:
    parts = []
    종류 = _종류(f)
    if 종류:
        parts.append(f"{종류} 제품")
    if f.get("finish"):
        parts.append(f"{f['finish']} 마무리감")
    if f.get("lasting_power"):
        parts.append(f"지속력 {f['lasting_power']}")
    if f.get("waterproof") is not None:
        parts.append(f"{'워터프루프' if f['waterproof'] else '워터프루프 아님'}")
    return ". ".join(parts) + "." if parts else ""


def _build_cheek(f: Dict[str, Any]) -> str:
    parts = []
    종류 = _종류(f)
    if 종류:
        parts.append(f"{종류} 제품")
    if f.get("finish"):
        parts.append(f"{f['finish']} 마무리감")
    if f.get("personal_color"):
        parts.append(f"{f['personal_color']}에 어울림")
    if f.get("lasting_power"):
        parts.append(f"지속력 {f['lasting_power']}")
    return ". ".join(parts) + "." if parts else ""
