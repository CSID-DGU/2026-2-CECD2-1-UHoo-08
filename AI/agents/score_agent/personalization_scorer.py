"""personalization: userProfile vs feature_json 매칭률."""
from typing import Any, Dict, List, Optional

from rules.product_match import norm_concerns, norm_skin_type, profile_checks


def _norm_skin_type(value: Optional[str]) -> Optional[str]:
    """OILY→지성, DRY→건성, NORMAL→중성, COMBINATION→복합, OILY_DEHYDRATED→복합, SENSITIVE→민감."""
    return norm_skin_type(value)


def _norm_concerns(values: List[str]) -> List[str]:
    """피부고민 영문 → 한글 매핑."""
    return norm_concerns(values)


def compute(
    user_profile: Dict[str, Any],
    feature_json: Optional[Dict[str, Any]],
) -> int:
    """
    feature_json의 personal_color, skin_type, skin_concern과
    userProfile 비교해서 매칭 횟수를 0~100점 매핑.

    feature_json 없으면 50점 중립.
    """
    checks = profile_checks(user_profile, feature_json)
    if not checks:
        return 50

    hits = sum(1 for c in checks if c)
    return round(hits / len(checks) * 100)
