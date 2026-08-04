#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Markdownの原稿から記事HTMLを作る。

    python3 scripts/new_article.py <原稿.md> <slug> [セクション] [--date YYYY-MM-DD]

    例) python3 scripts/new_article.py ~/Desktop/通知表_01_blog.md tsuuchihyou news

セクションは news / guide / report / case。省略時は news。

Codex（edunews-contents スキル）が書いた `*_01_blog.md` をそのまま渡せる。
note用に書かれた要素（ハッシュタグ、動画への誘導文、スマ塾の宣伝）は落とす。

出力されたファイルには ★ が残る。
  ・description / og:description / sj:ogp-lead
  ・article-lede …… 塾長向けのリード文
  ・「この記事は塾にどう効くか」…… 末尾の追記
これを埋めてから `python3 scripts/build.py` を実行する。
★が残っている記事は一覧とsitemapから自動で除外されるので、公開事故は起きない。
"""

from __future__ import annotations

import html as html_mod
import re
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from import_note import SECTION_NAMES, TEMPLATE, nav_html  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
BASE_URL = "https://smart-juku.syuni.jp"


def inline(text: str) -> str:
    """段落内の記法だけ変換する（強調・リンク）"""
    t = html_mod.escape(text, quote=False)
    t = re.sub(r"\[([^\]]+)\]\((https?://[^\s)]+)\)",
               r'<a href="\2" target="_blank" rel="noopener noreferrer">\1</a>', t)
    t = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", t)
    # 裸のURLもリンクにする
    t = re.sub(r'(?<!["\'>])(https?://[^\s<]+)',
               r'<a href="\1" target="_blank" rel="noopener noreferrer">\1</a>', t)
    return t


# note向けに入れている行。自社サイトには要らないので落とす
DROP_PATTERNS = [
    r"^#{1,6}?\s*$",
    r"^\s*#\S",                                   # ハッシュタグの行
    r"Youtubeチャンネルでは動画解説",
    r"動画で全体像を先に知りたい",
    r"^\s*▶|^\s*▼|^\s*▶️",
    r"スマ塾",                                     # note側に置く自社の宣伝
]


def convert(md: str) -> tuple[str, str]:
    """Markdown → (記事本文HTML, タイトル)"""
    lines = md.replace("\r\n", "\n").split("\n")

    title = ""
    for ln in lines:
        if ln.startswith("# "):
            title = ln[2:].strip()
            break

    out: list[str] = []
    buf: list[str] = []
    mode = None  # None / "ul" / "ol"

    def flush_para():
        if buf:
            out.append(f"<p>{inline(' '.join(buf))}</p>")
            buf.clear()

    def close_list():
        nonlocal mode
        if mode:
            out.append(f"</{mode}>")
            mode = None

    for raw in lines:
        ln = raw.rstrip()

        if ln.startswith("# "):          # h1は<h1>として別に出すのでここでは捨てる
            flush_para(); close_list()
            continue
        if any(re.search(p, ln) for p in DROP_PATTERNS) and not ln.startswith(("##", "-", "1.")):
            flush_para(); close_list()
            continue

        if not ln.strip():
            flush_para(); close_list()
            continue

        m = re.match(r"^(#{2,3})\s+(.*)$", ln)
        if m:
            flush_para(); close_list()
            lvl = len(m.group(1))
            out.append(f"<h{lvl}>{inline(m.group(2).strip())}</h{lvl}>")
            continue

        m = re.match(r"^[-*]\s+(.*)$", ln)
        if m:
            flush_para()
            if mode != "ul":
                close_list(); out.append("<ul>"); mode = "ul"
            out.append(f"<li>{inline(m.group(1))}</li>")
            continue

        m = re.match(r"^\d+[.)]\s+(.*)$", ln)
        if m:
            flush_para()
            if mode != "ol":
                close_list(); out.append("<ol>"); mode = "ol"
            out.append(f"<li>{inline(m.group(1))}</li>")
            continue

        if ln.startswith(">"):
            flush_para(); close_list()
            out.append(f"<blockquote><p>{inline(ln.lstrip('> ').strip())}</p></blockquote>")
            continue

        close_list()
        buf.append(ln.strip())

    flush_para(); close_list()

    body = "\n".join("        " + x for x in out if x.strip())
    body = body.replace("★", "&#9733;")     # 未編集マーカーとの衝突を避ける
    return body, title


def main() -> int:
    if len(sys.argv) < 3:
        print(__doc__)
        return 1
    md_path = Path(sys.argv[1]).expanduser()
    slug = sys.argv[2]
    section = sys.argv[3] if len(sys.argv) > 3 and not sys.argv[3].startswith("--") else "news"
    if section not in SECTION_NAMES:
        print(f"セクションは {' / '.join(SECTION_NAMES)} のいずれかです（指定: {section}）")
        return 1

    pub = date.today().isoformat()
    for i, a in enumerate(sys.argv):
        if a == "--date" and i + 1 < len(sys.argv):
            pub = sys.argv[i + 1]

    if not md_path.exists():
        print(f"原稿が見つかりません: {md_path}")
        return 1

    body, title = convert(md_path.read_text(encoding="utf-8"))
    if not title:
        print("原稿の先頭に「# タイトル」がありません。--- で始まるメタ行がある場合は取り除いてください。")
        return 1

    y, m, d = pub.split("-")
    out = TEMPLATE.format(
        sec=section,
        sec_name=SECTION_NAMES[section],
        nav=nav_html(section),
        title=html_mod.escape(title, quote=True),
        crumb=html_mod.escape(title[:24], quote=True),
        slug=slug,
        date=pub,
        today=pub,
        date_jp=f"{int(y)}年{int(m)}月{int(d)}日",
        base=BASE_URL,
        body=body,
    )
    dest = ROOT / section / f"{slug}.html"
    dest.parent.mkdir(exist_ok=True)
    dest.write_text(out, encoding="utf-8")

    print(f"作成: {section}/{slug}.html  「{title}」  公開日 {pub}")
    print(f"見出し: h2 {out.count('<h2>') - 2} 個 / 本文 {len(re.sub('<[^>]+>', '', body))} 字")
    print("\n★（description・リード文・末尾の塾への影響）を埋めてから build.py を実行してください。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
