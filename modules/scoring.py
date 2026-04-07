"""
6業態スコアリングエンジン

商圏データ（人口・競合・駅・地価）を入力として、
居酒屋/カフェ/ラーメン/定食・ファミレス/フレンチ・イタリアン/焼肉
の出店適性スコア（100点満点）を算出する。
"""

from typing import Any, Dict, List, Optional

from modules.scoring_weights import (
    CATEGORY_CUISINE_MAP,
    REFERENCE_VALUES,
    WEIGHTS,
)


def _count_category_competitors(
    competitors: List[Dict[str, Any]],
    category: str,
) -> int:
    """業態に該当する競合店舗数をカウントする。"""
    mapping = CATEGORY_CUISINE_MAP.get(category, {})
    target_amenities = set(mapping.get("amenity", []))
    target_cuisines = set(mapping.get("cuisine", []))

    count = 0
    for c in competitors:
        amenity = c.get("amenity", "")
        cuisine = c.get("cuisine", "").lower()

        if amenity in target_amenities:
            # amenityが一致し、cuisineも部分一致すればカウント
            if not target_cuisines:
                count += 1
            elif any(tc in cuisine for tc in target_cuisines):
                count += 1
            elif not cuisine:
                # cuisine未設定のものはamenityだけで判定
                count += 1
    return count


def _normalize(value: float, reference: float, inverse: bool = False) -> float:
    """
    特徴量を0〜1に正規化する。

    inverse=True の場合、値が小さいほどスコアが高い（駅距離など）。
    """
    if reference <= 0:
        return 0.0
    if inverse:
        # 値が0なら1.0、referenceなら0.0
        return max(0.0, min(1.0, 1.0 - value / reference))
    else:
        return max(0.0, min(1.0, value / reference))


def calculate_scores(
    population: Optional[Dict[str, Any]],
    competitors: List[Dict[str, Any]],
    stations: List[Dict[str, Any]],
    landprice: Optional[Dict[str, Any]],
) -> Dict[str, Dict[str, Any]]:
    """
    6業態の出店適性スコアを算出する。

    Args:
        population: fetch_populationの戻り値
        competitors: fetch_competitorsの戻り値
        stations: fetch_nearest_stationsの戻り値
        landprice: fetch_landpriceの戻り値

    Returns:
        {
            "居酒屋": {
                "score": 78,
                "breakdown": [
                    {"factor": "夜間人口", "value": 5234, "contribution": 25},
                    ...
                ]
            },
            ...
        }
    """
    ref = REFERENCE_VALUES

    # === 特徴量の抽出 ===
    total_pop = population["total_population"] if population else 0
    young_ratio = 0.0
    elderly_ratio = 0.0
    households = 0
    if population and total_pop > 0:
        age = population["age_groups"]
        young_ratio = age["15-64"] / total_pop
        elderly_ratio = age["65+"] / total_pop
        households = population["households"]

    station_distance = stations[0]["distance_m"] if stations else 2000
    total_competitor_count = len(competitors)
    lp_value = landprice["avg_price_per_sqm"] if landprice else None

    # === 各業態のスコア計算 ===
    results: Dict[str, Dict[str, Any]] = {}

    for category, weights in WEIGHTS.items():
        breakdown: List[Dict[str, Any]] = []
        raw_score = 0.0

        # 夜間人口
        w = weights.get("night_population", 0)
        if w != 0:
            norm = _normalize(total_pop, ref["night_population"])
            contrib = round(w * norm)
            breakdown.append({
                "factor": "夜間人口",
                "value": f"{total_pop:,}人",
                "contribution": contrib,
            })
            raw_score += contrib

        # 生産年齢人口比率
        w = weights.get("young_ratio", 0)
        if w != 0:
            norm = _normalize(young_ratio, ref["young_ratio"])
            contrib = round(w * norm)
            breakdown.append({
                "factor": "生産年齢比率",
                "value": f"{young_ratio:.0%}",
                "contribution": contrib,
            })
            raw_score += contrib

        # 高齢者比率
        w = weights.get("elderly_ratio", 0)
        if w != 0:
            if w > 0:
                # 定食・ファミレスなど：高齢者が多いとプラス
                norm = _normalize(elderly_ratio, ref["elderly_ratio"])
                contrib = round(w * norm)
            else:
                # 居酒屋など：高齢者が多いとマイナス
                norm = _normalize(elderly_ratio, ref["elderly_ratio"])
                contrib = round(w * norm)
            breakdown.append({
                "factor": "高齢者比率",
                "value": f"{elderly_ratio:.0%}",
                "contribution": contrib,
            })
            raw_score += contrib

        # 世帯数
        w = weights.get("households", 0)
        if w != 0:
            norm = _normalize(households, ref["households"])
            contrib = round(w * norm)
            breakdown.append({
                "factor": "世帯数",
                "value": f"{households:,}世帯",
                "contribution": contrib,
            })
            raw_score += contrib

        # 駅距離（近いほど高スコア）
        w = weights.get("station_distance", 0)
        if w != 0:
            norm = _normalize(station_distance, ref["station_distance_max"], inverse=True)
            contrib = round(w * norm)
            breakdown.append({
                "factor": "駅近接度",
                "value": f"{station_distance}m",
                "contribution": contrib,
            })
            raw_score += contrib

        # 同業態競合密度（多いほどマイナス）
        w = weights.get("competitor_density", 0)
        if w != 0:
            cat_count = _count_category_competitors(competitors, category)
            norm = _normalize(cat_count, ref["competitor_density_max"])
            contrib = round(w * norm)  # wが負なので自然にマイナスになる
            breakdown.append({
                "factor": "競合密度",
                "value": f"{cat_count}店",
                "contribution": contrib,
            })
            raw_score += contrib

        # 全飲食店数（集客力の指標）
        w = weights.get("total_competitors", 0)
        if w != 0:
            norm = _normalize(total_competitor_count, ref["total_competitors"])
            contrib = round(w * norm)
            breakdown.append({
                "factor": "飲食店集積度",
                "value": f"{total_competitor_count}店",
                "contribution": contrib,
            })
            raw_score += contrib

        # 公示地価（コスト指標）
        w = weights.get("landprice", 0)
        w_positive = weights.get("landprice_positive", 0)
        if lp_value is not None and (w != 0 or w_positive != 0):
            norm = _normalize(lp_value, ref["landprice_max"])
            # コストとしてのマイナス寄与
            if w != 0:
                contrib_cost = round(w * norm)
                raw_score += contrib_cost
            else:
                contrib_cost = 0
            # フレンチ等：高地価=高所得エリアとしてのプラス寄与
            if w_positive != 0:
                contrib_pos = round(w_positive * norm)
                raw_score += contrib_pos
            else:
                contrib_pos = 0
            contrib_total = contrib_cost + contrib_pos
            breakdown.append({
                "factor": "地価水準",
                "value": f"¥{lp_value:,}/㎡",
                "contribution": contrib_total,
            })

        # スコアを0〜100にクランプ
        score = max(0, min(100, round(raw_score)))

        # 寄与度の大きい順にソート
        breakdown.sort(key=lambda x: abs(x["contribution"]), reverse=True)

        results[category] = {
            "score": score,
            "breakdown": breakdown,
        }

    return results
