"""
商圏分析ツール - Streamlitアプリ

住所を入力すると、商圏内の競合店舗・人口データを集約し、
業態別の出店適性スコアを算出する。
"""

import streamlit as st
import folium
from streamlit_folium import st_folium
import pandas as pd

from modules.geocoding import geocode
from modules.competitors import fetch_competitors, summarize_by_category
from modules.estat import fetch_population
from modules.stations import fetch_nearest_stations
from modules.landprice import fetch_landprice
from modules.scoring import calculate_scores
from modules.report import generate_report


# ---------- ページ設定 ----------
st.set_page_config(
    page_title="商圏分析ツール",
    page_icon="🍴",
    layout="wide",
)

st.title("🍴 商圏分析ツール")
st.caption("住所を入力すると、商圏内の競合・人口・立地特性を分析し、業態別の出店適性を可視化します。")


# ---------- セッション状態 ----------
if "analysis" not in st.session_state:
    st.session_state.analysis = None
if "compare_list" not in st.session_state:
    st.session_state.compare_list = []


# ---------- サイドバー ----------
with st.sidebar:
    st.header("分析設定")

    address = st.text_input(
        "住所を入力",
        placeholder="例: 東京都渋谷区道玄坂2-1-1",
        help="番地まで入力すると精度が上がります",
    )

    radius = st.select_slider(
        "分析半径",
        options=[300, 500, 1000, 1500, 2000],
        value=1000,
        format_func=lambda x: f"{x}m",
    )

    analyze_btn = st.button("🔍 分析する", type="primary", use_container_width=True)

    # --- 比較リスト ---
    st.divider()
    st.markdown("**📋 候補地比較リスト**")
    if st.session_state.analysis is not None:
        if st.button("＋ 現在の分析結果を追加", use_container_width=True):
            current = st.session_state.analysis
            # 同じ住所が既に追加されていないかチェック
            existing = [c["matched"] for c in st.session_state.compare_list]
            if current["matched"] in existing:
                st.warning("この候補地は既に追加済みです")
            elif len(st.session_state.compare_list) >= 4:
                st.warning("比較は最大4地点までです")
            else:
                st.session_state.compare_list.append(current)
                st.success(f"「{current['matched']}」を追加しました")

    if st.session_state.compare_list:
        for i, c in enumerate(st.session_state.compare_list):
            st.caption(f"{i+1}. {c['matched']}")
        if st.button("🗑️ 比較リストをクリア", use_container_width=True):
            st.session_state.compare_list = []
            st.rerun()
    else:
        st.caption("分析後に「追加」で候補地を蓄積できます")

    st.divider()
    st.markdown("**データソース**")
    st.caption("- 住所検索: 国土地理院")
    st.caption("- 競合店舗: OpenStreetMap")
    st.caption("- 人口データ: e-Stat 500mメッシュ")
    st.caption("- 公示地価: 不動産情報ライブラリ")


# ---------- 分析実行 ----------
if analyze_btn:
    if not address.strip():
        st.error("住所を入力してください")
    else:
        with st.spinner("住所を検索中..."):
            geo = geocode(address)

        if geo is None:
            st.error("住所が見つかりませんでした。表記を変えて試してみてください。")
        else:
            lat, lng, matched = geo
            with st.spinner(f"半径{radius}m以内の競合店舗を取得中..."):
                competitors = fetch_competitors(lat, lng, radius_m=radius)

            with st.spinner("人口・世帯データを取得中..."):
                population = fetch_population(lat, lng, radius_m=radius)

            with st.spinner("最寄り駅を検索中..."):
                stations = fetch_nearest_stations(lat, lng)

            with st.spinner("公示地価を取得中..."):
                landprice = fetch_landprice(lat, lng)

            scores = calculate_scores(population, competitors, stations, landprice)

            st.session_state.analysis = {
                "address": address,
                "matched": matched,
                "lat": lat,
                "lng": lng,
                "radius": radius,
                "competitors": competitors,
                "population": population,
                "stations": stations,
                "landprice": landprice,
                "scores": scores,
            }


# ---------- 結果表示 ----------
analysis = st.session_state.analysis

if analysis is None:
    st.info("👈 サイドバーから住所を入力して「分析する」を押してください。")
    st.markdown("""
    ### このツールでできること
    - 商圏内の **人口・年齢構成・昼夜人口比** の把握
    - **競合店舗** の分布と業態別カウント
    - **最寄り駅** と乗降客数
    - **公示地価** から見る立地コスト感
    - 6業態（居酒屋／カフェ／ラーメン／定食・ファミレス／フレンチ・イタリアン／焼肉）の **出店適性スコア**
    - 複数候補地の **比較レポート**（PDF出力）
    """)
else:
    st.subheader(f"📍 分析結果: {analysis['matched']}")

    col_header1, col_header2 = st.columns([3, 1])
    with col_header1:
        st.caption(f"緯度経度: {analysis['lat']:.6f}, {analysis['lng']:.6f}")
    with col_header2:
        try:
            pdf_bytes = generate_report(analysis)
            st.download_button(
                label="📄 PDFレポート",
                data=pdf_bytes,
                file_name=f"商圏分析_{analysis['matched']}.pdf",
                mime="application/pdf",
                use_container_width=True,
            )
        except Exception as e:
            st.button("📄 PDF生成エラー", disabled=True, use_container_width=True)
            st.caption(f"PDF生成に失敗: {e}")

    col1, col2 = st.columns([3, 2])

    # ----- 地図 -----
    with col1:
        m = folium.Map(
            location=[analysis["lat"], analysis["lng"]],
            zoom_start=15,
            tiles="OpenStreetMap",
        )

        # 中心マーカー
        folium.Marker(
            [analysis["lat"], analysis["lng"]],
            popup=analysis["matched"],
            icon=folium.Icon(color="red", icon="star"),
        ).add_to(m)

        # 半径円
        for r, color, opacity in [(500, "#3186cc", 0.10), (1000, "#3186cc", 0.07), (2000, "#3186cc", 0.04)]:
            if r <= analysis["radius"]:
                folium.Circle(
                    location=[analysis["lat"], analysis["lng"]],
                    radius=r,
                    color=color,
                    fill=True,
                    fill_opacity=opacity,
                    weight=1,
                    popup=f"{r}m",
                ).add_to(m)

        # 競合店舗ピン
        amenity_colors = {
            "restaurant": "blue",
            "cafe": "green",
            "fast_food": "orange",
            "bar": "purple",
            "pub": "darkpurple",
            "food_court": "cadetblue",
        }
        for c in analysis["competitors"]:
            folium.CircleMarker(
                location=[c["lat"], c["lng"]],
                radius=4,
                color=amenity_colors.get(c["amenity"], "gray"),
                fill=True,
                fill_opacity=0.7,
                popup=f"{c['name']}<br>{c['label']}",
            ).add_to(m)

        # 最寄り駅ピン
        for s in analysis.get("stations", []):
            folium.Marker(
                [s["lat"], s["lng"]],
                popup=f"🚉 {s['name']}（{s['distance_m']}m）<br>{s['operator']}",
                icon=folium.Icon(color="darkblue", icon="train", prefix="fa"),
            ).add_to(m)

        st_folium(m, height=500, use_container_width=True)

    # ----- サマリー -----
    with col2:
        st.metric("検出された競合店舗", f"{len(analysis['competitors'])} 店")

        # 最寄り駅
        stations = analysis.get("stations", [])
        if stations:
            st.markdown("**最寄り駅**")
            for s in stations:
                st.caption(f"🚉 {s['name']}（{s['distance_m']}m）- {s['operator']}")

        # 公示地価
        lp = analysis.get("landprice")
        if lp:
            st.markdown("**公示地価（周辺平均）**")
            st.metric("㎡単価", f"¥{lp['avg_price_per_sqm']:,}")

        summary = summarize_by_category(analysis["competitors"])
        if summary:
            st.markdown("**業態別件数**")
            df = pd.DataFrame(
                [{"業態": k, "件数": v} for k, v in summary.items()]
            )
            st.dataframe(df, hide_index=True, use_container_width=True)

            st.bar_chart(df.set_index("業態"))
        else:
            st.info("競合店舗が見つかりませんでした。")

    # ----- タブ：詳細 -----
    st.divider()
    tab1, tab2, tab3 = st.tabs(["🏪 競合一覧", "👥 人口・属性", "📊 スコアリング"])

    with tab1:
        if analysis["competitors"]:
            df = pd.DataFrame(analysis["competitors"])
            df = df[["name", "label", "cuisine", "lat", "lng"]]
            df.columns = ["店名", "業態", "料理ジャンル", "緯度", "経度"]
            st.dataframe(df, hide_index=True, use_container_width=True)
        else:
            st.info("データなし")

    with tab2:
        pop = analysis.get("population")
        if pop is None:
            st.warning("人口データを取得できませんでした。.envにESTAT_APP_IDが設定されているか確認してください。")
        elif pop["total_population"] == 0:
            st.info("この地域のメッシュデータには人口が登録されていません。")
        else:
            import plotly.graph_objects as go

            # --- 主要指標 ---
            col_m1, col_m2, col_m3, col_m4 = st.columns(4)
            col_m1.metric("人口総数", f"{pop['total_population']:,} 人")
            col_m2.metric("世帯数", f"{pop['households']:,}")
            single = pop.get("single_households", 0)
            if pop["households"] > 0:
                single_pct = f"（単身 {single/pop['households']:.0%}）"
            else:
                single_pct = ""
            col_m3.metric("単身世帯", f"{single:,} {single_pct}")
            col_m4.metric("集計メッシュ", f"{pop['mesh_with_data']} / {pop['mesh_count']}")

            st.markdown("---")

            # --- 年齢ピラミッド + 男女比 ---
            col_a, col_b = st.columns([3, 2])

            with col_a:
                st.markdown("**年齢ピラミッド**")
                pyramid = pop.get("age_pyramid", {})
                labels = pyramid.get("labels", [])
                male_vals = pyramid.get("male", [])
                female_vals = pyramid.get("female", [])

                fig_pyramid = go.Figure()
                fig_pyramid.add_trace(go.Bar(
                    y=labels,
                    x=[-v for v in male_vals],  # 男性は左（負の値）
                    name="男性",
                    orientation="h",
                    marker_color="#4A90D9",
                    text=[f"{v:,}" for v in male_vals],
                    textposition="inside",
                ))
                fig_pyramid.add_trace(go.Bar(
                    y=labels,
                    x=female_vals,
                    name="女性",
                    orientation="h",
                    marker_color="#E8737A",
                    text=[f"{v:,}" for v in female_vals],
                    textposition="inside",
                ))
                max_val = max(max(male_vals, default=0), max(female_vals, default=0))
                fig_pyramid.update_layout(
                    barmode="overlay",
                    xaxis=dict(
                        range=[-max_val * 1.2, max_val * 1.2],
                        title="人口",
                        tickvals=[],
                    ),
                    yaxis=dict(title=""),
                    height=300,
                    margin=dict(l=20, r=20, t=10, b=40),
                    legend=dict(orientation="h", yanchor="bottom", y=1.02),
                )
                st.plotly_chart(fig_pyramid, use_container_width=True)

            with col_b:
                st.markdown("**男女比**")
                fig_gender = go.Figure(data=[go.Pie(
                    labels=["男性", "女性"],
                    values=[pop["male"], pop["female"]],
                    marker_colors=["#4A90D9", "#E8737A"],
                    hole=0.4,
                    textinfo="label+percent",
                )])
                fig_gender.update_layout(
                    height=300,
                    margin=dict(l=20, r=20, t=10, b=10),
                    showlegend=False,
                )
                st.plotly_chart(fig_gender, use_container_width=True)

                st.markdown("**年齢3区分**")
                age = pop["age_groups"]
                tp = pop["total_population"]
                for label, key in [("年少 (0-14)", "0-14"), ("生産年齢 (15-64)", "15-64"), ("高齢 (65+)", "65+")]:
                    val = age[key]
                    pct = val / tp * 100 if tp > 0 else 0
                    st.caption(f"{label}: {val:,}人（{pct:.1f}%）")

    with tab3:
        scores = analysis.get("scores", {})
        if not scores:
            st.warning("スコアデータがありません。")
        else:
            # --- 総評 ---
            sorted_scores = sorted(scores.items(), key=lambda x: x[1]["score"], reverse=True)
            best_cat, best_data = sorted_scores[0]
            worst_cat, worst_data = sorted_scores[-1]

            st.success(
                f"**おすすめ業態: {best_cat}（{best_data['score']}点）** — "
                f"この立地では{best_cat}の適性が最も高いです。"
            )
            if worst_data["score"] < 50:
                st.warning(
                    f"**注意業態: {worst_cat}（{worst_data['score']}点）** — "
                    f"この立地での{worst_cat}出店はリスクが高い可能性があります。"
                )

            st.markdown("---")

            # --- レーダーチャート ---
            import plotly.graph_objects as go

            categories_list = [cat for cat, _ in sorted_scores]
            values = [data["score"] for _, data in sorted_scores]
            # レーダーチャートは閉じた多角形にする
            categories_list_closed = categories_list + [categories_list[0]]
            values_closed = values + [values[0]]

            fig = go.Figure()
            fig.add_trace(go.Scatterpolar(
                r=values_closed,
                theta=categories_list_closed,
                fill="toself",
                name="出店適性スコア",
                line=dict(color="#FF6B6B"),
                fillcolor="rgba(255, 107, 107, 0.25)",
            ))
            fig.update_layout(
                polar=dict(
                    radialaxis=dict(visible=True, range=[0, 100]),
                ),
                showlegend=False,
                height=400,
                margin=dict(l=80, r=80, t=40, b=40),
            )
            st.plotly_chart(fig, use_container_width=True)

            # --- 各業態のスコア内訳 ---
            st.markdown("### 業態別スコア内訳")
            cols = st.columns(2)
            for i, (cat, data) in enumerate(sorted_scores):
                with cols[i % 2]:
                    st.markdown(f"**{cat}** — {data['score']}点")
                    breakdown_df = pd.DataFrame(data["breakdown"])
                    breakdown_df.columns = ["要因", "値", "寄与点"]
                    st.dataframe(breakdown_df, hide_index=True, use_container_width=True)


# ============================================================
# 候補地比較セクション
# ============================================================
if len(st.session_state.compare_list) >= 2:
    st.divider()
    st.header("📊 候補地比較")

    compare = st.session_state.compare_list
    import plotly.graph_objects as go

    # --- 比較レーダーチャート ---
    colors = ["#FF6B6B", "#4A90D9", "#50C878", "#FFB347"]
    fig_compare = go.Figure()

    category_names = list(compare[0]["scores"].keys())
    category_names_closed = category_names + [category_names[0]]

    for idx, loc in enumerate(compare):
        values = [loc["scores"][cat]["score"] for cat in category_names]
        values_closed = values + [values[0]]
        fig_compare.add_trace(go.Scatterpolar(
            r=values_closed,
            theta=category_names_closed,
            fill="toself",
            name=loc["matched"],
            line=dict(color=colors[idx % len(colors)]),
            fillcolor=f"rgba{tuple(list(bytes.fromhex(colors[idx % len(colors)][1:])) + [0.1])}",
        ))

    fig_compare.update_layout(
        polar=dict(radialaxis=dict(visible=True, range=[0, 100])),
        height=450,
        margin=dict(l=80, r=80, t=40, b=40),
    )
    st.plotly_chart(fig_compare, use_container_width=True)

    # --- 比較テーブル ---
    compare_data = {"業態": category_names}
    for loc in compare:
        compare_data[loc["matched"]] = [
            loc["scores"][cat]["score"] for cat in category_names
        ]
    compare_df = pd.DataFrame(compare_data)
    st.dataframe(compare_df, hide_index=True, use_container_width=True)

    # --- 主要指標比較 ---
    st.markdown("### 主要指標比較")
    metrics_data = []
    for loc in compare:
        pop = loc.get("population") or {}
        stn = loc.get("stations", [])
        lp = loc.get("landprice")
        metrics_data.append({
            "候補地": loc["matched"],
            "人口": f"{pop.get('total_population', 0):,}",
            "世帯数": f"{pop.get('households', 0):,}",
            "最寄り駅": stn[0]["name"] if stn else "-",
            "駅距離": f"{stn[0]['distance_m']}m" if stn else "-",
            "競合店舗数": len(loc["competitors"]),
            "地価(㎡)": f"¥{lp['avg_price_per_sqm']:,}" if lp else "未取得",
        })
    st.dataframe(pd.DataFrame(metrics_data), hide_index=True, use_container_width=True)
