"""
e-Stat 500mメッシュ統計モジュール

2020年国勢調査の500mメッシュ（2分の1地域メッシュ）データを
e-Stat APIから取得し、商圏内の人口・世帯情報を集計する。
"""

import math
import os
import sqlite3
import time
from typing import Any, Dict, List, Optional, Tuple

import requests
from dotenv import load_dotenv

load_dotenv()

ESTAT_API_URL = "https://api.e-stat.go.jp/rest/3.0/app/json/getStatsData"

def _get_estat_app_id() -> str:
    """環境変数 → st.secrets の順でAPIキーを取得する。毎回呼び出し時に評価。"""
    val = os.getenv("ESTAT_APP_ID", "")
    if val:
        return val
    try:
        import streamlit as st
        return st.secrets.get("ESTAT_APP_ID", "")
    except Exception:
        return ""

# 1次メッシュコード → 500mメッシュ統計テーブルID（2020年国勢調査）
# getStatsListから取得した全国151メッシュ分のマッピング
PRIMARY_MESH_TO_TABLE: Dict[str, str] = {
    "3622": "8003007448", "3623": "8003007340", "3624": "8003007447",
    "3653": "8003007508", "3724": "8003007459", "3725": "8003007341",
    "3741": "8003007590", "3831": "8003007426", "3926": "8003007320",
    "3927": "8003007460", "3928": "8003007418", "3942": "8003007358",
    "4027": "8003007411", "4028": "8003007427", "4042": "8003007384",
    "4128": "8003007329", "4129": "8003007428", "4229": "8003007330",
    "4230": "8003007331", "4329": "8003007439", "4429": "8003007359",
    "4530": "8003007380", "4531": "8003007395", "4629": "8003007461",
    "4630": "8003007396", "4631": "8003007420", "4729": "8003007360",
    "4730": "8003007419", "4731": "8003007421", "4828": "8003007412",
    "4829": "8003007429", "4830": "8003007449", "4831": "8003007422",
    "4839": "8003007348", "4928": "8003007405", "4929": "8003007385",
    "4930": "8003007462", "4931": "8003007397", "4932": "8003007423",
    "4933": "8003007369", "4934": "8003007349", "4939": "8003007343",
    "5029": "8003007342", "5030": "8003007321", "5031": "8003007398",
    "5032": "8003007413", "5033": "8003007399", "5034": "8003007450",
    "5035": "8003007361", "5036": "8003007463", "5039": "8003007441",
    "5129": "8003007430", "5130": "8003007440", "5131": "8003007322",
    "5132": "8003007431", "5133": "8003007464", "5134": "8003007370",
    "5135": "8003007386", "5136": "8003007424", "5137": "8003007332",
    "5138": "8003007371", "5139": "8003007432", "5229": "8003007451",
    "5231": "8003007400", "5232": "8003007350", "5233": "8003007323",
    "5234": "8003007351", "5235": "8003007433", "5236": "8003007324",
    "5237": "8003007401", "5238": "8003007387", "5239": "8003007372",
    "5240": "8003007344", "5332": "8003007414", "5333": "8003007352",
    "5334": "8003007362", "5335": "8003007406", "5336": "8003007434",
    "5337": "8003007435", "5338": "8003007353", "5339": "8003007402",
    "5340": "8003007442", "5432": "8003007381", "5433": "8003007373",
    "5435": "8003007407", "5436": "8003007452", "5437": "8003007333",
    "5438": "8003007334", "5439": "8003007325", "5440": "8003007374",
    "5536": "8003007388", "5537": "8003007425", "5538": "8003007382",
    "5539": "8003007443", "5540": "8003007335", "5541": "8003007354",
    "5636": "8003007444", "5637": "8003007363", "5638": "8003007389",
    "5639": "8003007465", "5640": "8003007466", "5641": "8003007376",
    "5738": "8003007390", "5739": "8003007375", "5740": "8003007355",
    "5741": "8003007364", "5839": "8003007365", "5840": "8003007469",
    "5841": "8003007377", "5939": "8003007408", "5940": "8003007336",
    "5941": "8003007467", "5942": "8003007345", "6039": "8003007415",
    "6040": "8003007409", "6041": "8003007391", "6139": "8003007454",
    "6140": "8003007356", "6141": "8003007453", "6239": "8003007416",
    "6240": "8003007457", "6241": "8003007378", "6243": "8003007326",
    "6339": "8003007403", "6340": "8003007458", "6341": "8003007455",
    "6342": "8003007456", "6343": "8003007346", "6439": "8003007337",
    "6440": "8003007468", "6441": "8003007366", "6442": "8003007438",
    "6443": "8003007445", "6444": "8003007393", "6445": "8003007394",
    "6540": "8003007446", "6541": "8003007436", "6542": "8003007357",
    "6543": "8003007392", "6544": "8003007410", "6545": "8003007417",
    "6641": "8003007338", "6642": "8003007379", "6643": "8003007437",
    "6644": "8003007347", "6645": "8003007327", "6741": "8003007367",
    "6742": "8003007368", "6840": "8003007339", "6841": "8003007470",
    "6842": "8003007383",
}

# e-Stat APIの分類コード → 使用するカテゴリ
# 総数のみ取得（男女別は0020/0030で取得）
CAT_CODES = {
    "0010": "population_total",     # 人口（総数）
    "0020": "population_male",      # 人口　男
    "0030": "population_female",    # 人口　女
    "0040": "age_0_14",             # 0〜14歳人口
    "0050": "age_0_14_male",        # 0〜14歳　男
    "0060": "age_0_14_female",      # 0〜14歳　女
    "0100": "age_15_64",            # 15〜64歳人口
    "0110": "age_15_64_male",       # 15〜64歳　男
    "0120": "age_15_64_female",     # 15〜64歳　女
    "0190": "age_65_over",          # 65歳以上人口
    "0200": "age_65_over_male",     # 65歳以上　男
    "0210": "age_65_over_female",   # 65歳以上　女
    "0220": "age_75_over",          # 75歳以上人口
    "0230": "age_75_over_male",     # 75歳以上　男
    "0240": "age_75_over_female",   # 75歳以上　女
    "0340": "households",           # 世帯総数
    "0360": "single_households",    # 1人世帯数
}

# SQLiteキャッシュ設定
CACHE_DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "cache", "estat_cache.db")


# ============================================================
# メッシュコード計算
# ============================================================

def _latlon_to_primary_mesh(lat: float, lng: float) -> str:
    """緯度経度から1次メッシュコード（4桁）を算出する。"""
    p = int(lat * 60 / 40)
    u = int(lng - 100)
    return f"{p:02d}{u:02d}"


def _latlon_to_secondary_mesh(lat: float, lng: float) -> str:
    """緯度経度から2次メッシュコード（6桁）を算出する。"""
    p1 = int(lat * 60 / 40)
    u1 = int(lng - 100)
    lat_rem = lat * 60 - p1 * 40
    lng_rem = (lng - 100) - u1
    p2 = int(lat_rem / 5)
    u2 = int(lng_rem * 8)
    return f"{p1:02d}{u1:02d}{p2}{u2}"


def _latlon_to_third_mesh(lat: float, lng: float) -> str:
    """緯度経度から3次メッシュコード（8桁）を算出する。"""
    p1 = int(lat * 60 / 40)
    u1 = int(lng - 100)
    lat_rem = lat * 60 - p1 * 40
    lng_rem = (lng - 100) - u1
    p2 = int(lat_rem / 5)
    u2 = int(lng_rem * 8)
    lat_rem2 = lat_rem - p2 * 5
    lng_rem2 = lng_rem - u2 * 0.125
    p3 = int(lat_rem2 / 0.5)
    u3 = int(lng_rem2 / 0.0125)
    return f"{p1:02d}{u1:02d}{p2}{u2}{p3}{u3}"


def _latlon_to_half_mesh(lat: float, lng: float) -> str:
    """
    緯度経度から500mメッシュコード（9桁、2分の1地域メッシュ）を算出する。

    3次メッシュを南北・東西に2分割し、1〜4の番号を付与する。
    1=南西, 2=南東, 3=北西, 4=北東
    """
    third = _latlon_to_third_mesh(lat, lng)

    # 3次メッシュの南端・西端の緯度経度
    p1 = int(third[0:2])
    u1 = int(third[2:4])
    p2 = int(third[4])
    u2 = int(third[5])
    p3 = int(third[6])
    u3 = int(third[7])

    lat_base = (p1 * 40 + p2 * 5 + p3 * 0.5) / 60
    lng_base = u1 + 100 + u2 * 0.125 + u3 * 0.0125

    # 3次メッシュ内での相対位置
    lat_half = 0.5 / 60 / 2  # 3次メッシュ高さの半分
    lng_half = 0.0125 / 2     # 3次メッシュ幅の半分

    south = 1 if lat < lat_base + lat_half else 0  # 南側=1
    west = 1 if lng < lng_base + lng_half else 0    # 西側=1

    # 1=南西, 2=南東, 3=北西, 4=北東
    if south and west:
        q = 1
    elif south and not west:
        q = 2
    elif not south and west:
        q = 3
    else:
        q = 4

    return f"{third}{q}"


def _half_mesh_center(mesh_code: str) -> Tuple[float, float]:
    """
    500mメッシュコード（9桁）から中心の緯度経度を返す。
    """
    p1 = int(mesh_code[0:2])
    u1 = int(mesh_code[2:4])
    p2 = int(mesh_code[4])
    u2 = int(mesh_code[5])
    p3 = int(mesh_code[6])
    u3 = int(mesh_code[7])
    q = int(mesh_code[8])

    # 3次メッシュの南西端
    lat_base = (p1 * 40 + p2 * 5 + p3 * 0.5) / 60
    lng_base = u1 + 100 + u2 * 0.125 + u3 * 0.0125

    # 500mメッシュのサイズ
    lat_step = 0.5 / 60 / 2  # 約15秒
    lng_step = 0.0125 / 2     # 約22.5秒

    # qから南北・東西のオフセットを決定
    lat_offset = 0 if q in (1, 2) else lat_step
    lng_offset = 0 if q in (1, 3) else lng_step

    # 中心座標
    center_lat = lat_base + lat_offset + lat_step / 2
    center_lng = lng_base + lng_offset + lng_step / 2

    return (center_lat, center_lng)


def _haversine(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """2点間の距離（メートル）をHaversine公式で計算する。"""
    R = 6371000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _enumerate_half_meshes(lat: float, lng: float, radius_m: int) -> List[str]:
    """
    指定地点を中心に半径radius_m以内の500mメッシュコードを列挙する。

    メッシュ中心が円内にあるものを採用する。
    """
    # バウンディングボックスを計算（余裕を持たせる）
    lat_deg_per_m = 1 / 111320
    lng_deg_per_m = 1 / (111320 * math.cos(math.radians(lat)))
    margin = 500  # メッシュ対角線の半分程度の余裕
    lat_delta = (radius_m + margin) * lat_deg_per_m
    lng_delta = (radius_m + margin) * lng_deg_per_m

    lat_min = lat - lat_delta
    lat_max = lat + lat_delta
    lng_min = lng - lng_delta
    lng_max = lng + lng_delta

    # 500mメッシュのステップ（緯度方向: 15秒, 経度方向: 22.5秒）
    lat_step = 0.5 / 60 / 2  # ≈0.004167度
    lng_step = 0.0125 / 2     # =0.00625度

    meshes = []
    current_lat = lat_min
    while current_lat <= lat_max:
        current_lng = lng_min
        while current_lng <= lng_max:
            mesh_code = _latlon_to_half_mesh(current_lat, current_lng)
            center = _half_mesh_center(mesh_code)
            dist = _haversine(lat, lng, center[0], center[1])
            if dist <= radius_m:
                if mesh_code not in meshes:
                    meshes.append(mesh_code)
            current_lng += lng_step
        current_lat += lat_step

    return meshes


# ============================================================
# SQLiteキャッシュ
# ============================================================

def _init_cache_db() -> sqlite3.Connection:
    """キャッシュDB初期化。テーブルが無ければ作成する。"""
    cache_dir = os.path.dirname(CACHE_DB_PATH)
    os.makedirs(cache_dir, exist_ok=True)
    conn = sqlite3.connect(CACHE_DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS mesh_data (
            mesh_code TEXT NOT NULL,
            cat_code TEXT NOT NULL,
            value INTEGER,
            PRIMARY KEY (mesh_code, cat_code)
        )
    """)
    conn.commit()
    return conn


def _get_cached(conn: sqlite3.Connection, mesh_codes: List[str]) -> Dict[str, Dict[str, Optional[int]]]:
    """キャッシュからメッシュデータを取得。存在するもののみ返す。"""
    if not mesh_codes:
        return {}
    placeholders = ",".join("?" for _ in mesh_codes)
    rows = conn.execute(
        f"SELECT mesh_code, cat_code, value FROM mesh_data WHERE mesh_code IN ({placeholders})",
        mesh_codes,
    ).fetchall()

    result: Dict[str, Dict[str, Optional[int]]] = {}
    for mesh_code, cat_code, value in rows:
        result.setdefault(mesh_code, {})[cat_code] = value
    return result


def _save_cache(conn: sqlite3.Connection, mesh_code: str, data: Dict[str, Optional[int]]) -> None:
    """メッシュデータをキャッシュに保存する。"""
    for cat_code, value in data.items():
        conn.execute(
            "INSERT OR REPLACE INTO mesh_data (mesh_code, cat_code, value) VALUES (?, ?, ?)",
            (mesh_code, cat_code, value),
        )
    conn.commit()


# ============================================================
# e-Stat API呼び出し
# ============================================================

def _fetch_estat_data(
    stats_data_id: str,
    mesh_codes: List[str],
) -> Dict[str, Dict[str, Optional[int]]]:
    """
    e-Stat APIから500mメッシュデータを取得する。

    Args:
        stats_data_id: 統計表ID
        mesh_codes: 取得対象のメッシュコード一覧

    Returns:
        {mesh_code: {cat_code: value}} の辞書
    """
    app_id = _get_estat_app_id()
    if not app_id:
        print("[estat] ESTAT_APP_IDが設定されていません")
        return {}

    result: Dict[str, Dict[str, Optional[int]]] = {}

    # cdAreaは最大100件までカンマ区切りで指定可能
    cat_filter = ",".join(CAT_CODES.keys())

    for i in range(0, len(mesh_codes), 100):
        batch = mesh_codes[i:i + 100]
        area_filter = ",".join(batch)

        params = {
            "appId": app_id,
            "statsDataId": stats_data_id,
            "cdArea": area_filter,
            "cdCat01": cat_filter,
            "cdCat02": "1",  # 秘匿なし
            "limit": 100000,
        }

        try:
            resp = requests.get(ESTAT_API_URL, params=params, timeout=60)
            resp.raise_for_status()
            data = resp.json()
        except requests.RequestException as e:
            print(f"[estat] APIリクエストエラー: {e}")
            time.sleep(1)
            continue

        stat_data = data.get("GET_STATS_DATA", {}).get("STATISTICAL_DATA", {})
        values = stat_data.get("DATA_INF", {}).get("VALUE", [])

        if not values:
            continue

        for v in values:
            mesh_code = v.get("@area", "")
            cat_code = v.get("@cat01", "")
            raw_value = v.get("$", "")

            if cat_code not in CAT_CODES:
                continue

            # 「-」や「*」は秘匿データ → Noneとして扱う
            try:
                num = int(raw_value)
            except (ValueError, TypeError):
                num = None

            result.setdefault(mesh_code, {})[cat_code] = num

        # レート制限対策
        if i + 100 < len(mesh_codes):
            time.sleep(1)

    return result


# ============================================================
# メイン関数
# ============================================================

def fetch_population(
    lat: float,
    lng: float,
    radius_m: int = 1000,
) -> Optional[Dict[str, Any]]:
    """
    指定地点の商圏内の人口・世帯データを取得する。

    500mメッシュの中心が指定半径内にあるメッシュのデータを集計する。

    Args:
        lat: 中心緯度
        lng: 中心経度
        radius_m: 分析半径（メートル）

    Returns:
        集計結果のdict。APIエラー時はNone。
        {
            "total_population": int,
            "male": int,
            "female": int,
            "age_groups": {"0-14": int, "15-64": int, "65+": int},
            "households": int,
            "mesh_count": int,
        }
    """
    # 1. 対象メッシュを列挙
    mesh_codes = _enumerate_half_meshes(lat, lng, radius_m)
    if not mesh_codes:
        return None

    # 2. 1次メッシュごとにグループ化
    mesh_by_primary: Dict[str, List[str]] = {}
    for mc in mesh_codes:
        primary = mc[:4]
        mesh_by_primary.setdefault(primary, []).append(mc)

    # 3. キャッシュ確認
    conn = _init_cache_db()
    cached = _get_cached(conn, mesh_codes)
    uncached_by_primary: Dict[str, List[str]] = {}
    for primary, codes in mesh_by_primary.items():
        for mc in codes:
            if mc not in cached or len(cached[mc]) < len(CAT_CODES) - 2:
                uncached_by_primary.setdefault(primary, []).append(mc)

    # 4. 未キャッシュ分をAPI取得
    for primary, codes in uncached_by_primary.items():
        table_id = PRIMARY_MESH_TO_TABLE.get(primary)
        if not table_id:
            print(f"[estat] 1次メッシュ {primary} のテーブルIDが見つかりません")
            continue

        fetched = _fetch_estat_data(table_id, codes)
        for mc, data in fetched.items():
            _save_cache(conn, mc, data)
            cached[mc] = data

        # データが返ってこなかったメッシュは人口0としてキャッシュ
        for mc in codes:
            if mc not in cached:
                empty = {cat: 0 for cat in CAT_CODES}
                _save_cache(conn, mc, empty)
                cached[mc] = empty

    conn.close()

    # 5. 集計
    total_pop = 0
    male = 0
    female = 0
    age_0_14 = 0
    age_0_14_m = 0
    age_0_14_f = 0
    age_15_64 = 0
    age_15_64_m = 0
    age_15_64_f = 0
    age_65_over = 0
    age_65_over_m = 0
    age_65_over_f = 0
    age_75_over = 0
    age_75_over_m = 0
    age_75_over_f = 0
    households = 0
    single_households = 0
    valid_mesh_count = 0

    for mc in mesh_codes:
        data = cached.get(mc, {})
        if not data:
            continue

        pop = data.get("0010")
        if pop is not None and pop > 0:
            valid_mesh_count += 1

        total_pop += pop or 0
        male += data.get("0020") or 0
        female += data.get("0030") or 0
        age_0_14 += data.get("0040") or 0
        age_0_14_m += data.get("0050") or 0
        age_0_14_f += data.get("0060") or 0
        age_15_64 += data.get("0100") or 0
        age_15_64_m += data.get("0110") or 0
        age_15_64_f += data.get("0120") or 0
        age_65_over += data.get("0190") or 0
        age_65_over_m += data.get("0200") or 0
        age_65_over_f += data.get("0210") or 0
        age_75_over += data.get("0220") or 0
        age_75_over_m += data.get("0230") or 0
        age_75_over_f += data.get("0240") or 0
        households += data.get("0340") or 0
        single_households += data.get("0360") or 0

    # 65〜74歳 = 65歳以上 - 75歳以上
    age_65_74 = age_65_over - age_75_over
    age_65_74_m = age_65_over_m - age_75_over_m
    age_65_74_f = age_65_over_f - age_75_over_f

    return {
        "total_population": total_pop,
        "male": male,
        "female": female,
        "age_groups": {
            "0-14": age_0_14,
            "15-64": age_15_64,
            "65+": age_65_over,
        },
        "age_pyramid": {
            "labels": ["0〜14歳", "15〜64歳", "65〜74歳", "75歳以上"],
            "male": [age_0_14_m, age_15_64_m, age_65_74_m, age_75_over_m],
            "female": [age_0_14_f, age_15_64_f, age_65_74_f, age_75_over_f],
        },
        "households": households,
        "single_households": single_households,
        "mesh_count": len(mesh_codes),
        "mesh_with_data": valid_mesh_count,
    }
