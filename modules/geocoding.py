"""
ジオコーディング: 住所 -> 緯度経度

国土地理院のジオコーディングAPIを使用（APIキー不要・無料）
https://msearch.gsi.go.jp/address-search/AddressSearch?q={address}
"""

import requests
from typing import Optional, Tuple


GEOCODE_URL = "https://msearch.gsi.go.jp/address-search/AddressSearch"


def geocode(address: str) -> Optional[Tuple[float, float, str]]:
    """
    住所文字列を緯度経度に変換する。

    Args:
        address: 住所文字列（例: "東京都千代田区丸の内1丁目"）

    Returns:
        (latitude, longitude, matched_title) のタプル。
        見つからなかった場合は None。
    """
    try:
        resp = requests.get(
            GEOCODE_URL,
            params={"q": address},
            timeout=10,
        )
        resp.raise_for_status()
        results = resp.json()

        if not results:
            return None

        # 最初のヒットを採用
        first = results[0]
        lng, lat = first["geometry"]["coordinates"]
        title = first["properties"].get("title", address)
        return (float(lat), float(lng), title)

    except (requests.RequestException, ValueError, KeyError, IndexError) as e:
        print(f"[geocoding] エラー: {e}")
        return None
