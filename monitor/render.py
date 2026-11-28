"""公開ページ（index.html）を生成する。外部ライブラリなし・1ファイル完結。"""
from __future__ import annotations

import datetime as dt
import html
import json
import urllib.parse

from monitor.aggregate import MARKET_LABEL

SEASON = {"winter": ("冬用", "winter"), "summer": ("夏用", "summer")}
E = html.escape


def safe_url(u: str | None) -> str:
    """http/https 以外（javascript: など）はリンクにしない。"""
    u = (u or "").strip()
    return E(u) if urllib.parse.urlsplit(u).scheme in ("http", "https") else "#"


def yen(v: int | None) -> str:
    return "—" if v is None else f"¥{v:,}"


def fmt_time(iso: str) -> str:
    t = dt.datetime.fromisoformat(iso)
    return f"{t:%Y/%m/%d %H:%M}"


def diff_badge(now: int | None, prev: int | None) -> str:
    if now is None or prev is None:
        return '<span class="diff flat">前回比 —</span>'
    d = now - prev
    cls = "down" if d < 0 else "up" if d > 0 else "flat"
    sign = "+" if d > 0 else "−" if d < 0 else "±"
    return f'<span class="diff {cls}">前回比 {sign}¥{abs(d):,}</span>'


def _status_list(status: dict[str, str]) -> str:
    items = []
    for m, label in MARKET_LABEL.items():
        if m not in status:
            continue
        s = status[m]
        cls = "ok" if s == "ok" else "warn" if s.startswith(("未設定", "未接続")) else "err"
        text = "取得済み" if s == "ok" else s
        items.append(f'<li class="{cls}"><b>{label}</b> {E(text)}</li>')
    return f'<ul class="mstatus">{"".join(items)}</ul>'


def _offers_table(snap: dict) -> str:
    if not snap["offers"]:
        return '<p class="muted">集計できる出品はありませんでした。</p>'
    rows = []
    for i, o in enumerate(snap["offers"], 1):
        qty = "4本セット" if o["quantity"] == 4 else f'{o["quantity"]}本'
        note = "<br>（本数は価格から推定）" if o["inferred"] else ""
        ship = "送料無料" if o["shipping"] == 0 else "送料別・要確認"
        rows.append(
            f'<tr><td class="n">{i}</td><td><a href="{safe_url(o["url"])}" target="_blank" rel="noopener noreferrer">{E(o["title"])}</a>'
            f'<div class="muted">{E(MARKET_LABEL[o["market"]])} ・ {E(o["store"])} ・ {ship}</div></td>'
            f'<td class="r"><b>{yen(o["unit_price"])}</b>/本<div class="muted">{qty} {yen(o["price"])}{note}</div></td></tr>'
        )
    return f'<table class="offers"><tbody>{"".join(rows)}</tbody></table>'


def _excluded(snap: dict) -> str:
    ex = snap.get("excluded") or {}
    if not ex:
        return ""
    parts = "、".join(f"{E(k)} {v}件" for k, v in sorted(ex.items(), key=lambda kv: -kv[1]))
    return f'<p class="muted small">集計から除いた出品：{parts}</p>'


def _warning(snap: dict) -> str:
    if snap.get("stale"):
        return (f'<p class="warn-note">最新のチェック（{fmt_time(snap["staleAt"])}）は全市場で取得に失敗しました。'
                f'表示は {fmt_time(snap["checkedAt"])} 時点のものです。</p>')
    if snap.get("degraded"):
        names = "・".join(MARKET_LABEL[m] for m in snap["degraded"])
        return f'<p class="warn-note">{names} の取得に失敗したため、この回はその市場を除いて集計しています（前回比は参考）。</p>'
    return ""


def _card(t: dict, snap: dict) -> str:
    season, cls = SEASON[t["season"]]
    if snap["lowestUnitPrice"] is None:
        main = '<div class="price none">出品なし</div>'
        meta = "主要市場で条件に合う出品が見つかりませんでした"
    else:
        main = f'<div class="price">{yen(snap["lowestUnitPrice"])}<small>/本</small></div>'
        meta = (f'{E(snap["lowestStore"])}（{MARKET_LABEL[snap["lowestMarket"]]}）'
                f' ・ 4本 {yen(snap["lowestSetPrice"])}')
    return (f'<a class="card" href="#{t["id"]}"><span class="season {cls}">{season}</span>'
            f'<h3>{E(t["name"])}</h3>{main}<p class="muted">{meta}</p>'
            f'{diff_badge(snap["lowestUnitPrice"], snap.get("previousLowestUnitPrice"))}{_warning(snap)}</a>')


def _section(t: dict, snap: dict) -> str:
    season, cls = SEASON[t["season"]]
    link = (f'<a class="btn" href="{safe_url(snap["lowestUrl"])}" target="_blank" rel="noopener noreferrer">最安の商品ページ ↗</a>'
            if snap["lowestUrl"] else "")
    return f'''
<section class="target" id="{t["id"]}">
  <div class="head"><span class="season {cls}">{season}</span><h2>{E(t["name"])}</h2></div>
  {_warning(snap)}
  <div class="board">
    <div><span class="lbl">最安値（1本）</span><b class="big">{yen(snap["lowestUnitPrice"])}</b>
      <span class="muted">{E(snap["lowestStore"] or "")}</span></div>
    <div><span class="lbl">安い順 上位3件の平均</span><b class="mid">{yen(snap["top3AvgUnitPrice"])}</b>
      <span class="muted">1件の出入りで跳ねにくい目安</span></div>
    <div><span class="lbl">相場（中央値）</span><b class="mid">{yen(snap["medianUnitPrice"])}</b>
      <span class="muted">{snap["offerCount"]}件から算出</span></div>
  </div>
  {link}
  <h4>価格の推移</h4>
  <div class="ranges" data-target="{t["id"]}">
    <button data-h="24">24時間</button><button data-h="168" class="on">7日</button>
    <button data-h="720">30日</button><button data-h="0">全期間</button>
  </div>
  <div class="chart" id="chart-{t["id"]}"></div>
  <p class="legend"><i class="l1"></i>最安値 <i class="l2"></i>上位3件の平均 <i class="l3"></i>中央値</p>
  <h4>いまの出品（1本あたりの安い順）</h4>
  {_offers_table(snap)}
  {_excluded(snap)}
  <h4>市場ごとの取得状況</h4>
  {_status_list(snap["marketStatus"])}
</section>'''


def page(latest: dict, history: dict) -> str:
    targets, snaps = latest["targets"], latest["snapshots"]
    cards = "".join(_card(t, snaps[t["id"]]) for t in targets)
    sections = "".join(_section(t, snaps[t["id"]]) for t in targets)
    data = json.dumps(history.get("targets", {}), ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/").replace("<!--", "<\\!--")
    return TEMPLATE.format(
        size=E(latest["size"]), checked=fmt_time(latest["checkedAt"]),
        cards=cards, sections=sections, data=data, css=CSS, js=JS,
    )


CSS = """
:root{--bg:#fff;--ink:#1a1a1a;--dim:#6b6b6b;--line:#e4e4e4;--accent:#b3261e;--soft:#f7f7f5;--ok:#2e7d32;--warn:#a36a00}
@media (prefers-color-scheme:dark){:root{--bg:#141414;--ink:#eee;--dim:#a0a0a0;--line:#333;--accent:#ff8a80;--soft:#1e1e1e;--ok:#81c784;--warn:#ffb74d}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.7 "Hiragino Kaku Gothic ProN","Noto Sans JP",system-ui,sans-serif}
.wrap{max-width:1040px;margin:0 auto;padding:32px 16px 64px}
h1,h2,h3{font-family:"Hiragino Mincho ProN","Yu Mincho",serif;font-weight:600;margin:0}
h1{font-size:clamp(24px,4vw,34px)}h2{font-size:22px}h4{margin:28px 0 8px;font-size:14px;color:var(--dim);letter-spacing:.06em}
header{border-bottom:1px solid var(--ink);padding-bottom:16px}
.muted{color:var(--dim)}.small{font-size:13px}a{color:var(--accent)}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:12px;margin-top:24px}
.card{display:block;border:1px solid var(--line);padding:16px;text-decoration:none;color:var(--ink)}
.card:hover{border-color:var(--ink)}.card h3{font-size:17px;margin-top:4px}
.price{font-size:38px;font-weight:600;color:var(--accent);margin-top:6px;font-variant-numeric:tabular-nums}
.price small{font-size:14px;color:var(--dim)}.price.none{font-size:22px;color:var(--dim)}
.card p{margin:4px 0 8px;font-size:13px}
.season{font-size:12px;border:1px solid;padding:1px 8px}.season.winter{color:#1d5f8a}.season.summer{color:#a35a00}
.diff{font-size:12px;padding:2px 8px;background:var(--soft)}.diff.down{color:var(--ok)}.diff.up{color:var(--accent)}.diff.flat{color:var(--dim)}
.target{margin-top:48px;padding-top:24px;border-top:1px solid var(--line)}
.head{display:flex;gap:10px;align-items:center;flex-wrap:wrap}
.board{display:grid;grid-template-columns:repeat(3,1fr);border:1px solid var(--line);margin-top:16px}
.board>div{padding:14px 16px;display:flex;flex-direction:column}.board>div+div{border-left:1px solid var(--line)}
@media(max-width:640px){.board{grid-template-columns:1fr}.board>div+div{border-left:0;border-top:1px solid var(--line)}}
.lbl{font-size:12px;color:var(--dim)}.big{font-size:40px;color:var(--accent);font-variant-numeric:tabular-nums}
.mid{font-size:26px;font-variant-numeric:tabular-nums}
.btn{display:inline-block;margin-top:12px;border:1px solid var(--accent);padding:8px 14px;text-decoration:none;min-height:44px}
.ranges button{background:var(--bg);color:var(--ink);border:1px solid var(--line);padding:6px 12px;min-height:36px;cursor:pointer;font:inherit}
.ranges button.on{border-color:var(--ink);font-weight:600}
.chart{border:1px solid var(--line);margin-top:8px;overflow-x:auto}.chart svg{display:block;width:100%;min-width:560px;height:auto}
.legend{font-size:12px;color:var(--dim)}.legend i{display:inline-block;width:20px;height:3px;vertical-align:middle;margin:0 4px 0 12px}
.l1{background:var(--accent)}.l2{background:var(--ink)}.l3{background:var(--dim);opacity:.5}
.offers{width:100%;border-collapse:collapse;table-layout:fixed}.offers td{overflow-wrap:anywhere}.offers .r{width:10.5em}.offers td{border-top:1px solid var(--line);padding:10px 6px;vertical-align:top}
.offers .n{width:28px;color:var(--dim)}body{overflow-wrap:anywhere}.offers .r{text-align:right;white-space:nowrap}.offers .muted{font-size:12px}
.mstatus{list-style:none;padding:0;margin:0;display:flex;flex-wrap:wrap;gap:6px 18px;font-size:13px}
.mstatus .ok b{color:var(--ok)}.mstatus .warn b{color:var(--warn)}.mstatus .err b{color:var(--accent)}
.warn-note{font-size:13px;color:var(--warn);border-left:3px solid var(--warn);padding:4px 10px;margin:10px 0}
footer{margin-top:56px;border-top:1px solid var(--line);padding-top:16px;font-size:13px;color:var(--dim)}
"""

JS = r"""
var H=JSON.parse(document.getElementById('history').textContent);
function css(n){return getComputedStyle(document.documentElement).getPropertyValue(n).trim();}
function draw(id,hours){
  var el=document.getElementById('chart-'+id);if(!el)return;
  var rows=(H[id]||[]).map(function(r){return{t:Date.parse(r.checkedAt),a:r.lowestUnitPrice,b:r.top3AvgUnitPrice,c:r.medianUnitPrice};});
  if(hours>0){var from=Date.now()-hours*3600e3;rows=rows.filter(function(r){return r.t>=from;});}
  var vals=[];rows.forEach(function(r){[r.a,r.b,r.c].forEach(function(v){if(v!=null)vals.push(v);});});
  if(vals.length<1){el.innerHTML='<p class="muted" style="padding:16px">この期間のデータはまだありません。</p>';return;}
  var W=960,Ht=300,L=70,R=16,T=14,B=40,pw=W-L-R,ph=Ht-T-B;
  var t0=rows[0].t,t1=rows[rows.length-1].t;if(t1===t0)t1=t0+3600e3;
  var lo=Math.min.apply(null,vals),hi=Math.max.apply(null,vals),pad=Math.max(300,(hi-lo)*.1);
  var d0=Math.floor((lo-pad)/500)*500,d1=Math.ceil((hi+pad)/500)*500;
  function X(t){return L+(t-t0)/(t1-t0)*pw;}function Y(v){return T+(d1-v)/(d1-d0)*ph;}
  var line=css('--line'),dim=css('--dim'),s='';
  for(var i=0;i<=4;i++){var v=d0+(d1-d0)*i/4,y=Y(v).toFixed(1);
    s+='<line x1="'+L+'" x2="'+(W-R)+'" y1="'+y+'" y2="'+y+'" stroke="'+line+'"/>';
    s+='<text x="'+(L-8)+'" y="'+y+'" dy="4" text-anchor="end" font-size="12" fill="'+dim+'">¥'+Math.round(v).toLocaleString('ja-JP')+'</text>';}
  var span=t1-t0,step=span>10*864e5?864e5*7:span>2*864e5?864e5:6*3600e3;
  var start=new Date(t0);start.setMinutes(0,0,0);if(step>=864e5)start.setHours(0);
  for(var tt=start.getTime();tt<=t1;tt+=step){if(tt<t0)continue;var d=new Date(tt),x=X(tt).toFixed(1);
    var lab=(d.getMonth()+1)+'/'+d.getDate()+(step<864e5?' '+('0'+d.getHours()).slice(-2)+':00':'');
    s+='<line x1="'+x+'" x2="'+x+'" y1="'+T+'" y2="'+(Ht-B)+'" stroke="'+line+'" stroke-dasharray="2 4"/>';
    s+='<text x="'+x+'" y="'+(Ht-B+18)+'" text-anchor="middle" font-size="12" fill="'+dim+'">'+lab+'</text>';}
  function path(k){var p='',pen=false;rows.forEach(function(r){if(r[k]==null){pen=false;return;}
    p+=(pen?'L':'M')+X(r.t).toFixed(1)+' '+Y(r[k]).toFixed(1)+' ';pen=true;});return p;}
  s+='<path d="'+path('c')+'" fill="none" stroke="'+dim+'" stroke-opacity=".5" stroke-width="2" stroke-dasharray="5 4"/>';
  s+='<path d="'+path('b')+'" fill="none" stroke="'+css('--ink')+'" stroke-width="1.6"/>';
  s+='<path d="'+path('a')+'" fill="none" stroke="'+css('--accent')+'" stroke-width="2.4"/>';
  rows.forEach(function(r){if(r.a==null)return;var d=new Date(r.t);
    s+='<circle cx="'+X(r.t).toFixed(1)+'" cy="'+Y(r.a).toFixed(1)+'" r="'+(rows.length>60?2:3.5)+'" fill="'+css('--accent')+'" stroke="transparent" stroke-width="8"><title>'+d.toLocaleString('ja-JP')+
    '\n最安 ¥'+r.a.toLocaleString('ja-JP')+(r.b!=null?'\n上位3件平均 ¥'+r.b.toLocaleString('ja-JP'):'')+
    (r.c!=null?'\n中央値 ¥'+r.c.toLocaleString('ja-JP'):'')+'</title></circle>';});
  el.innerHTML='<svg viewBox="0 0 '+W+' '+Ht+'" role="img" aria-label="価格の推移">'+s+'</svg>';
}
document.querySelectorAll('.ranges').forEach(function(g){
  var id=g.dataset.target;
  g.querySelectorAll('button').forEach(function(b){b.addEventListener('click',function(){
    g.querySelectorAll('button').forEach(function(x){x.classList.remove('on');});b.classList.add('on');draw(id,+b.dataset.h);});});
  draw(id,168);
});
"""

TEMPLATE = """<!doctype html>
<html lang="ja"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>タイヤ価格監視 {size}</title><style>{css}</style></head>
<body><div class="wrap">
<header><h1>タイヤ価格監視 <span class="muted">{size}</span></h1>
<p class="muted">楽天市場・Yahoo!ショッピング・ヤフオク! の新品出品を1日2回（朝8時半・夕方18時半ごろ）自動で集計しています。
価格は税込・1本あたりに換算（送料は含めず、送料無料かどうかを表示）。Amazon は対象外です。</p>
<p><b>データ時点：{checked}</b>（日本時間）</p></header>
<div class="cards">{cards}</div>
{sections}
<footer>
<p>集計ルール：サイズと銘柄が一致する新品だけを対象にし、ホイール付き・中古・予約品は除外。ヤフオク!は即決価格のみで入札中の出品は除外。
1本あたりが妥当な範囲を外れる価格は読み取りミスとして除外しています。</p>
<p>表示価格はチェック時点のものです。購入前に商品ページで在庫・送料・製造年をご確認ください。</p>
</footer></div>
<script type="application/json" id="history">{data}</script>
<script>{js}</script>
</body></html>
"""
