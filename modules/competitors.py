"""
競合店舗取得: OpenStreetMap (Overpass API)

APIキー不要・無料。
amenityタグで飲食店を絞り込み、cuisineタグで業態分類する。
"""

import requests
from typing import List, Dict, Any


# メインサーバーが混雑時に代替サーバーへフォールバック
OVERPASS_URLS = [
    "https://overpass-api.de/api/interpreter",
    "https://lz4.overpass-api.de/api/interpreter",
    "https://z.overpass-api.de/api/interpreter",
]

# OSMのamenityタグ -> 日本語業態カテゴリ
AMENITY_LABELS = {
    "restaurant": "レストラン",
    "cafe": "カフェ",
    "fast_food": "ファストフード",
    "bar": "バー",
    "pub": "パブ",
    "food_court": "フードコート",
}


def fetch_competitors(lat: float, lng: float, radius_m: int = 1000) -> List[Dict[str, Any]]:
    """
    指定地点の半径radius_m以内にある飲食店を取得する。

    Args:
        lat: 緯度
        lng: 経度
        radius_m: 検索半径(メートル)

    Returns:
        各店舗のdict（name, lat, lng, amenity, cuisine, label）のリスト
    """
    amenities = "|".join(AMENITY_LABELS.keys())
    query = f"""
    [out:json][timeout:25];
    (
      node["amenity"~"^({amenities})$"](around:{radius_m},{lat},{lng});
      way["amenity"~"^({amenities})$"](around:{radius_m},{lat},{lng});
    );
    out center body;
    """

    data = None
    for url in OVERPASS_URLS:
        try:
            resp = requests.post(url, data={"data": query}, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            break
        except (requests.RequestException, ValueError) as e:
            print(f"[competitors] {url} エラー: {e}")
            continue

    if data is None:
        print("[competitors] 全サーバーで取得失敗")
        return []

    results = []
    for el in data.get("elements", []):
        # nodeはlat/lon直接、wayはcenterから取得
        if el["type"] == "node":
            p_lat, p_lng = el.get("lat"), el.get("lon")
        else:
            center = el.get("center", {})
            p_lat, p_lng = center.get("lat"), center.get("lon")

        if p_lat is None or p_lng is None:
            continue

        tags = el.get("tags", {})
        amenity = tags.get("amenity", "")
        results.append({
            "name": tags.get("name", "（名称不明）"),
            "lat": p_lat,
            "lng": p_lng,
            "amenity": amenity,
            "cuisine": tags.get("cuisine", ""),
            "label": AMENITY_LABELS.get(amenity, amenity),
        })

    return results


def summarize_by_category(competitors: List[Dict[str, Any]]) -> Dict[str, int]:
    """業態カテゴリごとの件数を集計する。"""
    counts: Dict[str, int] = {}
    for c in competitors:
        label = c["label"]
        counts[label] = counts.get(label, 0) + 1
    return dict(sorted(counts.items(), key=lambda x: x[1], reverse=True))
