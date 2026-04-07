"""
最寄り駅検索: OpenStreetMap (Overpass API)

指定地点から近い鉄道駅を取得し、距離順でソートして返す。
国土数値情報のダウンロードが不要な、APIベースの実装。
"""

import math
import time
from typing import Any, Dict, List, Optional

import requests


# メインサーバーが混雑時に代替サーバーへフォールバック
OVERPASS_URLS = [
    "https://overpass-api.de/api/interpreter",
    "https://lz4.overpass-api.de/api/interpreter",
    "https://z.overpass-api.de/api/interpreter",
]


def _haversine(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """2点間の距離（メートル）をHaversine公式で計算する。"""
    R = 6371000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def fetch_nearest_stations(
    lat: float,
    lng: float,
    search_radius_m: int = 2000,
    top_n: int = 3,
) -> List[Dict[str, Any]]:
    """
    指定地点から最も近い鉄道駅をTOP N件取得する。

    同名駅（複数路線）は最も近い1件にまとめ、路線情報を統合する。

    Args:
        lat: 緯度
        lng: 経度
        search_radius_m: 検索半径（メートル）。デフォルト2000m。
        top_n: 返す駅数。デフォルト3。

    Returns:
        各駅のdict（name, distance_m, lat, lng, operator, lines）のリスト。
        距離昇順でソート済み。取得失敗時は空リスト。
    """
    query = f"""
    [out:json][timeout:25];
    (
      node["railway"="station"](around:{search_radius_m},{lat},{lng});
      node["railway"="halt"](around:{search_radius_m},{lat},{lng});
    );
    out body;
    """

    data = None
    for attempt in range(2):
        for url in OVERPASS_URLS:
            try:
                resp = requests.post(url, data={"data": query}, timeout=60)
                resp.raise_for_status()
                data = resp.json()
                break
            except (requests.RequestException, ValueError) as e:
                print(f"[stations] {url} エラー (試行{attempt+1}): {e}")
                time.sleep(2)
                continue
        if data is not None:
            break

    if data is None:
        print("[stations] 全サーバーで取得失敗")
        return []

    # 各駅ノードを処理
    raw_stations = []
    for el in data.get("elements", []):
        tags = el.get("tags", {})
        name = tags.get("name", "")
        if not name:
            continue

        s_lat = el.get("lat")
        s_lng = el.get("lon")
        if s_lat is None or s_lng is None:
            continue

        distance = _haversine(lat, lng, s_lat, s_lng)
        operator = tags.get("operator", "")
        line = tags.get("railway:line", "") or tags.get("line", "")

        raw_stations.append({
            "name": name,
            "lat": s_lat,
            "lng": s_lng,
            "distance_m": round(distance),
            "operator": operator,
            "line": line,
        })

    # 同名駅を統合（最も近い位置を採用、事業者・路線をまとめる）
    merged: Dict[str, Dict[str, Any]] = {}
    for s in raw_stations:
        name = s["name"]
        if name not in merged or s["distance_m"] < merged[name]["distance_m"]:
            merged[name] = {
                "name": name,
                "lat": s["lat"],
                "lng": s["lng"],
                "distance_m": s["distance_m"],
                "operators": set(),
                "lines": set(),
            }
        if s["operator"]:
            # 「;」区切りの複数事業者を分割
            for op in s["operator"].split(";"):
                merged[name]["operators"].add(op.strip())
        if s["line"]:
            for ln in s["line"].split(";"):
                merged[name]["lines"].add(ln.strip())

    # setをリストに変換し、距離順でソート
    results = []
    for s in merged.values():
        results.append({
            "name": s["name"],
            "lat": s["lat"],
            "lng": s["lng"],
            "distance_m": s["distance_m"],
            "operator": "／".join(sorted(s["operators"])) if s["operators"] else "不明",
            "lines": "／".join(sorted(s["lines"])) if s["lines"] else "",
        })

    results.sort(key=lambda x: x["distance_m"])
    return results[:top_n]
