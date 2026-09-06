#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""トップページ（LP）用の OGP 画像 assets/ogp.png（1200x630）を生成する。

記事用は make_ogp.py（build.py から毎回呼ばれる）。こちらは LP のコピーが
変わったときだけ手で回す。**build.py からは呼ばない。**

    python3 scripts/make_ogp_top.py

DESIGN.md の規約に従う：
  - 地色は白。クリーム（--paper）は「面」にだけ使う（右上の円）
  - 見出しは明朝、本文・ラベルはゴシック（make_ogp.py と同じヒラギノ）
  - 赤ペン（--akapen）は「月額保守費0円」の丸つけ1か所だけ。装飾に使わない
  - 蛍光マーカーは本文中の限定強調のみ。見出しには使わない（旧OGPは使っていた）
"""

from __future__ import annotations

import re
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "assets" / "ogp.png"

W, H = 1200, 630

# DESIGN.md の色トークン。ここに無い値を足さない
WHITE = "#FFFFFF"
PAPER = "#F7F4ED"
INK = "#22252B"
INK_SOFT = "#555962"
BLUE = "#24519E"
BLUE_DEEP = "#1B3D78"
AKAPEN = "#D6402C"

MINCHO = "/System/Library/Fonts/ヒラギノ明朝 ProN.ttc"   # index 2 = W6
GOTHIC_W6 = "/System/Library/Fonts/ヒラギノ角ゴシック W6.ttc"
GOTHIC_W3 = "/System/Library/Fonts/ヒラギノ角ゴシック W3.ttc"

# LP の h1（赤ペンの丸は「月額保守費0円」に付く）
TITLE_LINES = ["塾の強みが伝わり、", "入塾につながるホームページへ。"]
FOOT_TEXT = "無料HP診断で、いま効く改善点3つをお届けします"
FOOT_URL = "smart-juku.syuni.jp"

# .maru-ink の path（index.html と同一。viewBox 0 0 280 74 / stroke-width 3.2）
MARU_D = (
    "M260 24 C 246 10, 186 3, 134 5 C 64 7, 17 20, 18 38 "
    "C 20 56, 87 66, 151 65 C 221 64, 266 51, 267 33 C 269 23, 256 16, 239 11"
)
MARU_VB = (280.0, 74.0)
MARU_STROKE = 3.2


def _available() -> bool:
    try:
        import PIL  # noqa: F401
    except ImportError:
        return False
    return os.path.exists(MINCHO) and os.path.exists(GOTHIC_W6)


def _font(path: str, size: int, index: int = 0):
    from PIL import ImageFont

    return ImageFont.truetype(path, size, index=index)


# --- letter-spacing 付きの描画（LP の h1 は .04em、価格行は .03em） -------
def _track_width(draw, text: str, font, tracking: float) -> float:
    if not text:
        return 0.0
    return sum(draw.textlength(c, font=font) for c in text) + tracking * len(text)


def _track_text(draw, xy, text: str, font, fill, tracking: float) -> float:
    x, y = xy
    for c in text:
        draw.text((x, y), c, font=font, fill=fill)
        x += draw.textlength(c, font=font) + tracking
    return x


# --- SVG path（M/C だけ）を折れ線に落とす -------------------------------
def _parse_path(d: str) -> list[tuple[float, float]]:
    # "M260 24" のようにコマンドと数値がくっついた書き方があるので、
    # コマンド文字の前後を分けてから空白で切る
    toks = re.sub(r"([MC])", r" \1 ", d).replace(",", " ").split()
    pts: list[tuple[float, float]] = []
    cur = (0.0, 0.0)
    i = 0
    while i < len(toks):
        cmd = toks[i]
        if cmd == "M":
            cur = (float(toks[i + 1]), float(toks[i + 2]))
            pts.append(cur)
            i += 3
        elif cmd == "C":
            p1 = (float(toks[i + 1]), float(toks[i + 2]))
            p2 = (float(toks[i + 3]), float(toks[i + 4]))
            p3 = (float(toks[i + 5]), float(toks[i + 6]))
            p0 = cur
            for s in range(1, 25):
                t = s / 24
                u = 1 - t
                pts.append(
                    (
                        u**3 * p0[0] + 3 * u * u * t * p1[0] + 3 * u * t * t * p2[0] + t**3 * p3[0],
                        u**3 * p0[1] + 3 * u * u * t * p1[1] + 3 * u * t * t * p2[1] + t**3 * p3[1],
                    )
                )
            cur = p3
            i += 7
        else:  # 想定外のコマンドは無視（この path には現れない）
            i += 1
    return pts


def _draw_maru(img, cx: float, cy: float, box_w: float) -> None:
    """赤ペンの丸つけ。box_w は SVG の描画幅（px）。
    4倍で描いてから縮小し、SVG と同じなめらかさにする"""
    from PIL import Image, ImageDraw

    ss = 4
    layer = Image.new("RGBA", (img.width * ss, img.height * ss), (0, 0, 0, 0))
    dl = ImageDraw.Draw(layer)

    sx = box_w / MARU_VB[0]
    box_h = MARU_VB[1] * sx
    ox = cx - box_w / 2
    oy = cy - box_h / 2
    pts = [((ox + px * sx) * ss, (oy + py * sx) * ss) for px, py in _parse_path(MARU_D)]
    w = max(2, round(MARU_STROKE * sx * ss))
    dl.line(pts, fill=AKAPEN, width=w, joint="curve")
    # stroke-linecap:round の再現（両端を丸める）
    r = w / 2
    for p in (pts[0], pts[-1]):
        dl.ellipse((p[0] - r, p[1] - r, p[0] + r, p[1] + r), fill=AKAPEN)

    img.paste(layer.resize(img.size, Image.LANCZOS).convert("RGB"),
              (0, 0), layer.resize(img.size, Image.LANCZOS).split()[3])


def render(out_path: Path = OUT) -> None:
    from PIL import Image, ImageDraw

    img = Image.new("RGB", (W, H), WHITE)
    d = ImageDraw.Draw(img)

    pad = 76

    # --- 右上の「面」：クリームの円（旧OGPの構図を踏襲） ----------------
    # 4倍で描いて縮小し、縁のジャギーを消す
    ss = 4
    circle = Image.new("RGB", (W * ss, H * ss), WHITE)
    dc = ImageDraw.Draw(circle)
    # 見出し2行目（上端 322）に円が掛からない大きさ・位置にする
    ccx, ccy, cr = 1122, 38, 252
    dc.ellipse(
        ((ccx - cr) * ss, (ccy - cr) * ss, (ccx + cr) * ss, (ccy + cr) * ss), fill=PAPER
    )
    img.paste(circle.resize((W, H), Image.LANCZOS), (0, 0))
    d = ImageDraw.Draw(img)

    # --- ロゴ（旧OGPと同じ位置・同じ扱い：1行に並べる） -----------------
    logo_y = 116
    f_logo = _font(GOTHIC_W6, 40)
    f_tag = _font(GOTHIC_W3, 19)
    d.ellipse((pad, logo_y + 15, pad + 20, logo_y + 35), fill=BLUE)
    lx = _track_text(d, (pad + 36, logo_y), "スマ塾", f_logo, INK, 2.0)
    d.text((lx + 16, logo_y + 19), "学習塾専門のWeb支援", font=f_tag, fill=INK_SOFT)

    # --- 主見出し（明朝。2行。折り返しはしない＝1文字残りが出ない） -----
    t_size, t_gap, t_track = 64, 96, 2.6   # 2.6/64 ≒ .04em（LPの h1 と同じ）
    f_title = _font(MINCHO, t_size, index=2)
    max_w = W - pad * 2
    while max(_track_width(d, ln, f_title, t_track) for ln in TITLE_LINES) > max_w:
        t_size -= 2
        t_gap -= 3
        t_track = t_size * 0.04
        f_title = _font(MINCHO, t_size, index=2)

    ty = 226
    for ln in TITLE_LINES:
        _track_text(d, (pad, ty), ln, f_title, INK, t_track)
        ty += t_gap

    # --- 価格行（ゴシック700。枠は付けない。赤ペンの丸はここだけ） ------
    p_size = 34
    p_track = p_size * 0.03
    f_price = _font(GOTHIC_W6, p_size)
    f_small = _font(GOTHIC_W6, round(p_size * 0.68))   # LP の .hero-price small
    py = 448
    small_dy = round((p_size - p_size * 0.68) * 0.62)  # 小書きの下端を揃える

    x = float(pad)
    x = _track_text(d, (x, py), "55,000円", f_price, INK, p_track)
    x = _track_text(d, (x, py + small_dy), "（税込）から", f_small, INK, p_size * 0.02)
    x = _track_text(d, (x, py), "・買い切り・", f_price, INK, p_track)

    maru_text = "月額保守費0円"
    maru_x0 = x + p_size * 0.22   # .maru の padding 0 .22em（丸が中黒に掛からない）
    maru_w = _track_width(d, maru_text, f_price, p_track)
    _track_text(d, (maru_x0, py), maru_text, f_price, INK, p_track)

    # .maru: padding 0 .22em ／ .maru-ink: left -.6em, width 100% + 1.2em
    # path は viewBox 幅の 90% しか使わないぶん、CSS 値より少し広くとる
    # 縮小表示でも赤ペンが残るよう、CSS 値より 12% だけ大きく（線も太くなる）
    box_w = (maru_w + p_size * 0.44 + p_size * 1.2) * 1.12
    _draw_maru(img, maru_x0 + maru_w / 2, py + p_size * 0.62, box_w)

    # --- 下段の帯（LPの無料HP診断節と同じ紺） ---------------------------
    band_y = 530
    d.rectangle((0, band_y, W, H), fill=BLUE_DEEP)
    f_foot = _font(GOTHIC_W6, 27)
    d.text((pad, band_y + 33), FOOT_TEXT, font=f_foot, fill="#FFFFFF")
    f_url = _font(GOTHIC_W3, 21)
    uw = d.textlength(FOOT_URL, font=f_url)
    d.text((W - pad - uw, band_y + 38), FOOT_URL, font=f_url, fill="#BFCCE4")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(out_path, "PNG", optimize=True)


if __name__ == "__main__":
    if not _available():
        raise SystemExit("Pillow か ヒラギノフォントが見つかりません")
    render()
    print(f"{OUT.relative_to(ROOT)} を生成しました（{OUT.stat().st_size:,} bytes）")
