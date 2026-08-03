#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""塾HP診断バッチ（診断結果*.json）を集計し、記事に載せる数値を出す。

使い方:  python3 scripts/aggregate_shindan.py

データの所在:
  Google Drive「001.おまけの学校/12_スマ塾（HP）」配下に散在する 診断結果*.json
  1塾1ディレクトリ。同一ディレクトリに複数版がある場合は _v2 を優先。

集計上の注意（実データを見て判明した揺れ）:
  - 評価記号は ◎ / ◯(U+25EF LARGE CIRCLE) / △ / ✕(U+2715) / ×(U+00D7) の5種類。
    ◯ を「○」(U+25CB) と取り違えると大量に取りこぼすので CANON/GOOD/BAD で明示的に扱う。
  - 項目名に2系統の表記ゆれがある（例「スマホ表示」/「スマートフォン表示」）。
    CANON で正規化して初めて全40塾が揃う。
"""
import json, glob, os
from collections import defaultdict, Counter

ROOT = os.path.expanduser(
    "~/Library/CloudStorage/GoogleDrive-kazuhiro-oda@surala.jp/マイドライブ"
    "/001.おまけの学校/12_スマ塾（HP）"
)

# 項目名の表記ゆれ → 正規名
CANON = {
    "スマホ表示": "スマホ表示",                      "スマートフォン表示": "スマホ表示",
    "ファーストビュー": "ファーストビュー",          "ファーストビュー（第一印象）": "ファーストビュー",
    "問い合わせ導線": "問い合わせ導線",              "お問い合わせ導線": "問い合わせ導線",
    "情報の鮮度": "情報の鮮度",                      "更新頻度・鮮度": "情報の鮮度",
    "塾選びの必須情報": "必須情報(料金・実績)",      "必須情報（料金・実績）": "必須情報(料金・実績)",
    "信頼要素": "信頼要素",                          "信頼要素（顔・氏名・声）": "信頼要素",
    "検索・技術基盤": "検索・技術基盤",              "技術基盤（ドメイン・SEO）": "検索・技術基盤",
}
ORDER = ["スマホ表示", "ファーストビュー", "問い合わせ導線", "情報の鮮度",
         "必須情報(料金・実績)", "信頼要素", "検索・技術基盤"]
GOOD = {"◎", "◯"}
BAD = {"△", "✕", "×"}


def load():
    """1塾1件に正規化して読み込む（同一ディレクトリは _v2 優先）。"""
    by_dir = {}
    for f in glob.glob(os.path.join(ROOT, "**", "診断結果*.json"), recursive=True):
        d = os.path.dirname(f)
        if d not in by_dir or "_v2" in os.path.basename(f):
            by_dir[d] = f
    out = []
    for f in by_dir.values():
        try:
            j = json.load(open(f, encoding="utf-8"))
        except Exception:
            continue
        if j.get("items"):
            out.append(j)
    return out


def main():
    data = load()
    agg = defaultdict(Counter)
    for j in data:
        for it in j["items"]:
            name = CANON.get((it.get("name") or "").strip())
            grade = it.get("grade")
            if name and grade:
                agg[name][grade] += 1

    print(f"対象塾数: {len(data)}\n")
    print(f"{'項目':<20}{'n':>4}{'◎':>4}{'◯':>4}{'△':>4}{'✕系':>5}   課題あり率")
    print("-" * 64)
    for name in ORDER:
        c = agg[name]
        n = sum(c.values())
        if not n:
            continue
        bad = sum(c[g] for g in BAD)
        print(f"{name:<20}{n:>4}{c['◎']:>4}{c['◯']:>4}{c['△']:>4}"
              f"{c['✕'] + c['×']:>5}   {bad / n * 100:5.1f}%")

    scores = sorted(j["score"] for j in data if isinstance(j.get("score"), int))
    if scores:
        under70 = sum(1 for s in scores if s < 70)
        print(f"\n総合スコア: n={len(scores)} 平均{sum(scores) / len(scores):.1f}点 "
              f"中央値{scores[len(scores) // 2]}点 範囲{min(scores)}〜{max(scores)}")
        print(f"70点未満: {under70}件 ({under70 / len(scores) * 100:.0f}%)")


if __name__ == "__main__":
    main()
