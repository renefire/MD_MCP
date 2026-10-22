#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
麦门食养局 · 五行食养卡生成器（单文件 HTML，零外部依赖）

用法：
    python make_card.py --date 1988-06-15 --hour 10 [--name 小任] [-o card.html]
    python make_card.py --demo                # 离线演示，内置示例生辰
    python make_card.py --chart chart.json    # 直接消费 bazi_wuxing.py --json 的输出

数据源优先级：MCD_MCP_TOKEN 存在 → 尝试 MCP 实时菜单；失败/无 Token → 参考菜单，
卡片底部会如实标注数据来源，绝不冒充实时数据。
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from bazi_wuxing import paipan, classify, WUXING_ATTR          # noqa: E402
from mcp_client import McDonaldMCP, load_reference_menu        # noqa: E402

WUXING_COLOR = {"木": "#4a8c3f", "火": "#d0442e", "土": "#c08a1e", "金": "#9a8f7a", "水": "#2e5f8a"}

SLOGAN = {
    "木": "草木生发，宜青宜酸",
    "火": "以温养阳，忌寒凉入腹",
    "土": "甘平厚味，稳住中焦",
    "金": "辛香通气，清凉降燥",
    "水": "以寒制热，冰爽归元",
}


def fmt_price(p) -> str:
    return f"¥{p:.1f}" if p is not None else "价格以门店为准"


def _pick(items: list, element: str, n: int = 2) -> list:
    hits = [it for it in items if classify(it.get("name", "")) == element]
    priced = [it for it in hits if it.get("price") is not None]   # 有实价的优先展示
    return (priced + [it for it in hits if it not in priced])[:n]


def build_recommendation(chart: dict, menu_items: list) -> dict:
    favors, avoids = chart["favor"], chart["avoid"]
    return {
        "eat": [{"element": w, "items": _pick(menu_items, w)} for w in favors],
        "avoid": [{"element": w, "items": _pick(menu_items, w, 1)} for w in avoids],
    }


def render_card(chart: dict, reco: dict, source: str, name: str = "食客", meta: dict | None = None) -> str:
    counts = chart["counts"]
    total = max(sum(counts.values()), 1)
    bars = "".join(
        f'<div class="bar"><span class="wname" style="color:{WUXING_COLOR[w]}">{w}</span>'
        f'<div class="track"><div class="fill" style="width:{c / total * 100:.0f}%;background:{WUXING_COLOR[w]}"></div></div>'
        f'<span class="cnt">{c}</span></div>'
        for w, c in counts.items()
    )
    pillars = "".join(f'<span class="pillar"><b>{p["gan"]}{p["zhi"]}</b><i>{p["label"]}</i></span>' for p in chart["pillars"])

    eat_html = ""
    for grp in reco["eat"]:
        w = grp["element"]
        attr = WUXING_ATTR[w]
        lis = "".join(
            f'<li><b>{it["name"]}</b><span>{fmt_price(it.get("price"))} · {it.get("kcal") or "?"} kcal</span></li>'
            for it in grp["items"]
        ) or '<li class="empty">当前菜单暂无此类目，以门店实物为准</li>'
        eat_html += (
            f'<section class="eat" style="border-left:4px solid {WUXING_COLOR[w]}">'
            f'<h3 style="color:{WUXING_COLOR[w]}">宜补 · {w} <small>{attr["温"]}性 {attr["味"]}味</small></h3>'
            f'<p class="slogan">{SLOGAN[w]}</p><ul>{lis}</ul></section>'
        )

    avoid_html = ""
    for grp in reco["avoid"]:
        w = grp["element"]
        its = "".join(f'<b>{it["name"]}</b>' for it in grp["items"]) or ""
        avoid_html += f'<span class="chip">慎点 {w}：{its or "此类少碰"}</span>'

    favor_names = "、".join(chart["favor"])
    lucky = "、".join(WUXING_ATTR[w]["吉时"] for w in chart["favor"])
    today = datetime.now().strftime("%Y-%m-%d")
    src_note = "麦当劳官方 MCP 实时数据" if source == "mcp" else "离线参考菜单（非实时，仅演示）"
    if source == "mcp" and meta and meta.get("storeName"):
        src_note += f" · 门店：{meta['storeName']}"

    return f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>麦门食养局 · {name}的五行食养卡</title>
<style>
body{{margin:0;background:#f6f1e7;font-family:"PingFang SC","Microsoft YaHei",sans-serif;color:#3a2f24;display:flex;justify-content:center;padding:16px}}
.card{{width:100%;max-width:430px;background:#fffaf0;border:2px solid #d8b74a;border-radius:16px;overflow:hidden}}
.head{{background:#b91d1d;color:#ffe9b8;text-align:center;padding:22px 16px 14px}}
.head h1{{margin:0;font-size:22px;letter-spacing:6px}}
.head p{{margin:6px 0 0;font-size:12px;opacity:.85}}
.meta{{padding:16px 18px 4px;text-align:center}}
.pillars{{display:flex;justify-content:center;gap:10px}}
.pillar{{display:flex;flex-direction:column;background:#fdf4dc;border:1px solid #e3c983;border-radius:8px;padding:8px 12px}}
.pillar b{{font-size:17px}}.pillar i{{font-style:normal;font-size:11px;color:#8a7658}}
.meta .who{{font-size:13px;color:#8a7658;margin:10px 0 0}}
.box{{padding:6px 18px 14px}}
h2{{font-size:14px;margin:14px 0 8px;color:#7a5c1e;border-bottom:1px dashed #e3c983;padding-bottom:4px}}
.bar{{display:flex;align-items:center;gap:8px;margin:5px 0}}
.wname{{width:18px;font-weight:600}}
.track{{flex:1;height:12px;background:#f1e6cc;border-radius:6px;overflow:hidden}}
.fill{{height:100%;border-radius:6px}}
.cnt{{width:16px;font-size:12px;text-align:right;color:#8a7658}}
.eat{{background:#fdfaf3;border-radius:10px;padding:10px 14px;margin:10px 0}}
.eat h3{{margin:0;font-size:14px}}.eat h3 small{{font-weight:400;color:#8a7658}}
.slogan{{margin:4px 0 6px;font-size:12px;color:#a08a5f}}
.eat ul{{margin:0;padding:0;list-style:none}}
.eat li{{display:flex;justify-content:space-between;font-size:13px;padding:5px 0;border-top:1px dotted #eaddb8}}
.eat li span{{color:#8a7658;font-size:12px}}
.chip{{display:inline-block;background:#f7e8e8;color:#8a2f2f;border:1px solid #e0b9b9;border-radius:999px;padding:4px 12px;font-size:12px;margin:0 6px 6px 0}}
.lucky{{background:#fdf4dc;border-radius:10px;padding:10px 14px;font-size:13px;margin-top:10px}}
.foot{{background:#f6edd8;font-size:11px;color:#9a8a6a;text-align:center;padding:10px 14px;line-height:1.7}}
</style></head><body>
<div class="card">
  <div class="head"><h1>麦门食养局</h1><p>以八字五行，点人间烟火 · {today}</p></div>
  <div class="meta">
    <div class="pillars">{pillars}</div>
    <p class="who">{name} · 日主{chart["day_master"]}（身{chart["strength"]}）· 宜补【{favor_names}】</p>
  </div>
  <div class="box">
    <h2>五行分布</h2>{bars}
    <h2>今日宜吃</h2>{eat_html}
    <h2>今日慎点</h2>{avoid_html or "<span class='chip'>五行周全，百无禁忌</span>"}
    <div class="lucky">吉时：<b>{lucky}</b><br>{SLOGAN.get(chart["favor"][0], "")}</div>
  </div>
  <div class="foot">数据来源：{src_note}<br>{chart["disclaimer"]}</div>
</div>
</body></html>"""


def main() -> int:
    ap = argparse.ArgumentParser(description="麦门食养局 · 食养卡生成")
    ap.add_argument("--date"); ap.add_argument("--hour", type=int, default=12)
    ap.add_argument("--name", default="食客"); ap.add_argument("-o", "--output", default="食养卡.html")
    ap.add_argument("--chart", help="直接消费 bazi_wuxing.py --json 的输出文件")
    ap.add_argument("--city", default="上海市"); ap.add_argument("--keyword", default="麦当劳")
    ap.add_argument("--demo", action="store_true")
    args = ap.parse_args()

    if args.chart:
        chart = json.loads(Path(args.chart).read_text(encoding="utf-8"))
    elif args.demo:
        chart = paipan(1988, 6, 15, 10)
    elif args.date:
        y, m, d = (int(x) for x in args.date.split("-"))
        chart = paipan(y, m, d, max(0, min(23, args.hour)))
    else:
        ap.error("需要 --date / --demo / --chart 之一")

    mcp = McDonaldMCP()
    source, meta = "reference", {}
    menu_items = load_reference_menu()["items"]
    if mcp.available:
        try:
            menu_items, source, meta = mcp.get_menu(city=args.city, keyword=args.keyword)
        except Exception as e:
            print(f"[降级] MCP 不可用（{e}），改用离线参考菜单", file=sys.stderr)

    html = render_card(chart, build_recommendation(chart, menu_items), source, args.name, meta)
    Path(args.output).write_text(html, encoding="utf-8")
    print(f"食养卡已生成：{Path(args.output).resolve()}（数据源：{source}）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
