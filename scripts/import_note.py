#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""noteの記事を /news/ の記事HTMLに取り込む。

    python3 scripts/import_note.py <noteキー> <slug>
    例) python3 scripts/import_note.py n433e1a8030c9 tsuuchihyou-haishi

やること
  1. note の公開APIから本文HTMLを取得
  2. 画像を assets/news/<slug>/ に保存し、src を自社パスへ差し替え
  3. サイトの記事テンプレートに流し込んで news/<slug>.html を出力

出力されたファイルには ★ が2か所残ります。
  ・article-lede …… 塾長向けのリード文
  ・「塾への影響」…… 記事末尾の追記セクション
この2か所を書いてから `python3 scripts/build.py` を実行してください。
★が残っている記事は一覧・sitemapから自動で除外されるので、公開事故は起きません。

noteの原文には手を加えません（本文はそのまま移します）。
"""

from __future__ import annotations

import html as html_mod
import json
import re
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BASE_URL = "https://smart-juku.syuni.jp"
UA = {"User-Agent": "Mozilla/5.0"}


def fetch_json(url: str) -> dict:
    return json.load(urllib.request.urlopen(urllib.request.Request(url, headers=UA)))


SECTION_NAMES = {"case": "制作事例", "guide": "塾HPの基礎知識",
                 "report": "調査レポート", "news": "教育ニュース"}


def nav_html(section: str) -> str:
    """ヘッダーナビ。現在地に aria-current を付ける"""
    rows = []
    for slug, name in SECTION_NAMES.items():
        cur = ' aria-current="page"' if slug == section else ""
        rows.append(f'<a href="/{slug}/"{cur}>{name}</a>')
    return "\n      ".join(rows)


MAX_W = 1200      # 記事の本文幅（--measure 720px）の想定倍率で十分
JPEG_QUALITY = 85


def download(url: str, dest: Path) -> None:
    """取得してJPEGに正規化する。noteの図版は1点400KB前後あり、そのままだと重い"""
    dest.parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA)) as r:
        raw = r.read()

    try:
        import io

        from PIL import Image

        im = Image.open(io.BytesIO(raw))
        if im.width > MAX_W:
            im = im.resize((MAX_W, round(MAX_W * im.height / im.width)), Image.LANCZOS)
        im.convert("RGB").save(
            dest, "JPEG", quality=JPEG_QUALITY, optimize=True, progressive=True
        )
    except Exception:
        # Pillowが無い・変換できない形式のときは、取得したものをそのまま置く
        dest.write_bytes(raw)


def convert_body(body: str, slug: str, embeds: list[dict] | None = None, section: str = "news") -> tuple[str, list[dict]]:
    """note本文HTMLを記事本文に変換し、画像を自社へ移す"""
    images: list[dict] = []
    emap = {e["key"]: e for e in (embeds or []) if e.get("url")}

    # note の埋め込み（YouTube等）は空の <figure> になるので、リンクに置き換える
    def repl_embed(m: re.Match) -> str:
        e = emap.get(m.group(1))
        if not e:
            return ""
        url = html_mod.escape(e["url"], quote=True)
        # note側に置いた自社サイトへの誘導カードは、記事末のCTAと重複するので落とす
        if "smart-juku.syuni.jp" in url:
            return ""
        svc = (e.get("service") or "").lower()
        if svc == "youtube":
            label = "この内容を動画で見る（YouTube・Edu-NEWS）"
        elif svc in ("twitter", "x") or "://x.com" in url or "twitter.com" in url:
            label = "引用元のXの投稿を見る"
        else:
            label = "引用元を見る"
        return (
            '<p class="video-link"><a href="' + url + '" target="_blank" rel="noopener noreferrer">'
            + label + "</a></p>"
        )

    body = re.sub(
        r'<figure[^>]*embedded-content-key="([^"]+)"[^>]*>.*?</figure>',
        repl_embed, body, flags=re.S,
    )

    def repl_img(m: re.Match) -> str:
        src = m.group(1)
        # note の画像URLは末尾にサイズ指定のクエリが付くことがある
        name = f"{len(images) + 1:02d}.jpg"
        rel = f"/assets/{section}/{slug}/{name}"
        try:
            download(src, ROOT / rel.lstrip("/"))
            images.append({"no": len(images) + 1, "src": src, "local": rel})
        except Exception as e:
            images.append({"no": len(images) + 1, "src": src, "local": None, "error": str(e)})
            return ""
        return f'<img src="{rel}" alt="" loading="lazy" decoding="async">'

    out = re.sub(r'<img[^>]+src="([^"]+)"[^>]*>', repl_img, body)
    # noteの独自属性や空要素を落とす（video-link クラスだけは残す）
    out = re.sub(r'\s(name|id|style|data-[a-z-]+|embedded-[a-z-]+)="[^"]*"', "", out)
    out = re.sub(r'\sclass="(?!video-link)[^"]*"', "", out)

    # ここから先は属性を落としたあとに実行する（noteの<p>には属性が付いているため）
    # note側に置いていたスマ塾の宣伝セクションは、記事末のCTAと重複するので丸ごと落とす
    out = re.sub(
        r"<h2>[^<]*(?:スマ塾|塾の発信|無料HP診断)[^<]*</h2>.*?(?=<h2>|$)",
        "", out, flags=re.S,
    )
    # 取りこぼした自社サイトへのリンク段落も落とす
    out = re.sub(
        r'<p>[^<]*<a href="https://smart-juku\.syuni\.jp[^"]*"[^>]*>.*?</a>[^<]*</p>',
        "", out, flags=re.S,
    )
    out = re.sub(r"<figcaption>\s*</figcaption>", "", out)
    out = re.sub(r"<p>\s*(<br\s*/?>)?\s*</p>", "", out)

    # 同じ動画リンクが連続して入っている記事があるので、重複を落とす
    seen_video = set()

    def dedupe_video(m: re.Match) -> str:
        if m.group(0) in seen_video:
            return ""
        seen_video.add(m.group(0))
        return m.group(0)

    out = re.sub(r'<p class="video-link">.*?</p>', dedupe_video, out, flags=re.S)

    # note本文にマークダウン記法がそのまま残っていることがあるので、太字に直す
    out = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", out)
    # 空の見出しを落とす
    out = re.sub(r"<h([23])>\s*</h\1>", "", out)

    # note末尾のハッシュタグ段落を落とす
    out = re.sub(r"<p>(?:\s|&nbsp;|<br\s*/?>)*(?:#[^\s<#]+(?:\s|&nbsp;)*)+</p>", "", out)

    # h3だけで書かれた記事は、見出し階層が h1 → h3 と飛ぶので h2 に繰り上げる
    if "<h2>" not in out and "<h3>" in out:
        out = out.replace("<h3>", "<h2>").replace("</h3>", "</h2>")

    # 見出しタグを使わず「太字だけの段落」で見出しを表している記事がある。
    # 見出しが1つも無い場合に限り、太字だけの短い段落をh2として扱う。
    if "<h2>" not in out and "<h3>" not in out:
        def strong_to_h2(m: re.Match) -> str:
            text = m.group(1)
            plain = re.sub(r"<[^>]+>", "", text).strip()
            if not plain or len(plain) > 60 or plain.endswith("。"):
                return m.group(0)
            return f"<h2>{plain}</h2>"

        out = re.sub(r"<p><strong>(.*?)</strong>\s*(?:<br\s*/?>)?\s*</p>",
                     strong_to_h2, out, flags=re.S)
    # ★はテンプレートの未編集マーカーに使っているので、本文中の★は実体参照に逃がす
    # （build.py が本文の★を「書きかけ」と誤判定するのを防ぐ）
    out = out.replace("★", "&#9733;")

    out = re.sub(r"\n{3,}", "\n\n", out)
    # 記事本文のインデントに合わせる
    out = "\n".join("        " + ln.strip() for ln in out.splitlines() if ln.strip())
    return out, images


TEMPLATE = """<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">

<title>{title}｜スマ塾</title>
<meta name="description" content="★この記事の要点を、塾長にとっての意味を含めて2文で。全角120字前後。">
<meta name="robots" content="index, follow">

<link rel="canonical" href="{base}/{sec}/{slug}.html">

<meta name="sj:category" content="{sec}">
<meta property="article:published_time" content="{date}">
<meta property="article:modified_time" content="{today}">

<!-- OGP -->
<meta property="og:type" content="article">
<meta property="og:site_name" content="スマ塾｜学習塾専門のWeb支援">
<meta property="og:title" content="{title}">
<meta property="og:description" content="★この記事の要点を、塾長にとっての意味を含めて2文で。">
<meta property="og:url" content="{base}/{sec}/{slug}.html">
<meta property="og:image" content="{base}/assets/ogp/{sec}-{slug}.png">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta name="sj:ogp-lead" content="★共有時に出す一行（数値があれば入れる）">
<meta property="og:locale" content="ja_JP">
<meta name="twitter:card" content="summary_large_image">

<link rel="icon" href="/assets/favicon.svg" type="image/svg+xml">
<link rel="apple-touch-icon" href="/assets/apple-touch-icon.png">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Zen+Kaku+Gothic+New:wght@400;500;700;900&family=Shippori+Mincho:wght@500;600;700;800&display=swap" rel="stylesheet">
<link rel="stylesheet" href="/assets/site.css">

<!-- Meta Pixel -->
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
<!-- Google Analytics 4 -->
<script async src="https://www.googletagmanager.com/gtag/js?id=G-JLH0DEFEX9"></script>
<script>
  window.dataLayer = window.dataLayer || [];
  function gtag(){{dataLayer.push(arguments);}}
  gtag('js', new Date());
  gtag('config', 'G-JLH0DEFEX9');
</script>

<!-- 構造化データ：Article -->
<script type="application/ld+json">
{{
  "@context": "https://schema.org",
  "@type": "Article",
  "headline": "{title}",
  "description": "★この記事の要点を2文で。",
  "datePublished": "{date}",
  "dateModified": "{today}",
  "inLanguage": "ja",
  "mainEntityOfPage": {{ "@type": "WebPage", "@id": "{base}/{sec}/{slug}.html" }},
  "image": "{base}/assets/ogp/{sec}-{slug}.png",
  "author": {{
    "@type": "Person",
    "name": "小田 一勲",
    "jobTitle": "合同会社SyUNi 代表",
    "url": "{base}/#person"
  }},
  "publisher": {{
    "@type": "Organization",
    "name": "スマ塾（合同会社SyUNi）",
    "url": "{base}/",
    "logo": {{ "@type": "ImageObject", "url": "{base}/assets/ogp.png" }}
  }}
}}
</script>

<!-- 構造化データ：パンくず -->
<script type="application/ld+json">
{{
  "@context": "https://schema.org",
  "@type": "BreadcrumbList",
  "itemListElement": [
    {{ "@type": "ListItem", "position": 1, "name": "ホーム", "item": "{base}/" }},
    {{ "@type": "ListItem", "position": 2, "name": "{sec_name}", "item": "{base}/{sec}/" }},
    {{ "@type": "ListItem", "position": 3, "name": "{title}" }}
  ]
}}
</script>
</head>
<body>

<header class="site-header">
  <div class="site-header-in">
    <a class="site-logo" href="/"><span class="dot"></span><span>スマ塾<small>学習塾専門のWeb支援</small></span></a>
    <nav class="site-nav">
      {nav}
    </nav>
    <a class="header-cta" href="/#contact">無料でHP診断を受ける</a>
  </div>
</header>

<main>
  <div class="wrap">

    <nav class="breadcrumb" aria-label="パンくず">
      <ol>
        <li><a href="/">ホーム</a></li>
        <li><a href="/{sec}/">{sec_name}</a></li>
        <li>{crumb}</li>
      </ol>
    </nav>

    <article>
      <header class="article-head">
        <div class="post-meta">
          <span class="post-cat cat-{sec}">{sec_name}</span>
          <time datetime="{date}">{date_jp}</time>
        </div>
        <h1 class="article-title">{title}</h1>
        <p class="article-lede">★塾長向けのリード文。この制度変更が塾の何に効くのかを2〜3文で。</p>
      </header>

      <div class="article-body plain-strong">

{body}

        <h2>この記事は塾にどう効くか</h2>
        <div class="answer">
          <p>★結論を1〜2文で。</p>
        </div>

        <h3>保護者への説明材料になるか</h3>
        <p>★面談や保護者会でどう使えるか。</p>

        <h3>指導・カリキュラムへの影響</h3>
        <p>★教える中身や進め方が変わるか。変わらないなら、そう書く。</p>

        <h3>発信のネタとして使えるか</h3>
        <p>★塾のブログやLINEで扱うときの切り口。</p>

        <div class="article-cta">
          <h2>塾のホームページ、今のままで大丈夫か診断します</h2>
          <p>制度の変化を保護者に伝える場としても、ホームページは使えます。スマホ表示・問い合わせ導線・情報の鮮度を、塾専門の視点で無料チェックします。</p>
          <a class="btn" href="/#contact">無料でHP診断を受ける</a>
        </div>
      </div>
    </article>

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


def main() -> int:
    if len(sys.argv) < 3:
        print(__doc__)
        return 1
    key, slug = sys.argv[1], sys.argv[2]
    section = sys.argv[3] if len(sys.argv) > 3 else "news"

    d = fetch_json(f"https://note.com/api/v3/notes/{key}").get("data", {})
    title = html_mod.unescape(d.get("name") or "")
    pub = (d.get("publish_at") or "")[:10]
    body_src = d.get("body") or ""
    if not body_src:
        print(f"本文が取得できませんでした（{key}）")
        return 1

    body, images = convert_body(body_src, slug, d.get("embedded_contents") or [], section)
    y, m, dd = pub.split("-")
    out = TEMPLATE.format(
        sec=section,
        sec_name=SECTION_NAMES[section],
        nav=nav_html(section),
        title=html_mod.escape(title, quote=True),
        crumb=html_mod.escape(title[:24], quote=True),
        slug=slug,
        date=pub,
        today=pub,
        date_jp=f"{int(y)}年{int(m)}月{int(dd)}日",
        base=BASE_URL,
        body=body,
    )
    dest = ROOT / section / f"{slug}.html"
    dest.parent.mkdir(exist_ok=True)
    dest.write_text(out, encoding="utf-8")

    print(f"作成: {section}/{slug}.html  「{title}」  公開日 {pub}")
    print(f"画像: {len([i for i in images if i['local']])} 点を assets/{section}/{slug}/ に保存")
    for i in images:
        mark = i["local"] or f"取得失敗（{i.get('error')}）"
        print(f"   {i['no']:>2}. {mark}\n       元: {i['src']}")
    print("\n★（リード文・description・末尾の塾への影響）を埋めてから build.py を実行してください。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
