#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""記事ごとのOGP画像（1200x630 PNG）を生成する。

build.py から呼ばれます。単体でも実行できます:
    python3 scripts/make_ogp.py

デザインはサイト本体と同じ（生成り×紺青×明朝）。装飾は足さず、
「どの記事か」が一目で分かることだけを目的にしています。

記事側の任意メタ:
    <meta name="sj:ogp-lead" content="40塾を診断／情報の鮮度に課題 25.0%">
      → タイトルの下に一行入ります。数値を入れると共有時に効きます。

出力先: assets/ogp/<セクション>-<ファイル名>.png
      （記事の og:image をこのパスにしておくこと）

Pillow が無い環境では何もせずスキップします（build.py が警告を出します）。
"""

from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "assets" / "ogp"

W, H = 1200, 630
PAPER = "#F7F4ED"
INK = "#22252B"
INK_SOFT = "#555962"
BLUE = "#24519E"
LINE = "#DCD8CF"

MINCHO = "/System/Library/Fonts/ヒラギノ明朝 ProN.ttc"   # index 2 = W6
GOTHIC_W6 = "/System/Library/Fonts/ヒラギノ角ゴシック W6.ttc"
GOTHIC_W3 = "/System/Library/Fonts/ヒラギノ角ゴシック W3.ttc"

# 行頭に置かない文字 / 行末に置かない文字（簡易禁則）
NO_LINE_START = "、。，．）」』】〉》〕｝!?！？・ーぁぃぅぇぉっゃゅょゎァィゥェォッャュョヮ%％"
NO_LINE_END = "（「『【〈《〔｛"


def _available() -> bool:
    try:
        import PIL  # noqa: F401
    except ImportError:
        return False
    return os.path.exists(MINCHO) and os.path.exists(GOTHIC_W6)


def _font(path: str, size: int, index: int = 0):
    from PIL import ImageFont

    return ImageFont.truetype(path, size, index=index)


def _wrap(text: str, font, max_width: int, draw) -> list[str]:
    """日本語向けの1文字ずつの折り返し（簡易禁則つき）"""
    lines: list[str] = []
    cur = ""
    for ch in text:
        trial = cur + ch
        if draw.textlength(trial, font=font) <= max_width:
            cur = trial
            continue
        # 折り返す。ただし行頭に来られない文字はぶら下げる
        if ch in NO_LINE_START:
            cur = trial
            continue
        # 行末に来られない文字が末尾にあれば次行へ送る
        if cur and cur[-1] in NO_LINE_END:
            lines.append(cur[:-1])
            cur = cur[-1] + ch
        else:
            lines.append(cur)
            cur = ch
    if cur:
        lines.append(cur)

    # 熟語が「累／計」のように1文字で割れると目につく。
    # 行末が漢字1文字で、次行の先頭も漢字なら、その1文字を次行へ送る。
    def _kanji(c: str) -> bool:
        return "\u4e00" <= c <= "\u9fff"

    for i in range(len(lines) - 1):
        a, b = lines[i], lines[i + 1]
        if len(a) >= 2 and _kanji(a[-1]) and b and _kanji(b[0]) and not _kanji(a[-2]):
            lines[i], lines[i + 1] = a[:-1].rstrip(), a[-1] + b
    return lines


def render(out_path: Path, *, title: str, category: str, lead: str = "") -> None:
    from PIL import Image, ImageDraw

    img = Image.new("RGB", (W, H), PAPER)
    d = ImageDraw.Draw(img)

    pad = 76

    # --- ロゴ -------------------------------------------------------
    d.ellipse((pad, 62, pad + 18, 80), fill=BLUE)
    f_logo = _font(GOTHIC_W6, 34)
    d.text((pad + 32, 55), "スマ塾", font=f_logo, fill=INK)
    f_tag = _font(GOTHIC_W3, 17)
    d.text((pad + 32, 98), "学習塾専門のWeb支援", font=f_tag, fill=INK_SOFT)

    # --- カテゴリ ---------------------------------------------------
    f_cat = _font(GOTHIC_W6, 22)
    cat_w = d.textlength(category, font=f_cat)
    cy = 166
    d.rounded_rectangle((pad, cy, pad + cat_w + 40, cy + 44), radius=22, outline=BLUE, width=2)
    d.text((pad + 20, cy + 9), category, font=f_cat, fill=BLUE)

    # --- タイトル（入る大きさまで自動で縮める） ---------------------
    max_w = W - pad * 2
    foot_y = H - 96          # フッターの罫線。ここから下には何も置かない
    f_lead = _font(GOTHIC_W6, 26)
    lead_lines = _wrap(lead, f_lead, max_w, d)[:2] if lead else []
    need_lead = 14 + 40 * len(lead_lines) if lead_lines else 0

    # タイトルとリードが、フッターの手前に収まる大きさまで縮める
    for size, gap in ((62, 92), (56, 84), (50, 76), (44, 68)):
        f_title = _font(MINCHO, size, index=2)
        lines = _wrap(title, f_title, max_w, d)
        if len(lines) <= 3 and 258 + len(lines) * gap + need_lead <= foot_y - 16:
            break
    lines = lines[:3]

    y = 258
    for ln in lines:
        d.text((pad, y), ln, font=f_title, fill=INK)
        y += gap

    # --- リード（任意） ---------------------------------------------
    if lead_lines:
        ly = max(y + 14, 470)
        # それでも入らない場合は行を削る。フッターに重ねるくらいなら出さない
        while lead_lines and ly + 40 * len(lead_lines) > foot_y - 16:
            lead_lines.pop()
        for ln in lead_lines:
            d.text((pad, ly), ln, font=f_lead, fill=BLUE)
            ly += 40

    # --- フッター ---------------------------------------------------
    d.line((pad, H - 96, W - pad, H - 96), fill=LINE, width=1)
    f_url = _font(GOTHIC_W3, 21)
    d.text((pad, H - 74), "smart-juku.syuni.jp", font=f_url, fill=INK_SOFT)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(out_path, "PNG", optimize=True)


def ogp_rel_path(section_slug: str, filename: str) -> str:
    """記事URLから、その記事のOGP画像パスを決める（命名規則）"""
    return f"/assets/ogp/{section_slug}-{Path(filename).stem}.png"


def build(articles: list[dict]) -> tuple[int, list[str]]:
    """articles: {section, filename, title, category, lead} のリスト"""
    if not _available():
        return 0, ["Pillow か ヒラギノフォントが見つからないため、OGP画像の生成をスキップしました"]

    made = 0
    warns: list[str] = []
    for a in articles:
        rel = ogp_rel_path(a["section"], a["filename"])
        out = ROOT / rel.lstrip("/")
        try:
            render(out, title=a["title"], category=a["category"], lead=a.get("lead", ""))
            made += 1
        except Exception as e:  # 1本失敗しても全体は止めない
            warns.append(f"{rel}: 生成に失敗しました（{e}）")
    return made, warns


if __name__ == "__main__":
    # 単体実行時は build.py の収集ロジックを借りる
    import build as b  # type: ignore

    items = []
    for section in b.SECTIONS:
        arts, _ = b.collect_articles(section)
        for a in arts:
            items.append(
                {
                    "section": section["slug"],
                    "filename": Path(a["url"]).name,
                    "title": a["title"],
                    "category": section["name"],
                    "lead": a.get("ogp_lead", ""),
                }
            )
    n, warns = build(items)
    print(f"OGP画像を {n} 枚生成しました")
    for w in warns:
        print("  -", w)
