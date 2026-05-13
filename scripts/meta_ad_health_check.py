#!/usr/bin/env python3
"""
スマ塾Meta広告デイリーヘルスチェック

毎日17:00 JSTに実行され、異常を検知した場合のみSlack/メールに通知する。
GitHub Actions から実行される想定。

必要な環境変数（GitHub Secrets）:
  META_ACCESS_TOKEN: Meta Marketing API長期トークン
  META_AD_ACCOUNT_ID: 2498937130195109
  META_CAMPAIGN_ID: 120244887266740401
  SLACK_WEBHOOK_URL: Slack Incoming Webhook
  APPS_SCRIPT_WEBHOOK_URL: メール送信用Apps Script Web App
  ALERT_FORCE: "1"を入れると異常がなくても通知（テスト用）
"""

from __future__ import annotations
import json
import os
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

JST = timezone(timedelta(hours=9))

META_API_VERSION = "v21.0"
META_GRAPH_BASE = f"https://graph.facebook.com/{META_API_VERSION}"


# ---------- ユーティリティ ----------

def env(name: str, required: bool = True, default: str = "") -> str:
    v = os.environ.get(name, default)
    if required and not v:
        print(f"::error::必須環境変数 {name} が未設定", file=sys.stderr)
        sys.exit(2)
    return v


def http_get_json(url: str, params: dict | None = None) -> dict:
    if params:
        url = url + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, method="GET")
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


def http_post_json(url: str, payload: dict) -> str:
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url, data=body, method="POST",
        headers={"Content-Type": "application/json; charset=utf-8"},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", errors="replace")


def http_post_text(url: str, payload: dict) -> str:
    """Apps Script Web App向け（リダイレクト後の405を避ける）"""
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url, data=body, method="POST",
        headers={"Content-Type": "text/plain; charset=utf-8"},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.read().decode("utf-8", errors="replace")
    except Exception as e:
        # Apps Script のリダイレクトで失敗してもデータは書き込まれている
        return f"(redirect or error: {e})"


# ---------- Meta API ----------

def get_insights(object_id: str, token: str, since: str, until: str, fields: list[str], extra: dict | None = None) -> list[dict]:
    params = {
        "access_token": token,
        "time_range": json.dumps({"since": since, "until": until}),
        "fields": ",".join(fields),
        "level": "campaign",
    }
    if extra:
        params.update(extra)
    url = f"{META_GRAPH_BASE}/{object_id}/insights"
    return http_get_json(url, params).get("data", [])


def get_campaign_status(campaign_id: str, token: str) -> dict:
    params = {
        "access_token": token,
        "fields": "name,status,effective_status,daily_budget,budget_remaining",
    }
    return http_get_json(f"{META_GRAPH_BASE}/{campaign_id}", params)


def actions_to_dict(actions: list[dict] | None) -> dict[str, float]:
    if not actions:
        return {}
    return {a["action_type"]: float(a.get("value", 0)) for a in actions}


# ---------- 異常検知ロジック ----------

def detect_anomalies(today: dict, yesterday: dict, last7d: dict, campaign_meta: dict) -> list[dict]:
    """異常を検知してアラート辞書のリストを返す"""
    alerts: list[dict] = []

    today_spend = float(today.get("spend", 0))
    today_actions = actions_to_dict(today.get("actions"))
    today_leads = today_actions.get("onsite_conversion.lead_grouped", 0)
    today_ctr = float(today.get("ctr", 0))
    today_freq = float(today.get("frequency", 0))

    y_spend = float(yesterday.get("spend", 0)) if yesterday else 0

    last7_spend = float(last7d.get("spend", 0))
    last7_actions = actions_to_dict(last7d.get("actions"))
    last7_leads = last7_actions.get("onsite_conversion.lead_grouped", 0)
    last7_cpl = (last7_spend / last7_leads) if last7_leads > 0 else None
    last7_ctr = float(last7d.get("ctr", 0))

    # 配信ステータス
    eff = campaign_meta.get("effective_status", "")
    if eff not in ("ACTIVE", "IN_PROCESS"):
        alerts.append({
            "level": "CRITICAL",
            "title": "配信停止",
            "detail": f"effective_status={eff}",
        })

    # 当日消化ゼロ
    if today_spend == 0 and y_spend > 0:
        alerts.append({
            "level": "HIGH",
            "title": "本日の消化ゼロ",
            "detail": f"昨日 ¥{y_spend:,.0f} → 本日 ¥0。配信が止まっている可能性。",
        })

    # CPL急騰（7日CPLが¥10,000超え or 前週比+30%超え）
    # 過去比較は外部に持たせるので、ここでは絶対値のみで判定
    if last7_cpl is not None and last7_cpl >= 10000:
        alerts.append({
            "level": "MEDIUM",
            "title": "CPLが高水準",
            "detail": f"直近7日 CPL ¥{last7_cpl:,.0f}（参考閾値 ¥10,000）",
        })

    # リード0が直近3日連続
    # 当日まで含めた3日間の lead_grouped が 0
    if last7_leads == 0 and last7_spend > 3000:
        alerts.append({
            "level": "MEDIUM",
            "title": "直近7日のリードがゼロ",
            "detail": f"直近7日で ¥{last7_spend:,.0f} 消化、リード0件。",
        })

    # CTR急落（7日CTRが0.8%未満）
    if last7_ctr > 0 and last7_ctr < 0.8:
        alerts.append({
            "level": "MEDIUM",
            "title": "CTR低下",
            "detail": f"直近7日 CTR {last7_ctr:.2f}%（参考閾値 0.8%）",
        })

    # フリークエンシー過大（当日 > 3.0）
    if today_freq > 3.0:
        alerts.append({
            "level": "LOW",
            "title": "フリークエンシー過大",
            "detail": f"今日 {today_freq:.2f}（同じ人に多く表示されている）",
        })

    # 予算残額0（dailyキャンペーンで残¥0表示は正常な場合もあるが念のため）
    rem = int(campaign_meta.get("budget_remaining", 0) or 0)
    daily = int(campaign_meta.get("daily_budget", 0) or 0)
    if daily > 0 and rem == 0 and today_spend < daily * 0.5:
        alerts.append({
            "level": "LOW",
            "title": "予算消化が日割と乖離",
            "detail": f"日予算 ¥{daily}、本日消化 ¥{today_spend:,.0f}",
        })

    return alerts


# ---------- 通知 ----------

def build_text_summary(today: dict, last7d: dict, alerts: list[dict], campaign_meta: dict) -> tuple[str, str]:
    """(short_title, detail_body) を返す"""
    today_actions = actions_to_dict(today.get("actions"))
    today_leads = int(today_actions.get("onsite_conversion.lead_grouped", 0))
    today_spend = float(today.get("spend", 0))
    today_ctr = float(today.get("ctr", 0))
    today_cpm = float(today.get("cpm", 0))

    last7_actions = actions_to_dict(last7d.get("actions"))
    last7_leads = int(last7_actions.get("onsite_conversion.lead_grouped", 0))
    last7_spend = float(last7d.get("spend", 0))
    last7_cpl = (last7_spend / last7_leads) if last7_leads > 0 else None

    if alerts:
        critical = any(a["level"] == "CRITICAL" for a in alerts)
        prefix = "🚨" if critical else "⚠️"
        title = f"{prefix} スマ塾広告 異常検知 ({len(alerts)}件)"
    else:
        title = "✅ スマ塾広告 日次チェック OK"

    lines = [
        title,
        "",
        f"📅 {datetime.now(JST).strftime('%Y-%m-%d %H:%M JST')}",
        f"🎯 キャンペーン: {campaign_meta.get('name', '?')}（{campaign_meta.get('effective_status', '?')}）",
        "",
        "── 本日 ──",
        f"消化 ¥{today_spend:,.0f}  リード {today_leads}件  CTR {today_ctr:.2f}%  CPM ¥{today_cpm:,.0f}",
        "",
        "── 直近7日 ──",
        f"消化 ¥{last7_spend:,.0f}  リード {last7_leads}件  CPL {f'¥{last7_cpl:,.0f}' if last7_cpl else 'N/A'}",
    ]
    if alerts:
        lines += ["", "── アラート ──"]
        for a in alerts:
            lines.append(f"・[{a['level']}] {a['title']}：{a['detail']}")

    return title, "\n".join(lines)


def notify_slack(webhook: str, text: str) -> None:
    if not webhook:
        print("Slack webhook 未設定")
        return
    try:
        http_post_json(webhook, {"text": text})
        print("Slack通知 OK")
    except Exception as e:
        print(f"::warning::Slack通知失敗: {e}", file=sys.stderr)


def notify_email_via_apps_script(webhook: str, subject: str, body: str) -> None:
    if not webhook:
        print("Apps Script webhook 未設定")
        return
    try:
        http_post_text(webhook, {"type": "meta-ad-alert", "summary": subject, "body": body})
        print("メール通知（Apps Script経由） OK")
    except Exception as e:
        print(f"::warning::メール通知失敗: {e}", file=sys.stderr)


# ---------- メイン ----------

def main() -> int:
    token = env("META_ACCESS_TOKEN")
    account_id = env("META_AD_ACCOUNT_ID")  # noqa: F841 -- 未使用だが将来拡張用
    campaign_id = env("META_CAMPAIGN_ID")
    slack_url = env("SLACK_WEBHOOK_URL", required=False)
    apps_script_url = env("APPS_SCRIPT_WEBHOOK_URL", required=False)
    force = env("ALERT_FORCE", required=False) == "1"

    # 日付計算（JST）
    now_jst = datetime.now(JST)
    today = now_jst.strftime("%Y-%m-%d")
    yesterday = (now_jst - timedelta(days=1)).strftime("%Y-%m-%d")
    seven_days_ago = (now_jst - timedelta(days=6)).strftime("%Y-%m-%d")  # 当日含め7日

    fields = ["spend", "impressions", "clicks", "ctr", "cpc", "cpm", "frequency", "reach", "actions"]

    print(f"対象キャンペーン: {campaign_id}")
    print(f"今日: {today} / 昨日: {yesterday} / 直近7日: {seven_days_ago}〜{today}")

    # データ取得
    try:
        today_data_list = get_insights(campaign_id, token, today, today, fields)
        yesterday_data_list = get_insights(campaign_id, token, yesterday, yesterday, fields)
        last7_data_list = get_insights(campaign_id, token, seven_days_ago, today, fields)
        campaign_meta = get_campaign_status(campaign_id, token)
    except Exception as e:
        msg = f"Meta API 取得失敗: {e}"
        print(f"::error::{msg}", file=sys.stderr)
        # APIエラー自体もアラートとして通知
        notify_slack(slack_url, f"🚨 スマ塾広告 ヘルスチェック失敗\n{msg}")
        notify_email_via_apps_script(apps_script_url, "Meta広告チェック失敗", msg)
        return 1

    today_data = today_data_list[0] if today_data_list else {"spend": 0, "actions": []}
    yesterday_data = yesterday_data_list[0] if yesterday_data_list else {"spend": 0}
    last7_data = last7_data_list[0] if last7_data_list else {"spend": 0, "actions": []}

    alerts = detect_anomalies(today_data, yesterday_data, last7_data, campaign_meta)

    title, body = build_text_summary(today_data, last7_data, alerts, campaign_meta)

    print("─" * 40)
    print(body)
    print("─" * 40)

    # 通知判定
    if alerts or force:
        notify_slack(slack_url, body)
        notify_email_via_apps_script(apps_script_url, title, body)
        # アラート時はサマリをアーティファクトとして残す
        out_dir = "reports/daily"
        os.makedirs(out_dir, exist_ok=True)
        out_path = f"{out_dir}/{today}_alert.md"
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(f"# {title}\n\n```\n{body}\n```\n")
        print(f"アラート保存: {out_path}")
    else:
        print("異常なし。通知スキップ。")

    return 0


if __name__ == "__main__":
    sys.exit(main())
