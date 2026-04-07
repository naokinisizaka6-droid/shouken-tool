"""
PDFレポート生成モジュール

商圏分析結果を1ページのPDFレポートとして出力する。
fpdf2（純Python）+ matplotlib（チャート画像）で構成。
"""

import io
import os
import tempfile
from datetime import datetime
from typing import Any, Dict, List, Optional

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import numpy as np
from fpdf import FPDF

# Linux環境（Streamlit Cloud）ではフォントキャッシュを再構築
if os.name != "nt":
    fm._load_fontmanager(try_read_cache=False)

# 日本語フォント設定（デプロイ先で利用可能なフォントを自動検出）
def _find_japanese_font() -> Optional[str]:
    """日本語対応フォントのパスを検出する。Windows/Linux両対応。"""
    # 1. matplotlibのフォントマネージャーから検索
    for candidate in ["Noto Sans JP", "Noto Sans CJK JP", "Meiryo", "Yu Gothic", "MS Gothic", "BIZ UDGothic"]:
        matches = [f for f in fm.fontManager.ttflist if candidate in f.name and "Bold" not in f.name]
        if matches:
            return matches[0].fname

    # 2. Linux（Streamlit Cloud）でのフォントパスを直接検索
    linux_font_paths = [
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJKjp-Regular.otf",
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/noto/NotoSansCJKjp-Regular.otf",
        "/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc",
    ]
    for path in linux_font_paths:
        if os.path.exists(path):
            return path

    # 3. フォントディレクトリを再帰検索（最終手段）
    for font_dir in ["/usr/share/fonts"]:
        if os.path.isdir(font_dir):
            for root, dirs, files in os.walk(font_dir):
                for f in files:
                    if "noto" in f.lower() and "cjk" in f.lower() and f.endswith((".ttf", ".otf", ".ttc")):
                        return os.path.join(root, f)

    return None

_FONT_PATH = _find_japanese_font()


def _setup_matplotlib_font() -> None:
    """matplotlibに日本語フォントを設定する。"""
    if _FONT_PATH:
        plt.rcParams["font.family"] = fm.FontProperties(fname=_FONT_PATH).get_name()
    plt.rcParams["axes.unicode_minus"] = False


def _create_radar_chart(scores: Dict[str, Dict[str, Any]]) -> bytes:
    """6業態のレーダーチャートをPNG画像（bytes）で返す。"""
    _setup_matplotlib_font()

    categories = list(scores.keys())
    values = [scores[cat]["score"] for cat in categories]
    N = len(categories)

    angles = [n / float(N) * 2 * np.pi for n in range(N)]
    angles += angles[:1]
    values += values[:1]

    fig, ax = plt.subplots(figsize=(4, 4), subplot_kw=dict(polar=True))
    ax.fill(angles, values, color="#FF6B6B", alpha=0.25)
    ax.plot(angles, values, color="#FF6B6B", linewidth=2)
    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(categories, fontsize=9)
    ax.set_ylim(0, 100)
    ax.set_yticks([20, 40, 60, 80, 100])
    ax.set_yticklabels(["20", "40", "60", "80", "100"], fontsize=7, color="gray")

    # 各頂点にスコアを表示
    for angle, value in zip(angles[:-1], values[:-1]):
        ax.text(angle, value + 5, str(value), ha="center", va="center", fontsize=10, fontweight="bold")

    plt.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return buf.read()


class ReportPDF(FPDF):
    """商圏分析レポート用PDF。"""

    def __init__(self) -> None:
        super().__init__(orientation="P", unit="mm", format="A4")
        self._setup_font()

    def _setup_font(self) -> None:
        """日本語フォントを登録する。"""
        if _FONT_PATH:
            try:
                self.add_font("JP", "", _FONT_PATH, uni=True)
                self.add_font("JP", "B", _FONT_PATH, uni=True)
                self._jp_font = "JP"
            except Exception as e:
                print(f"[report] フォント登録失敗: {e}")
                self._jp_font = "Helvetica"
        else:
            self._jp_font = "Helvetica"

    def header(self) -> None:
        self.set_font(self._jp_font, "B", 16)
        self.set_text_color(50, 50, 50)
        self.cell(0, 10, "商圏分析レポート", new_x="LMARGIN", new_y="NEXT", align="C")
        self.ln(2)

    def footer(self) -> None:
        self.set_y(-15)
        self.set_font(self._jp_font, "", 8)
        self.set_text_color(150, 150, 150)
        self.cell(0, 10, f"商圏分析ツール | {datetime.now().strftime('%Y/%m/%d %H:%M')}", align="C")


def generate_report(analysis: Dict[str, Any]) -> bytes:
    """
    分析結果からPDFレポートを生成する。

    Args:
        analysis: app.pyのst.session_state.analysisと同じ構造のdict

    Returns:
        PDF内容のbytes
    """
    pdf = ReportPDF()
    pdf.add_page()
    jp = pdf._jp_font

    # === 表紙情報 ===
    pdf.set_font(jp, "", 10)
    pdf.set_text_color(100, 100, 100)
    pdf.cell(0, 6, f"分析日: {datetime.now().strftime('%Y年%m月%d日')}", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 6, f"分析対象: {analysis['matched']}", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(
        0, 6,
        f"緯度経度: {analysis['lat']:.6f}, {analysis['lng']:.6f} / 半径: {analysis['radius']}m",
        new_x="LMARGIN", new_y="NEXT",
    )
    pdf.ln(4)

    # === 主要指標サマリー ===
    pdf.set_font(jp, "B", 12)
    pdf.set_text_color(50, 50, 50)
    pdf.cell(0, 8, "主要指標", new_x="LMARGIN", new_y="NEXT")

    pdf.set_font(jp, "", 10)
    pop = analysis.get("population") or {}
    stations = analysis.get("stations", [])
    landprice = analysis.get("landprice")
    competitors = analysis.get("competitors", [])

    # 指標テーブル
    pdf.set_fill_color(240, 240, 240)
    metrics = [
        ("人口総数", f"{pop.get('total_population', 0):,} 人"),
        ("世帯数", f"{pop.get('households', 0):,}"),
        ("競合店舗数", f"{len(competitors)} 店"),
        ("最寄り駅", f"{stations[0]['name']}（{stations[0]['distance_m']}m）" if stations else "—"),
        ("公示地価", f"¥{landprice['avg_price_per_sqm']:,}/㎡" if landprice else "未取得"),
    ]

    col_w = 95
    for i, (label, value) in enumerate(metrics):
        x = 10 + (i % 2) * col_w
        pdf.set_x(x)
        pdf.set_font(jp, "", 9)
        pdf.set_text_color(100, 100, 100)
        pdf.cell(30, 6, label, new_x="END")
        pdf.set_font(jp, "B", 10)
        pdf.set_text_color(50, 50, 50)
        pdf.cell(60, 6, value, new_x="LMARGIN", new_y="NEXT" if i % 2 == 1 else "LAST")
    if len(metrics) % 2 == 1:
        pdf.ln(6)
    pdf.ln(4)

    # === 年齢構成 ===
    if pop.get("total_population", 0) > 0:
        pdf.set_font(jp, "B", 12)
        pdf.cell(0, 8, "年齢構成", new_x="LMARGIN", new_y="NEXT")
        pdf.set_font(jp, "", 10)
        age = pop.get("age_groups", {})
        tp = pop["total_population"]
        for label, key in [("年少人口 (0-14歳)", "0-14"), ("生産年齢人口 (15-64歳)", "15-64"), ("高齢人口 (65歳以上)", "65+")]:
            val = age.get(key, 0)
            pct = val / tp * 100 if tp > 0 else 0
            pdf.cell(0, 6, f"  {label}: {val:,}人（{pct:.1f}%）", new_x="LMARGIN", new_y="NEXT")
        pdf.ln(4)

    # === レーダーチャート ===
    scores = analysis.get("scores", {})
    if scores:
        pdf.set_font(jp, "B", 12)
        pdf.cell(0, 8, "6業態 出店適性スコア", new_x="LMARGIN", new_y="NEXT")
        pdf.ln(2)

        # チャート画像を生成して埋め込む
        chart_bytes = _create_radar_chart(scores)
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            tmp.write(chart_bytes)
            tmp_path = tmp.name

        chart_y = pdf.get_y()
        pdf.image(tmp_path, x=55, w=100)
        os.unlink(tmp_path)

        pdf.ln(4)

        # === スコア一覧テーブル ===
        sorted_scores = sorted(scores.items(), key=lambda x: x[1]["score"], reverse=True)

        # テーブルヘッダー
        pdf.set_font(jp, "B", 9)
        pdf.set_fill_color(70, 130, 210)
        pdf.set_text_color(255, 255, 255)
        pdf.cell(40, 7, "業態", border=1, fill=True, align="C", new_x="END")
        pdf.cell(20, 7, "スコア", border=1, fill=True, align="C", new_x="END")
        pdf.cell(0, 7, "主な要因", border=1, fill=True, align="C", new_x="LMARGIN", new_y="NEXT")

        # テーブルボディ
        pdf.set_text_color(50, 50, 50)
        for i, (cat, data) in enumerate(sorted_scores):
            if i % 2 == 0:
                pdf.set_fill_color(245, 245, 245)
            else:
                pdf.set_fill_color(255, 255, 255)

            pdf.set_font(jp, "B", 9)
            pdf.cell(40, 7, cat, border=1, fill=True, new_x="END")
            pdf.set_font(jp, "", 9)
            pdf.cell(20, 7, f"{data['score']}点", border=1, fill=True, align="C", new_x="END")

            # 上位2要因を表示
            top_factors = data["breakdown"][:2]
            factors_text = "、".join(
                f"{f['factor']}({'+' if f['contribution']>=0 else ''}{f['contribution']})" for f in top_factors
            )
            pdf.cell(0, 7, factors_text, border=1, fill=True, new_x="LMARGIN", new_y="NEXT")

        pdf.ln(4)

        # === 総評 ===
        best_cat, best_data = sorted_scores[0]
        worst_cat, worst_data = sorted_scores[-1]

        pdf.set_font(jp, "B", 12)
        pdf.cell(0, 8, "総評", new_x="LMARGIN", new_y="NEXT")

        pdf.set_font(jp, "", 10)
        pdf.multi_cell(
            0, 6,
            f"この立地では「{best_cat}」の出店適性が最も高く、スコアは{best_data['score']}点です。"
            f"主な強みは{best_data['breakdown'][0]['factor']}と{best_data['breakdown'][1]['factor']}です。",
        )
        pdf.ln(2)
        if worst_data["score"] < 50:
            pdf.multi_cell(
                0, 6,
                f"一方、「{worst_cat}」は{worst_data['score']}点と低めです。"
                f"出店を検討する場合は競合状況や立地特性を慎重に評価してください。",
            )

    # PDF出力
    return pdf.output()
