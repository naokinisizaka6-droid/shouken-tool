"""
6業態スコアリングの重み定数

各業態ごとに、特徴量の重みを定義する。
重みは正=プラス寄与、負=マイナス寄与。合計が100前後になるよう設計。
後から調整しやすいように、業態ごとに辞書で管理する。

【特徴量一覧】
- night_population     : 夜間人口（商圏内総人口）
- young_ratio          : 20〜64歳比率（生産年齢人口 / 総人口）
- elderly_ratio        : 65歳以上比率
- households           : 世帯数
- station_distance     : 最寄り駅距離（m）※近いほど高スコア
- competitor_density   : 同業態の競合密度（件数）※多いほど低スコア
- total_competitors    : 全飲食店数（エリアの集客力指標）
- landprice            : 公示地価㎡単価 ※高いほどコスト大（マイナス寄与）
"""

# 各特徴量の理想的な基準値（スコア正規化に使用）
# 「この値なら満点」という目安
REFERENCE_VALUES = {
    "night_population": 15000,    # 半径1km圏の理想的な夜間人口
    "young_ratio": 0.70,          # 生産年齢人口比率の理想値
    "elderly_ratio": 0.30,        # 高齢者比率（これ以上でスコア低下）
    "households": 8000,           # 理想的な世帯数
    "station_distance": 300,      # 駅距離（これ以下で満点）
    "station_distance_max": 2000, # これ以上離れるとスコア0
    "competitor_density": 5,      # 同業態競合がこの数なら適度
    "competitor_density_max": 20, # これ以上で飽和
    "total_competitors": 50,      # 全飲食店数の理想値（集客力あり）
    "landprice": 500000,          # 地価の基準値（円/㎡）
    "landprice_max": 3000000,     # これ以上は高コストペナルティ大
}

# ============================================================
# 業態別の重み
# ============================================================
# 各値は「その特徴量が満点のとき何点寄与するか」を意味する。
# 負の値はマイナス寄与。
# 各業態の重み合計（正の重みのみ）が約100になるよう設計。

WEIGHTS = {
    "居酒屋": {
        "night_population": 30,     # 夜間人口が最重要
        "young_ratio": 20,          # 20〜64歳が多いほど有利
        "elderly_ratio": -5,        # 高齢者比率はやや不利
        "households": 10,           # 単身世帯が多いエリアは有利
        "station_distance": 25,     # 駅近が非常に重要
        "competitor_density": -10,  # 同業態多すぎはマイナス
        "total_competitors": 10,    # 飲食街としての成熟度
        "landprice": -10,           # 高地価はコスト増
    },
    "カフェ": {
        "night_population": 15,
        "young_ratio": 20,
        "elderly_ratio": 5,         # 高齢者もカフェ利用あり
        "households": 15,
        "station_distance": 20,     # 駅近だが居酒屋ほどではない
        "competitor_density": -15,  # カフェは差別化が難しい
        "total_competitors": 15,    # 人通りの多さが重要
        "landprice": -15,           # カフェは客単価低いので地価影響大
    },
    "ラーメン": {
        "night_population": 25,
        "young_ratio": 25,          # 若年層がメインターゲット
        "elderly_ratio": -5,
        "households": 10,
        "station_distance": 25,     # 駅近が重要
        "competitor_density": -8,   # ラーメン激戦区でも成立しやすい
        "total_competitors": 10,
        "landprice": -5,            # 小規模店舗なので地価影響は小さめ
    },
    "定食・ファミレス": {
        "night_population": 20,
        "young_ratio": 10,
        "elderly_ratio": 10,        # 幅広い年齢層が利用
        "households": 25,           # 家族世帯が多いほど有利
        "station_distance": 15,     # 駅近でなくてもOK
        "competitor_density": -10,
        "total_competitors": 10,
        "landprice": -10,
    },
    "フレンチ・イタリアン": {
        "night_population": 15,
        "young_ratio": 15,
        "elderly_ratio": 5,
        "households": 10,
        "station_distance": 15,
        "competitor_density": -5,   # 高級業態は競合少ない方が有利だが影響小
        "total_competitors": 15,    # 飲食街としてのブランド力
        "landprice": -5,            # 客単価高いので地価の影響は相対的に小さい
        # 重み合計の補正として、人口の質（所得水準の代替指標として地価を正に加算）
        "landprice_positive": 20,   # 高地価エリア=高所得層が多い=プラス
    },
    "焼肉": {
        "night_population": 25,
        "young_ratio": 20,
        "elderly_ratio": 0,
        "households": 15,           # 家族利用も多い
        "station_distance": 20,
        "competitor_density": -10,
        "total_competitors": 10,
        "landprice": -8,
    },
}

# 業態名→OSM amenity/cuisineタグのマッピング（競合カウント用）
CATEGORY_CUISINE_MAP = {
    "居酒屋": {"amenity": ["bar", "pub"], "cuisine": ["japanese"]},
    "カフェ": {"amenity": ["cafe"], "cuisine": ["coffee"]},
    "ラーメン": {"amenity": ["fast_food", "restaurant"], "cuisine": ["ramen", "noodle"]},
    "定食・ファミレス": {"amenity": ["restaurant", "fast_food"], "cuisine": ["japanese", "regional"]},
    "フレンチ・イタリアン": {"amenity": ["restaurant"], "cuisine": ["french", "italian", "pizza"]},
    "焼肉": {"amenity": ["restaurant"], "cuisine": ["barbecue", "korean", "yakiniku"]},
}
