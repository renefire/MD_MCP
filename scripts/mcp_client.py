#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
麦门食养局 · 麦当劳 MCP 客户端（仅标准库）

用法：
    from mcp_client import McDonaldMCP, load_reference_menu
    mcp = McDonaldMCP()                 # 自动读环境变量 MCD_MCP_TOKEN / MCD_MCP_ENDPOINT
    menu, source = mcp.get_menu(city="上海", keyword="麦当劳")

设计红线：
  - Token 只从环境变量读取，绝不写死、绝不落盘、绝不写进配置文件；
  - 无 Token 或网络失败 → 抛 MCPUnavailable，由调用方降级到参考菜单，
    且降级产物必须标注"离线参考数据"，禁止冒充实时数据。
"""

from __future__ import annotations

import json
import os
import urllib.request
from pathlib import Path

DEFAULT_ENDPOINT = "https://mcp.mcd.cn"   # 官方接入地址（open.mcd.cn/mcp/doc），Streamable HTTP
REFERENCE_MENU = Path(__file__).resolve().parent.parent / "references" / "reference_menu.json"

_JSON_HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json, text/event-stream",
}


class MCPUnavailable(Exception):
    """无 Token / 网络失败 / 服务端错误，调用方应降级。"""


def _norm_name(s: str) -> str:
    """名字归一：去 ™®、去空白，供营养表模糊匹配。"""
    for ch in ("™", "®", " ", "\u3000"):
        s = s.replace(ch, "")
    return s


def load_reference_menu() -> dict:
    with open(REFERENCE_MENU, encoding="utf-8") as f:
        return json.load(f)


class McDonaldMCP:
    def __init__(self, token: str | None = None, endpoint: str | None = None, timeout: int = 20):
        self.token = token or os.environ.get("MCD_MCP_TOKEN", "").strip()
        self.endpoint = endpoint or os.environ.get("MCD_MCP_ENDPOINT", "").strip() or DEFAULT_ENDPOINT
        self.timeout = timeout
        self._id = 0
        self._session_ready = False
        self._session_id: str | None = None

    @property
    def available(self) -> bool:
        return bool(self.token)

    # -------------------------------------------------------- JSON-RPC 底座

    def _next_id(self) -> int:
        self._id += 1
        return self._id

    def _post(self, payload: dict) -> dict:
        headers = dict(_JSON_HEADERS)
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        if self._session_id:
            headers["Mcp-Session-Id"] = self._session_id
        req = urllib.request.Request(
            self.endpoint, data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers=headers, method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                sid = resp.headers.get("Mcp-Session-Id")
                if sid:
                    self._session_id = sid
                ctype = resp.headers.get("Content-Type", "")
                body = resp.read().decode("utf-8", errors="replace")
        except Exception as e:  # 网络层任何失败都不可静默
            raise MCPUnavailable(f"MCP 请求失败: {e}") from e

        if "text/event-stream" in ctype:
            return self._parse_sse(body)
        return self._parse_jsonrpc(body)

    @staticmethod
    def _parse_sse(body: str) -> dict:
        """极简 SSE 解析：取第一条 data: 行里的 JSON-RPC 响应。"""
        for line in body.splitlines():
            line = line.strip()
            if line.startswith("data:"):
                data = line[5:].strip()
                if data and data != "[DONE]":
                    try:
                        return json.loads(data)
                    except json.JSONDecodeError:
                        continue
        raise MCPUnavailable("SSE 响应中未找到 JSON-RPC 数据")

    @staticmethod
    def _parse_jsonrpc(body: str) -> dict:
        if not body.strip():
            return {}   # 通知类请求服务端常回 202 空响应体，属正常
        try:
            msg = json.loads(body)
        except json.JSONDecodeError as e:
            raise MCPUnavailable(f"响应不是合法 JSON: {e}") from e
        if isinstance(msg, list):   # 通知批次，取首个带 id 的
            msg = next((m for m in msg if m.get("id") is not None), {})
        if "error" in msg:
            raise MCPUnavailable(f"MCP 错误: {msg['error']}")
        return msg

    def _rpc(self, method: str, params: dict | None = None, notify: bool = False) -> dict | None:
        payload = {"jsonrpc": "2.0", "method": method}
        if params is not None:
            payload["params"] = params
        if notify:
            payload.pop("id", None)
            self._post(payload)     # 通知的响应可忽略
            return None
        payload["id"] = self._next_id()
        return self._post(payload)

    # -------------------------------------------------------- 生命周期

    def _ensure_session(self) -> None:
        if self._session_ready:
            return
        if not self.available:
            raise MCPUnavailable("未配置 MCD_MCP_TOKEN（open.mcd.cn 免费申请），降级到离线参考菜单")
        result = self._rpc("initialize", {
            "protocolVersion": "2025-03-26",
            "capabilities": {},
            "clientInfo": {"name": "mcd-shiyangju", "version": "0.1.0"},
        })
        if result is None:
            raise MCPUnavailable("initialize 无响应")
        self._rpc("notifications/initialized", {}, notify=True)
        self._session_ready = True

    # -------------------------------------------------------- 业务封装

    def list_tools(self) -> list:
        self._ensure_session()
        result = self._rpc("tools/list", {})
        return (result or {}).get("result", {}).get("tools", [])

    def call_tool(self, name: str, arguments: dict) -> dict:
        """返回解包后的结构化内容；失败抛 MCPUnavailable。"""
        self._ensure_session()
        result = self._rpc("tools/call", {"name": name, "arguments": arguments})
        content = (result or {}).get("result", {}).get("content", [])
        texts = [c.get("text", "") for c in content if c.get("type") == "text"]
        raw = "\n".join(t for t in texts if t)
        if not raw:
            return {}
        from mcd_parse import parse_wrapper, normalize_rows
        parsed = parse_wrapper(raw)
        if isinstance(parsed, dict) and isinstance(parsed.get("data"), list):
            parsed["data"] = normalize_rows(parsed["data"])
        return parsed

    def get_menu(self, city: str = "上海市", keyword: str = "麦当劳", detail_limit: int = 10) -> tuple[list, str, dict]:
        """
        实时菜单全链路（实测 2026-10-22，上海黄浦悦荟广场店）：
          query-nearby-stores(beType=1, searchType=2, city=上海市, keyword=麦当劳)
            → query-meals(orderType=1, beType=1, storeCode)  → 只有分类+code，无名字
            → query-meal-detail(storeCode, code)             → 套餐名 + 默认子项 productCode
            → calculate-price(items=[{productCode, quantity:1}]) → 实价，单位是"分"！1300 = ¥13.00
            → list-nutrition-foods()                          → 160 行官方营养表（kcal 等）
        返回 (items, source, meta)；items 元素：{name, price(元|None), kcal(官方|None), code}。
        """
        self._ensure_session()
        stores = self.call_tool("query-nearby-stores", {
            "beType": 1, "searchType": 2, "city": city, "keyword": keyword,
        }).get("data") or []
        if not stores:
            raise MCPUnavailable(f"未查询到门店（city={city}, keyword={keyword}）")
        store = stores[0]
        sc = store["storeCode"]

        meals = self.call_tool("query-meals", {"orderType": 1, "beType": 1, "storeCode": sc}).get("data") or {}
        codes: list = []
        for cat in meals.get("categories", []):
            for meal in cat.get("meals", []):
                c = meal.get("code")
                if c and c not in codes:
                    codes.append(c)

        items: list = []
        for code in codes[:detail_limit]:
            try:
                d = self.call_tool("query-meal-detail", {
                    "orderType": 1, "beType": 1, "storeCode": sc, "code": code,
                })
            except MCPUnavailable:
                continue
            dd = d.get("data") or {}
            name = dd.get("name")
            if not name:
                continue
            # 取套餐第一个默认子项作为核价主体；单品即自身
            pcode = code
            for r in dd.get("rounds", []):
                default = next((ch for ch in r.get("choices", []) if ch.get("isDefault") == 1), None)
                if default and default.get("code"):
                    pcode = default["code"]
                    break
            price = None
            try:
                pr = self.call_tool("calculate-price", {
                    "orderType": 1, "beType": 1, "storeCode": sc,
                    "items": [{"productCode": pcode, "quantity": 1}],
                })
                pd = pr.get("data") or {}
                if pd.get("price") is not None:
                    price = round(pd["price"] / 100, 1)   # 分 → 元
            except MCPUnavailable:
                pass
            items.append({"name": name, "price": price, "kcal": None, "code": code})

        nutri = self.call_tool("list-nutrition-foods", {}).get("data") or []
        kcal_by_name = {r["productName"]: r.get("energyKcal") for r in nutri if r.get("productName")}
        for it in items:
            if it["kcal"] is None:
                it["kcal"] = self._match_kcal(it["name"], kcal_by_name)
        # 把官方营养表全量并入商品池（无价格，kcal 齐全），保证五行映射的覆盖面
        have = {_norm_name(i["name"]) for i in items}
        for pn, kcal in kcal_by_name.items():
            if _norm_name(pn) not in have:
                items.append({"name": pn, "price": None, "kcal": kcal, "code": None})

        meta = {"storeName": store.get("storeName"), "storeCode": sc}
        return items, "mcp", meta

    @staticmethod
    def _match_kcal(name: str, kcal_by_name: dict):
        n = _norm_name(name)
        if n in kcal_by_name:
            return kcal_by_name[n]
        for pn, k in kcal_by_name.items():
            p = _norm_name(pn)
            if p and (n.startswith(p) or p.startswith(n)):
                return k
        return None


if __name__ == "__main__":
    m = McDonaldMCP()
    if not m.available:
        print("[离线] 未配置 MCD_MCP_TOKEN，参考菜单自检：")
        ref = load_reference_menu()
        print(f"  参考菜单 {len(ref['items'])} 项 · {ref['_meta']['note']}")
        raise SystemExit(0)
    tools = m.list_tools()
    print(f"[在线] MCP 可用，共 {len(tools)} 个工具：")
    for t in tools:
        print(f"  - {t.get('name')}: {t.get('description', '')[:60]}")
