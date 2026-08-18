#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
スマ塾サイト ビルドスクリプト

やること:
  1. /case /guide /report /news 配下の記事HTMLを走査してメタ情報を抽出
  2. 各セクションの一覧ページ（index.html）を生成
  3. sitemap.xml を生成（トップ・固定ページ・一覧・全記事）

使い方:
  python3 scripts/build.py          # 生成を実行
  python3 scripts/build.py --check  # 生成せず、記事のメタ不備だけ点検

記事側の必須メタ（テンプレートに入っています）:
  <title>...</title>
  <meta name="description" content="...">
  <meta name="sj:category" content="guide">          ← セクションと一致させる
  <meta property="article:published_time" content="2026-08-01">
  <meta property="article:modified_time" content="2026-08-01">   ← 任意
"""

from __future__ import annotations

import argparse
import html
import re
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import add_share  # noqa: E402  （同じ scripts/ 配下）
import make_ogp  # noqa: E402

BASE_URL = "https://smart-juku.syuni.jp"
ROOT = Path(__file__).resolve().parent.parent

# セクション定義（ここを増やせばディレクトリが増える）
SECTIONS = [
    {
        "slug": "case",
        "name": "制作事例",
        "title": "制作事例｜スマ塾が作った学習塾のホームページ",
        "description": "スマ塾が制作した学習塾ホームページの事例集。塾の課題、制作の狙い、公開後の変化までを掲載しています。",
        "lede": "実際にスマ塾が制作した学習塾のホームページです。どんな課題があり、何をどう設計したのかを、塾ごとに具体的に紹介します。",
    },
    {
        "slug": "guide",
        "name": "塾HPの基礎知識",
        "title": "塾HPの基礎知識｜費用・作り方・集客の考え方",
        "description": "学習塾のホームページについて、費用相場・制作方法の選び方・問い合わせを増やす設計を、塾専門の視点で解説します。",
        "lede": "「塾のHPはいくらかかるのか」「何を載せれば問い合わせが来るのか」。塾長からよく聞かれることに、現場の視点で答えます。",
    },
    {
        "slug": "report",
        "name": "調査レポート",
        "title": "調査レポート｜学習塾ホームページの実態調査",
        "description": "学習塾のホームページを対象にした独自調査のレポート。スマホ対応率・料金掲載率・更新頻度などを数値で公開しています。",
        "lede": "スマ塾が独自に集計した一次データを公開します。数値は出典を明記いただければ自由に引用いただけます。",
    },
    {
        "slug": "news",
        "name": "教育ニュース",
        "title": "教育ニュース｜塾経営に関わる制度・政策の解説",
        "description": "学習塾の経営に影響する制度変更・政策・教育トレンドを、塾の現場目線でわかりやすく解説します。",
        "lede": "文部科学省の発表や制度変更のうち、塾経営に関わるものを噛み砕いて解説します。",
    },
]

# トップページ（index.html）の「お役立ち情報」セクションに載せる記事の本数
# （カテゴリの絞り込みタブがあるので、1カテゴリだけ選んでも数本は残る程度にしておく）
READING_LIMIT = 9
READING_START = "<!-- READING:START -->"
READING_END = "<!-- READING:END -->"

# サイトマップに含める固定ページ（トップは別途追加）
STATIC_PAGES = [
    {"path": "privacy.html", "changefreq": "yearly", "priority": "0.3"},
    {"path": "tokushoho.html", "changefreq": "yearly", "priority": "0.3"},
]


# ---------------------------------------------------------------- utilities
def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def meta_content(source: str, *, name: str = None, prop: str = None) -> str | None:
    """<meta name=".." content=".."> / <meta property=".." content=".."> を抽出"""
    key, val = ("name", name) if name else ("property", prop)
    # 属性の順序が逆でも拾えるように2パターン試す
    patterns = [
        rf'<meta\s+{key}=["\']{re.escape(val)}["\']\s+content=["\'](.*?)["\']\s*/?>',
        rf'<meta\s+content=["\'](.*?)["\']\s+{key}=["\']{re.escape(val)}["\']\s*/?>',
    ]
    for p in patterns:
        m = re.search(p, source, re.I | re.S)
        if m:
            return html.unescape(m.group(1)).strip()
    return None


def page_title(source: str) -> str | None:
    m = re.search(r"<title>(.*?)</title>", source, re.I | re.S)
    if not m:
        return None
    t = html.unescape(m.group(1)).strip()
    # 「記事名｜スマ塾」の後半を落として見出し用に
    return re.sub(r"\s*[｜|]\s*スマ塾.*$", "", t).strip()


def jp_date(iso: str) -> str:
    try:
        y, m, d = (int(x) for x in iso.split("-"))
        return f"{y}年{m}月{d}日"
    except Exception:
        return iso


def esc(s: str) -> str:
    return html.escape(s, quote=True)


# ---------------------------------------------------------------- collect
def collect_articles(section: dict) -> tuple[list[dict], list[str]]:
    """セクション配下の記事を集める。戻り値: (記事リスト, 警告リスト)"""
    articles: list[dict] = []
    warnings: list[str] = []
    sec_dir = ROOT / section["slug"]
    if not sec_dir.is_dir():
        return articles, warnings

    for f in sorted(sec_dir.glob("*.html")):
        if f.name == "index.html":
            continue
        src = read(f)
        rel = f"/{section['slug']}/{f.name}"

        title = page_title(src)
        desc = meta_content(src, name="description")
        cat = meta_content(src, name="sj:category")
        pub = meta_content(src, prop="article:published_time")
        mod = meta_content(src, prop="article:modified_time") or pub

        # 未編集テンプレの取り込み防止。★はタイトルに限らずファイル全体で見る
        # （リード文や本文だけ★が残った書きかけを公開してしまわないため）
        if "★" in src:
            where = []
            if title and "★" in title:
                where.append("タイトル")
            if desc and "★" in desc:
                where.append("description")
            if "★" in src.split("<body", 1)[-1]:
                where.append("本文")
            warnings.append(
                f"{rel}: ★が {('・'.join(where) or 'ファイル内')} に残っています（一覧・sitemapから除外）"
            )
            continue
        if not title:
            warnings.append(f"{rel}: <title> がありません（除外）")
            continue
        if not pub:
            warnings.append(f"{rel}: article:published_time がありません（除外）")
            continue
        if cat and cat != section["slug"]:
            warnings.append(f"{rel}: sj:category が '{cat}' でディレクトリと不一致")
        if not desc:
            warnings.append(f"{rel}: description がありません")

        # 画像の代替テキスト。空のまま公開すると、AIにも読み上げにも内容が伝わらない。
        # 自社の記事で他塾に「代替テキストが0%」と指摘している以上、ここは落とせない。
        for tag in re.findall(r"<img[^>]*>", src):
            if "facebook.com/tr" in tag:      # 計測用の1×1画像は対象外
                continue
            m = re.search(r'alt="([^"]*)"', tag)
            if not (m and m.group(1).strip()):
                name = (re.search(r'src="([^"]+)"', tag) or [None, "?"])[1].split("/")[-1]
                warnings.append(f"{rel}: 画像 {name} に alt がありません")
            elif re.search(r"すらら|公式LINE|チャンネル登録|概要欄|プレゼント", m.group(1)):
                warnings.append(f"{rel}: 画像 {m.group(1)[:20]}… の alt に他社の宣伝文が混ざっています")

        # OGP画像は命名規則で決まる。記事側の og:image が一致しているか点検する
        want_ogp = make_ogp.ogp_rel_path(section["slug"], f.name)
        og = meta_content(src, prop="og:image")
        if og and not og.endswith(want_ogp):
            warnings.append(f"{rel}: og:image を {want_ogp} に直してください（現在 {og}）")

        articles.append(
            {
                "url": rel,
                "filename": f.name,
                "title": title,
                "description": desc or "",
                "published": pub,
                "modified": mod,
                "ogp_lead": meta_content(src, name="sj:ogp-lead") or "",
            }
        )

    # 新しい順
    articles.sort(key=lambda a: a["published"], reverse=True)
    return articles, warnings


# ---------------------------------------------------------------- render
def render_index(section: dict, articles: list[dict]) -> str:
    slug, name = section["slug"], section["name"]

    if articles:
        # セクション一覧はカテゴリが自明なので、行ごとのカテゴリ表示はしない。
        # （LPの「お役立ち情報」は複数カテゴリが混ざるので、あちらには残す）
        items = "\n".join(
            f"""        <a class="post-item" href="{esc(a['url'])}">
          <div class="post-meta">
            <time datetime="{esc(a['published'])}">{esc(jp_date(a['published']))}</time>
          </div>
          <h2>{esc(a['title'])}</h2>
          <p>{esc(a['description'])}</p>
        </a>"""
            for a in articles
        )
        list_html = f'      <div class="post-list">\n{items}\n      </div>'
    else:
        list_html = (
            '      <div class="list-empty">\n'
            "        <p>記事を準備しています。もうしばらくお待ちください。</p>\n"
            '        <p><a href="/#contact">ホームページのご相談はこちら</a></p>\n'
            "      </div>"
        )

    # 一覧の構造化データ
    if articles:
        elems = ",\n".join(
            f'      {{ "@type": "ListItem", "position": {i+1}, '
            f'"url": "{BASE_URL}{a["url"]}", "name": {html.escape(a["title"]).__repr__().replace(chr(39), chr(34))} }}'
            for i, a in enumerate(articles)
        )
        itemlist = f"""<script type="application/ld+json">
{{
  "@context": "https://schema.org",
  "@type": "ItemList",
  "name": "{esc(name)}",
  "itemListElement": [
{elems}
  ]
}}
</script>"""
    else:
        itemlist = ""

    return f"""<!DOCTYPE html>
<!-- このファイルは scripts/build.py が自動生成します。直接編集しないでください。 -->
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{esc(section['title'])}｜スマ塾</title>
<meta name="description" content="{esc(section['description'])}">
<meta name="robots" content="index, follow">
<link rel="canonical" href="{BASE_URL}/{slug}/">
<meta property="og:type" content="website">
<meta property="og:site_name" content="スマ塾｜学習塾専門のWeb支援">
<meta property="og:title" content="{esc(section['title'])}">
<meta property="og:description" content="{esc(section['description'])}">
<meta property="og:url" content="{BASE_URL}/{slug}/">
<meta property="og:image" content="{BASE_URL}/assets/ogp.png">
<meta property="og:locale" content="ja_JP">
<meta name="twitter:card" content="summary_large_image">
<link rel="icon" href="/assets/favicon.svg" type="image/svg+xml">
<link rel="apple-touch-icon" href="/assets/apple-touch-icon.png">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Zen+Kaku+Gothic+New:wght@400;500;700;900&family=Shippori+Mincho:wght@500;600;700;800&display=swap" rel="stylesheet">
<link rel="stylesheet" href="/assets/site.css">
<script>
  !function(f,b,e,v,n,t,s)
  {{if(f.fbq)return;n=f.fbq=function(){{n.callMethod?
  n.callMethod.apply(n,arguments):n.queue.push(arguments)}};
  if(!f._fbq)f._fbq=n;n.push=n;n.loaded=!0;n.version='2.0';
  n.queue=[];t=b.createElement(e);t.async=!0;
  t.src=v;s=b.getElementsByTagName(e)[0];
  s.parentNode.insertBefore(t,s)}}(window,document,'script',
  'https://connect.facebook.net/en_US/fbevents.js');
  fbq('init', '2147777948929240');
  fbq('track', 'PageView');
</script>
<noscript><img height="1" width="1" style="display:none" src="https://www.facebook.com/tr?id=2147777948929240&ev=PageView&noscript=1"/></noscript>
<script async src="https://www.googletagmanager.com/gtag/js?id=G-JLH0DEFEX9"></script>
<script>
  window.dataLayer = window.dataLayer || [];
  function gtag(){{dataLayer.push(arguments);}}
  gtag('js', new Date());
  gtag('config', 'G-JLH0DEFEX9');
</script>
<script type="application/ld+json">
{{
  "@context": "https://schema.org",
  "@type": "BreadcrumbList",
  "itemListElement": [
    {{ "@type": "ListItem", "position": 1, "name": "ホーム", "item": "{BASE_URL}/" }},
    {{ "@type": "ListItem", "position": 2, "name": "{esc(name)}" }}
  ]
}}
</script>
{itemlist}
</head>
<body>

<header class="site-header">
  <div class="site-header-in">
    <a class="site-logo" href="/"><span class="dot"></span><span>スマ塾<small>学習塾専門のWeb支援</small></span></a>
    <nav class="site-nav">
      <a href="/case/"{' aria-current="page"' if slug == 'case' else ''}>制作事例</a>
      <a href="/guide/"{' aria-current="page"' if slug == 'guide' else ''}>塾HPの基礎知識</a>
      <a href="/report/"{' aria-current="page"' if slug == 'report' else ''}>調査レポート</a>
      <a href="/news/"{' aria-current="page"' if slug == 'news' else ''}>教育ニュース</a>
    </nav>
    <a class="header-cta" href="/#contact">無料でHP診断を受ける</a>
  </div>
</header>

<main>
  <div class="wrap">
    <nav class="breadcrumb" aria-label="パンくず">
      <ol>
        <li><a href="/">ホーム</a></li>
        <li>{esc(name)}</li>
      </ol>
    </nav>

    <div class="list-head">
      <p class="sec-label">{esc(name)}</p>
      <h1 class="sec-title">{esc(section['title'].split('｜')[0])}</h1>
      <p class="sec-lede">{esc(section['lede'])}</p>
    </div>

{list_html}
  </div>
</main>

<footer class="site-footer">
  <div class="wrap">
    <div class="foot-grid">
      <div class="foot-brand">
        <a class="site-logo" href="/"><span class="dot"></span><span>スマ塾<small style="color:rgba(247,244,237,.55)">学習塾専門のWeb支援</small></span></a>
        <p>個人塾・地域密着塾専門のWeb支援サービス<br>運営：<a href="https://syuni.jp/" target="_blank" rel="noopener noreferrer">合同会社SyUNi</a>（代表：小田 一勲）</p>
      </div>
      <nav class="foot-nav">
        <a href="/case/">制作事例</a>
        <a href="/guide/">塾HPの基礎知識</a>
        <a href="/report/">調査レポート</a>
        <a href="/news/">教育ニュース</a>
        <a href="/#contact">無料相談</a>
      </nav>
    </div>
    <div class="foot-copy">
      <span>© 2026 合同会社SyUNi</span>
      <span>
        <a href="/privacy.html">プライバシーポリシー</a>
        <a href="/tokushoho.html">特定商取引法に基づく表記</a>
      </span>
    </div>
  </div>
</footer>

</body>
</html>
"""


def update_reading(all_sections: list[tuple[dict, list[dict]]]) -> str:
    """トップページの「お役立ち情報」セクションの中身を差し替える。

    READING:START 〜 READING:END の間だけを書き換えるので、
    セクションの見出しやリード文は index.html 側で自由に編集できる。
    """
    index = ROOT / "index.html"
    if not index.exists():
        return "index.html が見つかりません（お役立ち情報セクションはスキップ）"

    src = read(index)
    n_start, n_end = src.count(READING_START), src.count(READING_END)
    if n_start == 0 or n_end == 0:
        return "index.html に READING のマーカーがありません（お役立ち情報セクションはスキップ）"
    if n_start != 1 or n_end != 1:
        # マーカー文字列が説明コメント等にも書かれていると、置換範囲がずれて壊れる
        return (
            f"index.html の READING マーカーが複数あります"
            f"（START {n_start} / END {n_end}）。1組だけにしてください（スキップ）"
        )

    # 全セクションを混ぜて新しい順に
    merged: list[dict] = []
    for section, articles in all_sections:
        for a in articles:
            merged.append({**a, "cat": section["name"], "slug": section["slug"]})
    merged.sort(key=lambda a: a["published"], reverse=True)
    merged = merged[:READING_LIMIT]

    if merged:
        # 表示中の記事に存在するカテゴリだけタブにする（空振りするタブを作らない）
        present = [s for s in SECTIONS if any(a["slug"] == s["slug"] for a in merged)]
        tabs = "\n".join(
            f'          <button type="button" class="read-tab" data-cat="{esc(s["slug"])}" '
            f'aria-pressed="false">{esc(s["name"])}</button>'
            for s in present
        )
        tabs_html = (
            '        <div class="read-tabs" role="group" aria-label="カテゴリで絞り込む">\n'
            '          <button type="button" class="read-tab" data-cat="all" aria-pressed="true">すべて</button>\n'
            f"{tabs}\n        </div>"
        )
        items = "\n".join(
            f"""          <a class="read-item rv" data-cat="{esc(a['slug'])}" href="{esc(a['url'])}">
            <div class="read-meta">
              <span class="read-cat">{esc(a['cat'])}</span>
              <time datetime="{esc(a['published'])}">{esc(jp_date(a['published']))}</time>
            </div>
            <h3>{esc(a['title'])}</h3>
            <p>{esc(a['description'])}</p>
          </a>"""
            for a in merged
        )
        block = (
            f"{tabs_html}\n"
            f'        <div class="read-list">\n{items}\n        </div>\n'
            f'        <p class="read-empty" hidden>このカテゴリの記事はまだありません。</p>'
        )
    else:
        block = ""

    new = re.sub(
        re.escape(READING_START) + r".*?" + re.escape(READING_END),
        f"{READING_START}\n{block}\n      {READING_END}",
        src,
        flags=re.S,
    )
    if new != src:
        index.write_text(new, encoding="utf-8")
    return f"更新: index.html のお役立ち情報セクション（{len(merged)} 本）"


def render_sitemap(all_sections: list[tuple[dict, list[dict]]]) -> str:
    today = date.today().isoformat()
    rows = [
        f"  <url>\n    <loc>{BASE_URL}/</loc>\n    <lastmod>{today}</lastmod>\n"
        f"    <changefreq>monthly</changefreq>\n    <priority>1.0</priority>\n  </url>"
    ]

    for section, articles in all_sections:
        # 記事が無いセクションはサイトマップに載せない（空ページの登録を避ける）
        if not articles:
            continue
        newest = max(a["modified"] for a in articles)
        rows.append(
            f"  <url>\n    <loc>{BASE_URL}/{section['slug']}/</loc>\n"
            f"    <lastmod>{newest}</lastmod>\n"
            f"    <changefreq>weekly</changefreq>\n    <priority>0.8</priority>\n  </url>"
        )
        for a in articles:
            rows.append(
                f"  <url>\n    <loc>{BASE_URL}{a['url']}</loc>\n"
                f"    <lastmod>{a['modified']}</lastmod>\n"
                f"    <changefreq>monthly</changefreq>\n    <priority>0.7</priority>\n  </url>"
            )

    for p in STATIC_PAGES:
        if not (ROOT / p["path"]).exists():
            continue
        rows.append(
            f"  <url>\n    <loc>{BASE_URL}/{p['path']}</loc>\n"
            f"    <lastmod>{today}</lastmod>\n"
            f"    <changefreq>{p['changefreq']}</changefreq>\n"
            f"    <priority>{p['priority']}</priority>\n  </url>"
        )

    body = "\n".join(rows)
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<!-- scripts/build.py が自動生成します -->
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
{body}
</urlset>
"""


# ---------------------------------------------------------------- main
def main() -> int:
    ap = argparse.ArgumentParser(description="スマ塾サイトの一覧ページとsitemapを生成します")
    ap.add_argument("--check", action="store_true", help="生成せず点検のみ")
    args = ap.parse_args()

    all_sections: list[tuple[dict, list[dict]]] = []
    all_warnings: list[str] = []
    total = 0

    for section in SECTIONS:
        (ROOT / section["slug"]).mkdir(exist_ok=True)
        articles, warns = collect_articles(section)
        all_sections.append((section, articles))
        all_warnings += warns
        total += len(articles)
        print(f"  {section['slug']:<7} 記事 {len(articles)} 本")

    if args.check:
        print(f"\n合計 {total} 本")
        if all_warnings:
            print("\n[要確認]")
            for w in all_warnings:
                print(f"  - {w}")
            return 1
        print("問題は見つかりませんでした。")
        return 0

    for section, articles in all_sections:
        out = ROOT / section["slug"] / "index.html"
        out.write_text(render_index(section, articles), encoding="utf-8")
        print(f"  生成: /{section['slug']}/index.html")

    ogp_items = [
        {
            "section": section["slug"],
            "filename": a["filename"],
            "title": a["title"],
            "category": section["name"],
            "lead": a["ogp_lead"],
        }
        for section, articles in all_sections
        for a in articles
    ]
    made, ogp_warns = make_ogp.build(ogp_items)
    all_warnings += ogp_warns
    print(f"  生成: OGP画像 {made} 枚")

    n_share, n_total, share_warns = add_share.run()
    all_warnings += share_warns
    print(f"  共有ボタン: {n_share}/{n_total} ファイルを更新")

    print(f"  {update_reading(all_sections)}")

    sm = ROOT / "sitemap.xml"
    sm.write_text(render_sitemap(all_sections), encoding="utf-8")
    print(f"  生成: sitemap.xml")

    print(f"\n完了（記事 {total} 本）")
    if all_warnings:
        print("\n[要確認]")
        for w in all_warnings:
            print(f"  - {w}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
