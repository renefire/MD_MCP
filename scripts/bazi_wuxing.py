#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
麦门食养局 · 八字五行核心算法（纯标准库，可离线运行）

定位声明（务必保留在一切产出物中）：
  本模块是"简化版五行食养模型"，面向餐饮娱乐场景，不是命理排盘软件。
  简化点：
    1. 节气边界采用固定日期近似（±1 天误差），未做真太阳时/经度校正；
    2. 地支五行取本气，不含藏干加权；
    3. 喜用神采用"日主强弱三段判法"的启发式规则，非《滴天髓》级取用。
  但所有计算是确定性、可复现、可开源验证的——同一天同一时辰，全世界算出同一结果。

验证锚点（公开历法事实）：
  2000-01-01 12:00 → 己卯年 丙子月 戊午日 戊午时
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime

# ---------------------------------------------------------------- 干支基础

TIANGAN = "甲乙丙丁戊己庚辛壬癸"
DIZHI = "子丑寅卯辰巳午未申酉戌亥"

GAN_WUXING = ["木", "木", "火", "火", "土", "土", "金", "金", "水", "水"]
ZHI_WUXING = ["水", "土", "木", "木", "土", "火", "火", "土", "金", "金", "土", "水"]

# 日柱锚点：2000-01-01 = 戊午 = 甲子序 54（甲子=0）
_DAY_ANCHOR = date(2000, 1, 1)
_DAY_ANCHOR_IDX = 54

# 年柱锚点：1984 年 = 甲子年；立春为界（固定 2/4 近似）
_SPRING_FESTIVAL = (2, 4)

# 节气近似边界：(月, 日) → 进入的月支序号（寅=2）。此前一天仍属上一气。
# 近似误差 ±1 天，已足够餐饮场景；如需精排请接专业历法库。
_TERM_BOUNDS = [
    (1, 6, 1),   # 小寒 → 丑月
    (2, 4, 2),   # 立春 → 寅月（交立春同时换年柱）
    (3, 6, 3),   # 惊蛰 → 卯月
    (4, 5, 4),   # 清明 → 辰月
    (5, 6, 5),   # 立夏 → 巳月
    (6, 6, 6),   # 芒种 → 午月
    (7, 7, 7),   # 小暑 → 未月
    (8, 8, 8),   # 立秋 → 申月
    (9, 8, 9),   # 白露 → 酉月
    (10, 8, 10), # 寒露 → 戌月
    (11, 7, 11), # 立冬 → 亥月
    (12, 7, 0),  # 大雪 → 子月
]

# ---------------------------------------------------------------- 五行关系

SHENG = {"木": "火", "火": "土", "土": "金", "金": "水", "水": "木"}   # 我生（食伤）
KE = {"木": "土", "土": "水", "水": "火", "火": "金", "金": "木"}     # 我克（财）
BEI_SHENG = {v: k for k, v in SHENG.items()}                          # 生我（印）
BEI_KE = {v: k for k, v in KE.items()}                                # 克我（官杀）

WUXING_ATTR = {
    "木": {"味": "酸", "温": "温", "色": "青绿", "吉时": "03:00-09:00"},
    "火": {"味": "苦", "温": "热", "色": "赤红", "吉时": "09:00-15:00"},
    "土": {"味": "甘", "温": "平", "色": "黄", "吉时": "13:00-19:00"},
    "金": {"味": "辛", "温": "凉", "色": "白", "吉时": "15:00-21:00"},
    "水": {"味": "咸", "温": "寒", "色": "黑", "吉时": "21:00-03:00"},
}

# ---------------------------------------------------------------- 排盘


def _year_pillar(d: date) -> tuple[int, int]:
    """年柱干支序号，以立春（固定 2/4 近似）为界。"""
    y = d.year if (d.month, d.day) >= _SPRING_FESTIVAL else d.year - 1
    return (y - 4) % 10, (y - 4) % 12


def _month_pillar(d: date, year_gan_idx: int) -> tuple[int, int]:
    """月柱：节气定支，五虎遁定干。返回 (干序, 支序)。"""
    mday = (d.month, d.day)
    if mday < (1, 6):
        zhi = 0        # 大雪后小寒前 → 子月（年柱已按立春界回退到上一年，直接用该年干起遁）
    else:
        zhi = 2        # 兜底：立春后
        for bm, bd, bz in _TERM_BOUNDS:
            if mday >= (bm, bd):
                zhi = bz
        # 丑月（小寒后立春前）支序 1
        if (1, 6) <= mday < _SPRING_FESTIVAL:
            zhi = 1
        # 子月（大雪后）支序 0
        if mday >= (12, 7):
            zhi = 0
    first = (year_gan_idx % 5) * 2 + 2        # 五虎遁：甲己→丙寅起
    gan = (first + ((zhi - 2) % 12)) % 10     # 自寅月起算，支序需对 12 取模（子月 = 寅后 10 个月）
    return gan, zhi


def _day_pillar(d: date) -> tuple[int, int]:
    idx = (_DAY_ANCHOR_IDX + (d - _DAY_ANCHOR).days) % 60
    return idx % 10, idx % 12


def _hour_pillar(h: int, day_gan_idx: int) -> tuple[int, int]:
    """时柱：23 时起作次日子时算（晚子时归本日日柱，简化处理）。"""
    zhi = ((h + 1) // 2) % 12
    gan = ((day_gan_idx % 5) * 2 + zhi) % 10
    return gan, zhi


def paipan(year: int, month: int, day: int, hour: int) -> dict:
    """输入公历生辰，输出四柱、五行分布与简化喜用神。"""
    d = date(year, month, day)
    yg, yz = _year_pillar(d)
    mg, mz = _month_pillar(d, yg)
    dg, dz = _day_pillar(d)
    hg, hz = _hour_pillar(hour, dg)

    pillars = [
        {"label": "年柱", "gan": TIANGAN[yg], "zhi": DIZHI[yz]},
        {"label": "月柱", "gan": TIANGAN[mg], "zhi": DIZHI[mz]},
        {"label": "日柱", "gan": TIANGAN[dg], "zhi": DIZHI[dz]},
        {"label": "时柱", "gan": TIANGAN[hg], "zhi": DIZHI[hz]},
    ]

    counts = {"木": 0, "火": 0, "土": 0, "金": 0, "水": 0}
    for p in pillars:
        counts[GAN_WUXING[TIANGAN.index(p["gan"])]] += 1
        counts[ZHI_WUXING[DIZHI.index(p["zhi"])]] += 1

    day_master = GAN_WUXING[dg]
    same_party = counts[day_master] + counts[BEI_SHENG[day_master]] - 1  # 去掉日主自己重复计
    # same_party = 日主 + 印星（生我者）的总份数，衡量身强身弱

    # 忌神不做"禁吃"输出：命理讲"忌神有制化则不忌"，一律转成"以喜化忌"的搭档建议，
    # 保持"百味皆宜"的商业友好输出（详见 SKILL.md 红线）。
    if same_party >= 4:
        strength = "强"
        favor = [KE[day_master], SHENG[day_master]]      # 财 / 食伤泄秀
        partner = [BEI_SHENG[day_master]]
        resolve = "印重，以财破印——搭档与主角同点，五行流通"
    elif same_party <= 2:
        strength = "弱"
        favor = [BEI_SHENG[day_master], day_master]      # 印比生扶
        partner = [BEI_KE[day_master]]
        resolve = "杀重，以印化杀——搭档与主角同点，五行流通"
    else:
        strength = "中和"
        missing = [w for w, c in counts.items() if c == 0]
        favor = missing if missing else [SHENG[day_master]]
        partner = []
        resolve = "五行周全，百味皆宜"

    favor = [w for w in favor if w != day_master] or [SHENG[day_master]]
    partner = [w for w in partner if w not in favor]

    return {
        "input": {"date": f"{year:04d}-{month:02d}-{day:02d}", "hour": hour},
        "pillars": pillars,
        "day_master": day_master,
        "strength": strength,
        "counts": counts,
        "favor": favor,
        "partner": partner,
        "resolve": resolve,
        "tips": {
            w: WUXING_ATTR[w] for w in dict.fromkeys(favor + partner)
        },
        "disclaimer": "简化五行食养模型，仅供餐饮娱乐参考，非命理排盘、非医疗建议。",
    }


# ---------------------------------------------------------------- 菜单五行分类

# 分类优先级：温度（寒热）> 味（苦/酸/辣）> 形态（主食归土）
CLASSIFY_RULES = [
    (["冰", "圆筒", "圣代", "雪糕", "冰淇淋", "冰鲜", "可乐", "雪碧", "零度"], "水"),
    (["辣", "藤椒", "香辣", "麦辣"], "金"),
    (["咖啡", "美式", "浓缩", "茶", "拿铁"], "火"),
    (["柠檬", "苹果", "蔬菜", "沙拉", "玉米", "菠萝"], "木"),
    (["堡", "饭", "薯条", "派", "麦芬", "饼", "卷"], "土"),
    (["鸡", "牛", "猪", "鱼"], "土"),
]


def classify(item_name: str) -> str:
    for keywords, element in CLASSIFY_RULES:
        for kw in keywords:
            if kw in item_name:
                return element
    return "土"


# ---------------------------------------------------------------- CLI


def _print_report(chart: dict) -> None:
    print("── 麦门食养局 · 八字食养排盘 ──")
    print(f"公历：{chart['input']['date']} {chart['input']['hour']:02d} 时")
    print("四柱：" + "  ".join(f"{p['gan']}{p['zhi']}" for p in chart["pillars"]))
    print(f"日主：{chart['day_master']}（身{chart['strength']}）")
    print("五行：" + "  ".join(f"{w} {c}" for w, c in chart["counts"].items()))
    print(f"宜补（喜用）：{'、'.join(chart['favor'])}")
    if chart["partner"]:
        print(f"宜搭档（{chart['resolve']}）：{'、'.join(chart['partner'])}")
    else:
        print("五行周全，百味皆宜")
    for w, attr in chart["tips"].items():
        print(f"  {w}: {attr['温']}性 {attr['味']}味 · 吉时 {attr['吉时']}")
    print(chart["disclaimer"])


def main() -> int:
    ap = argparse.ArgumentParser(description="麦门食养局 · 八字五行排盘")
    ap.add_argument("--date", required=False, help="公历生日 YYYY-MM-DD")
    ap.add_argument("--hour", type=int, default=12, help="出生钟表小时 0-23（默认 12，缺时辰请自估并注明）")
    ap.add_argument("--json", action="store_true", help="输出 JSON（供 make_card.py / MCP 客户端消费）")
    ap.add_argument("--demo", action="store_true", help="离线演示：使用内置示例生辰")
    args = ap.parse_args()

    if args.demo:
        args.date, args.hour = "1988-06-15", 10
    if not args.date:
        ap.error("需要 --date 或 --demo")

    y, m, d = (int(x) for x in args.date.split("-"))
    chart = paipan(y, m, d, max(0, min(23, args.hour)))

    if args.json:
        json.dump(chart, sys.stdout, ensure_ascii=False, indent=2)
        print()
    else:
        _print_report(chart)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
