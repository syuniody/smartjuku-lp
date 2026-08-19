#!/usr/bin/env python3
"""アドホック: Q3診断キャンペーンの広告別・日別実績をログに出力する（判定用）"""
import json, os, sys, urllib.parse, urllib.request

TOKEN = os.environ["META_ACCESS_TOKEN"]
CAMPAIGN = os.environ.get("REPORT_CAMPAIGN_ID", "120253032563250401")
BASE = "https://graph.facebook.com/v21.0"
SINCE = os.environ.get("REPORT_SINCE", "2026-08-01")
UNTIL = os.environ.get("REPORT_UNTIL", "2026-08-13")

def get(url, **params):
    params["access_token"] = TOKEN
    with urllib.request.urlopen(url + "?" + urllib.parse.urlencode(params), timeout=30) as r:
        return json.loads(r.read().decode())

def act(actions, key):
    for a in actions or []:
        if a["action_type"] == key:
            return float(a.get("value", 0))
    return 0

# キャンペーン・広告ステータス
meta = get(f"{BASE}/{CAMPAIGN}", fields="name,effective_status,daily_budget")
print(f"CAMPAIGN: {meta.get('name')} status={meta.get('effective_status')} daily_budget={meta.get('daily_budget')}")
ads = get(f"{BASE}/{CAMPAIGN}/ads", fields="name,effective_status", limit="50").get("data", [])
for a in ads:
    print(f"AD-STATUS: {a['name']} = {a['effective_status']}")

# 日別×広告別
rows = get(f"{BASE}/{CAMPAIGN}/insights",
           level="ad", time_increment="1",
           time_range=json.dumps({"since": SINCE, "until": UNTIL}),
           fields="date_start,ad_name,spend,impressions,ctr,frequency,actions",
           limit="500").get("data", [])
print("DATE | AD | SPEND | IMP | CTR | FREQ | LEADS")
for r in sorted(rows, key=lambda x: (x["date_start"], x.get("ad_name", ""))):
    leads = act(r.get("actions"), "onsite_conversion.lead_grouped") or act(r.get("actions"), "lead")
    print(f"{r['date_start']} | {r.get('ad_name','?')} | {float(r.get('spend',0)):.0f} | {r.get('impressions','0')} | {float(r.get('ctr',0)):.2f} | {float(r.get('frequency',0)):.2f} | {leads:.0f}")

# ---- アカウント全体サマリ（REPORT_SCOPE=account のとき）----
if os.environ.get("REPORT_SCOPE") == "account":
    acct = get(f"{BASE}/{CAMPAIGN}", fields="account_id").get("account_id")
    print(f"\nACCOUNT: act_{acct}  期間 {SINCE} 〜 {UNTIL}")
    camps = get(f"{BASE}/act_{acct}/insights",
                level="campaign",
                time_range=json.dumps({"since": SINCE, "until": UNTIL}),
                fields="campaign_name,spend,impressions,clicks,actions",
                limit="200").get("data", [])
    tot_spend = tot_leads = tot_imp = tot_clicks = 0.0
    print("CAMPAIGN | SPEND | IMP | CLICKS | LEADS")
    for c in sorted(camps, key=lambda x: -float(x.get("spend", 0))):
        leads = act(c.get("actions"), "onsite_conversion.lead_grouped") or act(c.get("actions"), "lead")
        sp = float(c.get("spend", 0)); imp = float(c.get("impressions", 0)); ck = float(c.get("clicks", 0))
        tot_spend += sp; tot_leads += leads; tot_imp += imp; tot_clicks += ck
        print(f"{c.get('campaign_name','?')} | {sp:.0f} | {imp:.0f} | {ck:.0f} | {leads:.0f}")
    print(f"TOTAL | {tot_spend:.0f} | {tot_imp:.0f} | {tot_clicks:.0f} | {tot_leads:.0f}")
    if tot_leads:
        print(f"CPL(全体) = {tot_spend/tot_leads:.0f}")
