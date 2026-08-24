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
           fields="date_start,ad_name,spend,impressions,clicks,cpc,ctr,frequency,reach,actions",
           limit="500").get("data", [])
print("DATE | AD | SPEND | IMP | REACH | CLICKS | CPC | CTR | FREQ | LEADS")
for r in sorted(rows, key=lambda x: (x["date_start"], x.get("ad_name", ""))):
    leads = act(r.get("actions"), "onsite_conversion.lead_grouped") or act(r.get("actions"), "lead")
    print(f"{r['date_start']} | {r.get('ad_name','?')} | {float(r.get('spend',0)):.0f} | {r.get('impressions','0')} | {r.get('reach','0')} | {r.get('clicks','0')} | {float(r.get('cpc',0)):.0f} | {float(r.get('ctr',0)):.2f} | {float(r.get('frequency',0)):.2f} | {leads:.0f}")

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

# ---- 診断モード：ステータス更新履歴・広告セット設定・アクティビティログ ----
if os.environ.get("REPORT_SCOPE") == "diag":
    acct = get(f"{BASE}/{CAMPAIGN}", fields="account_id").get("account_id")
    print(f"\n=== 広告の設定状態 ===")
    ads2 = get(f"{BASE}/{CAMPAIGN}/ads",
               fields="name,status,effective_status,created_time,updated_time,adset_id",
               limit="50").get("data", [])
    for a in ads2:
        print(f"AD | {a['name'][:34]} | status={a.get('status')} | eff={a.get('effective_status')} | created={a.get('created_time','')[:16]} | updated={a.get('updated_time','')[:16]}")
    print(f"\n=== 広告セットの設定 ===")
    sets = get(f"{BASE}/{CAMPAIGN}/adsets",
               fields="name,status,effective_status,daily_budget,bid_strategy,optimization_goal,updated_time,learning_stage_info",
               limit="25").get("data", [])
    for s in sets:
        print(f"ADSET | {s.get('name','?')[:30]} | {s.get('effective_status')} | 日予算={s.get('daily_budget')} | 入札={s.get('bid_strategy')} | 目標={s.get('optimization_goal')} | updated={s.get('updated_time','')[:16]}")
        print(f"        learning={s.get('learning_stage_info')}")
    print(f"\n=== アカウント変更履歴（{SINCE}〜{UNTIL}）===")
    try:
        acts = get(f"{BASE}/act_{acct}/activities",
                   since=SINCE, until=UNTIL,
                   fields="event_type,event_time,object_name,object_type,actor_name,extra_data",
                   limit="100").get("data", [])
        if not acts:
            print("（該当期間の変更履歴なし）")
        for a in acts:
            ex = str(a.get("extra_data", ""))[:110]
            print(f"{a.get('event_time','')[:16]} | {a.get('event_type')} | {a.get('object_type')} {str(a.get('object_name',''))[:30]} | by {a.get('actor_name')} | {ex}")
    except Exception as e:
        print(f"activities取得エラー: {e}")

# ---- フォーム診断モード（REPORT_SCOPE=form）----
if os.environ.get("REPORT_SCOPE") == "form":
    print("\n=== リードフォームの状態 ===")
    ads3 = get(f"{BASE}/{CAMPAIGN}/ads", fields="name,effective_status", limit="50").get("data", [])
    seen_forms = {}
    for a in ads3:
        try:
            forms = get(f"{BASE}/{a['id']}/leadgen_forms",
                        fields="id,name,status,locale,questions,created_time", limit="10").get("data", [])
        except Exception as e:
            print(f"  {a['name'][:30]}: フォーム取得エラー {e}")
            continue
        for f in forms:
            seen_forms[f["id"]] = f
            qs = [q.get("key") or q.get("type") for q in (f.get("questions") or [])]
            print(f"FORM | {f.get('name','?')[:40]} | id={f['id']} | status={f.get('status')} | 質問={qs}")
    print("\n=== フォーム別の実リード（直近取得できる分）===")
    for fid, f in seen_forms.items():
        try:
            leads = get(f"{BASE}/{fid}/leads", fields="created_time,id", limit="50").get("data", [])
            if leads:
                dates = sorted(l.get("created_time", "")[:10] for l in leads)
                from collections import Counter
                c = Counter(dates)
                print(f"  {f.get('name','?')[:30]} 合計{len(leads)}件 / 最新={dates[-1]}")
                for d in sorted(c)[-12:]:
                    print(f"     {d} : {c[d]}件")
            else:
                print(f"  {f.get('name','?')[:30]} : リード0件")
        except Exception as e:
            print(f"  {f.get('name','?')[:30]} : leads取得エラー {e}")
