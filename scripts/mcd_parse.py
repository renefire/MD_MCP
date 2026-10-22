#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
麦门食养局 · MCP 响应包装解析器

麦当劳 MCP 的 text 内容不是纯 JSON，而是"字段说明 + 原始响应"的包装文档：
    # API Response Information
    ...
    ## Original Response
    {"success":true,...,"data":"[160]{col1,col2,...}:\n  row1\n  row2 ..."}

本模块负责两层解包：
    1. 提取 "## Original Response" 后的 JSON；
    2. 若 data 是 "[N]{col,...}:\n rows" 形式的内嵌表字符串，解析为 dict 列表。
"""

from __future__ import annotations

import json
import re

_ORIGINAL_RE = re.compile(r"##\s*Original Response\s*\n(.*?)(?:\n##\s|\Z)", re.S)
_TABLE_RE = re.compile(r"^\[(\d+)\]\{([^}]*)\}:\s*\n(.*)$", re.S)


def _extract_first_json(s: str):
    """扫描正文，提取第一个括号配平的 JSON 对象（兼容有无 Original Response 标题两种包装）。"""
    start = s.find("{")
    while start != -1:
        depth, in_str, esc = 0, False, False
        for i in range(start, len(s)):
            ch = s[i]
            if in_str:
                if esc:
                    esc = False
                elif ch == "\\":
                    esc = True
                elif ch == '"':
                    in_str = False
                continue
            if ch == '"':
                in_str = True
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(s[start : i + 1])
                    except json.JSONDecodeError:
                        break
        start = s.find("{", start + 1)
    return None


def parse_wrapper(raw: str):
    """输入 call_tool 拿到的 text，返回结构化数据（dict / list / 原文）。"""
    if raw.strip().startswith("{") or raw.strip().startswith("["):
        # 本身就是 JSON
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            pass
    m = _ORIGINAL_RE.search(raw)
    if m:
        try:
            payload = json.loads(m.group(1).strip())
        except json.JSONDecodeError:
            payload = None
        if payload is not None:
            return _unwrap_table(payload)
    payload = _extract_first_json(raw)   # 兜底：正文内嵌 JSON，无标题包装
    if payload is not None:
        return _unwrap_table(payload)
    return {"raw": raw}


def _unwrap_table(payload):
    if isinstance(payload, dict) and isinstance(payload.get("data"), str):
        table = parse_embedded_table(payload["data"])
        if table is not None:
            payload = dict(payload)
            payload["data"] = table
    return payload


def parse_embedded_table(s: str):
    """解析 "[N]{col1,col2}:\\n rows" 形式的内嵌表；不匹配返回 None。"""
    m = _TABLE_RE.match(s.strip())
    if not m:
        return None
    _count, cols_raw, body = m.groups()
    cols = [c.strip() for c in cols_raw.split(",")]
    rows = []
    for line in body.splitlines():
        line = line.strip()
        if not line:
            continue
        vals = [v.strip() for v in line.split(",")]
        if len(vals) < len(cols):
            vals += [None] * (len(cols) - len(vals))
        rows.append(dict(zip(cols, vals[: len(cols)])))
    return rows


def _norm(v):
    """'null'/空 → None；数字串 → 数值。"""
    if v is None:
        return None
    v = v.strip() if isinstance(v, str) else v
    if v in ("null", "", "None", "-"):
        return None
    if isinstance(v, str) and re.fullmatch(r"-?\d+(\.\d+)?", v):
        return float(v) if "." in v else int(v)
    return v


def normalize_rows(rows: list) -> list:
    return [{k: _norm(v) for k, v in r.items()} for r in rows]
