# MCP 工具链实测记录

> 实测日期：2026-10-22 · 实测门店：麦当劳上海黄浦悦荟广场餐厅（storeCode 1450104）

## 在线工具清单（tools/list 返回 35 个）

| 工具 | 用途 | 本作品用法 |
|---|---|---|
| now-time-info | 服务器时间 | 排盘日期校验 |
| list-nutrition-foods | 官方营养表（160 项，kcal/蛋白/钠等） | **核心**：食养卡 kcal 数据源 + 商品池扩充 |
| query-nearby-stores | 门店查询 | **核心**：定位门店 |
| query-meals | 菜单分类+code（无名字无价格） | **核心**：取 code 列表 |
| query-meal-detail | 套餐详情（名字+默认子项） | **核心**：取餐品名 |
| calculate-price | 实时核价（含优惠） | **核心**：实价展示 |
| available-coupons / auto-bind-coupons | 优惠券查询/领取 | 备选增强（未接入） |
| create-order / party-order-create 等写工具 | 下单 | **红线：默认不接入** |

## 实测要点（踩坑实录）

1. **接入地址是 `https://mcp.mcd.cn`**，不是 open.mcd.cn；Streamable HTTP，Bearer Token 认证；每 Token 600 请求/分钟。
2. **响应是包装文档不是纯 JSON**：text 内容 = 字段说明 + 内嵌 JSON（有的带 `## Original Response` 标题，有的直接裸内嵌），`mcd_parse.py` 两层解包 + 括号配平兜底。
3. **query-nearby-stores 的 city 必须 "上海市" 且 keyword 不能空**：`{'beType':1,'searchType':2,'city':'上海'}` 返回 600058 城市名或关键词为空。
4. **query-meals 只给 code**：名字在 query-meal-detail，价格在 calculate-price，三跳才能拼出完整商品。
5. **价格单位是分**：calculate-price 返回 1300 = ¥13.00（与赛事其他选手实测一致）。
6. **通知返回 202 空响应体**：notifications/initialized 解析空 body 属正常。
7. **名字匹配**：商品名带 ™/® 时营养表模糊匹配需归一化；个别商品（如麦咖啡冰奶铁）不在营养表，kcal 如实显示 `?`。

## 验证清单

- [x] initialize 握手成功
- [x] tools/list 返回工具数：35
- [x] 菜单链路：门店 → code → 详情 → 实价 全通
- [x] 营养表 160 项解析成功（含类型化字段）
- [x] 端到端：食养卡数据源自动切换为 mcp（示例食养卡.html）
- [x] 降级路径：无 Token 时走参考菜单并标注
- [ ] 429 限流实测（未触发，600/min 余量大）
