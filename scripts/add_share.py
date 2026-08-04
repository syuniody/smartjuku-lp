#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""記事ページに共有ボタンを差し込む（べき等。何度実行しても二重にならない）。

    python3 scripts/add_share.py

・X / LINE / Facebook は素のリンク。共有先のURLとタイトルはページごとに埋め込むので、
  JavaScriptが動かない環境でも機能する。
・「リンクをコピー」だけ assets/site.js を使う。
・置き場所は記事末尾のCTAの直前。
"""

from __future__ import annotations

import glob
import html as html_mod
import re
import sys
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parent.parent
MARK = '<div class="share">'
SCRIPT = '<script src="/assets/site.js" defer></script>'


def share_block(url: str, title: str) -> str:
    u, t = quote(url, safe=""), quote(title, safe="")
    x = f"https://x.com/intent/post?text={t}&url={u}"
    line = f"https://social-plugins.line.me/lineit/share?url={u}"
    fb = f"https://www.facebook.com/sharer/sharer.php?u={u}"
    a = 'target="_blank" rel="noopener noreferrer"'
    return f"""        <div class="share">
          <p class="share-label">この記事を共有する</p>
          <div class="share-btns">
            <a class="share-btn sb-x" href="{html_mod.escape(x, quote=True)}" {a}><span class="sv-dot"></span>X</a>
            <a class="share-btn sb-line" href="{html_mod.escape(line, quote=True)}" {a}><span class="sv-dot"></span>LINE</a>
            <a class="share-btn sb-fb" href="{html_mod.escape(fb, quote=True)}" {a}><span class="sv-dot"></span>Facebook</a>
            <button class="share-btn sb-copy" type="button" data-url="{html_mod.escape(url, quote=True)}"><span class="sv-dot"></span><span class="sb-text">リンクをコピー</span></button>
          </div>
        </div>

"""


def patch(path: Path) -> str:
    s = path.read_text(encoding="utf-8")

    canon = re.search(r'<link rel="canonical" href="([^"]+)">', s)
    title = re.search(r'<meta property="og:title" content="([^"]+)">', s)
    if not canon or not title:
        return f"{path}: canonical か og:title が無いのでスキップ"
    url = canon.group(1)
    ttl = html_mod.unescape(title.group(1))

    changed = False

    # 共有ボタン（既にあれば作り直す。URLやタイトルの変更に追随させるため）
    block = share_block(url, ttl)
    if MARK in s:
        s2 = re.sub(r'        <div class="share">.*?</div>\n\n(?=        <div class="article-cta">)',
                    block, s, flags=re.S)
        if s2 != s:
            s, changed = s2, True
    else:
        anchor = '        <div class="article-cta">'
        if anchor not in s:
            return f"{path}: article-cta が無いのでスキップ"
        s = s.replace(anchor, block + anchor, 1)
        changed = True

    # スクリプト
    if SCRIPT not in s:
        s = s.replace("</body>", f"{SCRIPT}\n</body>", 1)
        changed = True

    if changed:
        path.write_text(s, encoding="utf-8")
    return f"{path}: {'更新' if changed else '変更なし'}"


def run() -> tuple[int, int, list[str]]:
    """全記事に共有ボタンを設置する。戻り値: (更新数, 対象数, 警告)

    テンプレートには入れない。★を含むURLがエンコードされて残り、
    書き換え忘れの原因になるため。記事を作ったら build.py が自動で設置する。
    """
    targets: list[Path] = []
    for sec in ("news", "guide", "report", "case"):
        targets += [Path(f) for f in sorted(glob.glob(str(ROOT / sec / "*.html")))
                    if not f.endswith("index.html")]

    updated, warns = 0, []
    for p in targets:
        r = patch(p)
        if r.endswith("更新"):
            updated += 1
        elif "スキップ" in r:
            warns.append(r)
    return updated, len(targets), warns


def main() -> int:
    updated, total, warns = run()
    for w in warns:
        print(" ", w)
    print(f"共有ボタン: {updated} ファイルを更新（対象 {total} ファイル）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
