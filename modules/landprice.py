"""
公示地価取得モジュール: 不動産情報ライブラリAPI (XPT002)

国土交通省の不動産情報ライブラリAPIから、指定地点周辺の
公示地価ポイントを取得し、最寄り3点の平均㎡単価を返す。

APIキーは https://www.reinfolib.mlit.go.jp/api/request/ から申請（無料）。
"""

import math
import os
import re
from typing import Any, Dict, List, Optional

import requests
from dotenv import load_dotenv

load_dotenv()

LANDPRICE_API_URL = "https://www.reinfolib.mlit.go.jp/ex-api/external/XPT002"

def _get_reinfolib_api_key() -> str:
    """環境変数 → st.secrets の順でAPIキーを取得する。毎回呼び出し時に評価。"""
    val = os.getenv("REINFOLIB_API_KEY", "")
    if val:
        return val
    try:
        import streamlit as st
        return st.secrets.get("REINFOLIB_API_KEY", "")
    except Exception:
        return ""


def _latlon_to_tile(lat: float, lng: float, zoom: int) -> tuple[int, int]:
    """緯度経度をXYZタイル座標に変換する。"""
    n = 2 ** zoom
    x = int((lng + 180.0) / 360.0 * n)
    lat_rad = math.radians(lat)
    y = int((1.0 - math.log(math.tan(lat_rad) + 1.0 / math.cos(lat_rad)) / math.pi) / 2.0 * n)
    return x, y


def _haversine(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """2点間の距離（メートル）をHaversine公式で計算する。"""
    R = 6371000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _parse_price(price_str: str) -> Optional[int]:
    """地価文字列から数値を抽出する。例: '3,100,000(円/㎡)' → 3100000"""
    if not price_str:
        return None
    digits = re.sub(r"[^\d]", "", price_str)
    if digits:
        return int(digits)
    return None


def fetch_landprice(
    lat: float,
    lng: float,
    top_n: int = 3,
) -> Optional[Dict[str, Any]]:
    """
    指定地点周辺の公示地価を取得する。

    最寄りtop_n地点の㎡単価平均と各ポイントの詳細を返す。

    Args:
        lat: 緯度
        lng: 経度
        top_n: 使用する最寄りポイント数（デフォルト3）

    Returns:
        {
            "avg_price_per_sqm": int,  # 平均㎡単価（円）
            "points": [
                {
                    "price_per_sqm": int,
                    "address": str,
                    "use_category": str,
                    "distance_m": int,
                },
                ...
            ],
        }
        APIキー未設定またはデータなしの場合はNone。
    """
    api_key = _get_reinfolib_api_key()
    if not api_key:
        print("[landprice] REINFOLIB_API_KEYが設定されていません")
        return None

    # zoom=14で周辺タイルを取得（1タイル≈約1km四方）
    zoom = 14
    cx, cy = _latlon_to_tile(lat, lng, zoom)

    all_points: List[Dict[str, Any]] = []

    # 中心タイルとその周囲8タイル（3x3）を検索
    for dx in range(-1, 2):
        for dy in range(-1, 2):
            tx, ty = cx + dx, cy + dy
            params = {
                "response_format": "geojson",
                "z": zoom,
                "x": tx,
                "y": ty,
                "year": "2025",
                "priceClassification": "0",  # 地価公示のみ
            }
            headers = {
                "Ocp-Apim-Subscription-Key": api_key,
            }

            try:
                resp = requests.get(
                    LANDPRICE_API_URL,
                    params=params,
                    headers=headers,
                    timeout=15,
                )
                resp.raise_for_status()
                data = resp.json()
            except (requests.RequestException, ValueError) as e:
                print(f"[landprice] APIエラー (tile {tx},{ty}): {e}")
                continue

            features = data.get("features", [])
            for f in features:
                props = f.get("properties", {})
                geom = f.get("geometry", {})
                coords = geom.get("coordinates", [])
                if len(coords) < 2:
                    continue

                p_lng, p_lat = coords[0], coords[1]
                price = _parse_price(props.get("u_current_years_price_ja", ""))
                if price is None:
                    continue

                distance = _haversine(lat, lng, p_lat, p_lng)
                all_points.append({
                    "price_per_sqm": price,
                    "address": props.get("u_station_name_ja", ""),
                    "use_category": props.get("u_use_category_ja", ""),
                    "distance_m": round(distance),
                    "lat": p_lat,
                    "lng": p_lng,
                })

    if not all_points:
        return None

    # 距離順ソートして上位N件
    all_points.sort(key=lambda x: x["distance_m"])
    closest = all_points[:top_n]

    avg_price = sum(p["price_per_sqm"] for p in closest) // len(closest)

    return {
        "avg_price_per_sqm": avg_price,
        "points": closest,
    }
