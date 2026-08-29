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
    print("\n=== 広告セットの promoted_object ===")
    sets2 = get(f"{BASE}/{CAMPAIGN}/adsets", fields="name,promoted_object,optimization_goal", limit="25").get("data", [])
    form_ids = set()
    for st in sets2:
        po = st.get("promoted_object") or {}
        print(f"ADSET | {st.get('name','?')[:30]} | goal={st.get('optimization_goal')} | promoted={po}")
        if po.get("leadgen_form_id"):
            form_ids.add(po["leadgen_form_id"])

    print("\n=== 広告クリエイティブのフォームID ===")
    ads3 = get(f"{BASE}/{CAMPAIGN}/ads", fields="name,creative{id,object_story_spec,effective_object_story_id}", limit="50").get("data", [])
    for a in ads3:
        cr = a.get("creative") or {}
        oss = cr.get("object_story_spec") or {}
        page_id = oss.get("page_id")
        call = ((oss.get("link_data") or {}).get("call_to_action") or {}).get("value") or {}
        fid = call.get("lead_gen_form_id")
        print(f"AD | {a['name'][:30]} | page={page_id} | form={fid}")
        if fid: form_ids.add(str(fid))

    print("\n=== フォームの状態と実リード ===")
    for fid in form_ids:
        try:
            f = get(f"{BASE}/{fid}", fields="name,status,locale,questions,created_time")
            qs = [q.get("key") or q.get("type") for q in (f.get("questions") or [])]
            print(f"FORM {fid} | {f.get('name','?')[:40]} | status={f.get('status')} | 質問={qs}")
        except Exception as e:
            print(f"FORM {fid} | 取得エラー: {e}")
        try:
            leads = get(f"{BASE}/{fid}/leads", fields="created_time", limit="100").get("data", [])
            if leads:
                from collections import Counter
                c = Counter(l.get("created_time","")[:10] for l in leads)
                print(f"   実リード 合計{len(leads)}件 / 最新 {max(c)}")
                for d in sorted(c)[-14:]: print(f"     {d} : {c[d]}件")
            else:
                print("   実リード 0件")
        except Exception as e:
            print(f"   leads取得エラー: {e}")

    print("\n=== アクション内訳（日別・全種類）===")
    arows = get(f"{BASE}/{CAMPAIGN}/insights", time_increment="1",
                time_range=json.dumps({"since": SINCE, "until": UNTIL}),
                fields="date_start,spend,clicks,actions", limit="200").get("data", [])
    for r in sorted(arows, key=lambda x: x["date_start"]):
        acts = {a["action_type"]: a.get("value") for a in (r.get("actions") or [])}
        keep = {k: v for k, v in acts.items() if any(x in k for x in ("lead", "click", "view", "landing"))}
        print(f"{r['date_start']} | 消化{float(r.get('spend',0)):>5.0f} | clicks={r.get('clicks','0')} | {keep}")


# ---- クリエイティブ設定の比較（REPORT_SCOPE=creative）----
if os.environ.get("REPORT_SCOPE") == "creative":
    print("\n=== 各広告のクリエイティブ設定 ===")
    ads4 = get(f"{BASE}/{CAMPAIGN}/ads",
               fields="name,effective_status,creative{id,name,degrees_of_freedom_spec,object_story_spec,asset_feed_spec,contextual_multi_ads}",
               limit="50").get("data", [])
    for a in ads4:
        cr = a.get("creative") or {}
        print(f"\n--- {a['name']} ({a.get('effective_status')}) ---")
        dof = cr.get("degrees_of_freedom_spec")
        print(f"  Advantage+設定(degrees_of_freedom_spec): {json.dumps(dof, ensure_ascii=False) if dof else 'なし'}")
        oss = cr.get("object_story_spec") or {}
        ld = oss.get("link_data") or {}
        msg = (ld.get("message") or "")[:60].replace("\n", " / ")
        cta = (ld.get("call_to_action") or {})
        print(f"  page_id={oss.get('page_id')} / IG={oss.get('instagram_actor_id') or oss.get('instagram_user_id')}")
        print(f"  本文冒頭: {msg}")
        print(f"  見出し(name): {ld.get('name')}")
        print(f"  説明(description): {ld.get('description')}")
        print(f"  link: {ld.get('link')}")
        print(f"  CTA: type={cta.get('type')} value={json.dumps(cta.get('value'), ensure_ascii=False)}")
        afs = cr.get("asset_feed_spec")
        if afs:
            print(f"  asset_feed_spec: optimization={afs.get('optimization_type')} / keys={list(afs.keys())}")


# ---- オーディエンス設定（REPORT_SCOPE=audience）----
if os.environ.get("REPORT_SCOPE") == "audience":
    acct = get(f"{BASE}/{CAMPAIGN}", fields="account_id").get("account_id")
    print("\n=== 広告セットのターゲティング ===")
    sets3 = get(f"{BASE}/{CAMPAIGN}/adsets",
                fields="name,targeting,optimization_goal,daily_budget,effective_status", limit="25").get("data", [])
    for st in sets3:
        t = st.get("targeting") or {}
        print(f"\nADSET: {st.get('name')} ({st.get('effective_status')})")
        print(f"  年齢: {t.get('age_min')}-{t.get('age_max')} / 性別: {t.get('genders','すべて')}")
        print(f"  地域: {json.dumps(t.get('geo_locations'), ensure_ascii=False)[:200]}")
        print(f"  カスタムオーディエンス: {json.dumps(t.get('custom_audiences'), ensure_ascii=False)}")
        print(f"  除外: {json.dumps(t.get('excluded_custom_audiences'), ensure_ascii=False)}")
        fs = t.get("flexible_spec")
        print(f"  興味関心(flexible_spec): {json.dumps(fs, ensure_ascii=False)[:300] if fs else 'なし'}")
        print(f"  配置: {t.get('publisher_platforms')} / 自動拡張: targeting_relaxation={json.dumps(t.get('targeting_relaxation_types'), ensure_ascii=False)}")

    print("\n=== アカウントの保存済みオーディエンス ===")
    try:
        auds = get(f"{BASE}/act_{acct}/customaudiences",
                   fields="id,name,subtype,approximate_count_lower_bound,time_created",
                   limit="50").get("data", [])
        for a in auds:
            if not isinstance(a, dict):
                continue
            print(f"  {a.get('id')} | {str(a.get('name','?'))[:45]} | {a.get('subtype')} | 規模≒{a.get('approximate_count_lower_bound')} | 作成={str(a.get('time_created',''))[:10]}")
    except Exception as e:
        print(f"  取得エラー: {e}")
