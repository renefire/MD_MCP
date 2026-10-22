# MCP 集成说明（MCP INTEGRATION）

## 1. 接入概览

| 项目 | 内容 |
|---|---|
| 协议 | MCP（Model Context Protocol），Streamable HTTP 传输 |
| 服务方 | 麦当劳中国官方（open.mcd.cn 开放平台） |
| 客户端实现 | `scripts/mcp_client.py`（Python 3 标准库，零第三方依赖） |
| 认证 | `Authorization: Bearer <MCD_MCP_TOKEN>`，Token 仅存环境变量 |
| 会话 | 遵循 `initialize` → `notifications/initialized` → `tools/*`，透传 `Mcp-Session-Id` |

## 2. Token 获取（免费）

1. 访问 https://open.mcd.cn → 手机号登录；
2. 右上角【控制台】→【激活】申请 MCP Token（需审核，建议尽早）；
3. `export MCD_MCP_TOKEN="..."`（Windows: `set MCD_MCP_TOKEN=...`）；
4. 如控制台下发的 endpoint 与默认值不同：`export MCD_MCP_ENDPOINT="..."`。

## 3. 调用链路

```
McDonaldMCP._ensure_session()          # initialize + initialized 通知
        ↓
McDonaldMCP.list_tools()               # tools/list，动态发现能力
        ↓
按工具名探测菜单类工具（名称含 meal/menu）
        ↓
McDonaldMCP.call_tool(name, args)      # tools/call，解析 text/plain → JSON
        ↓
返回 (items, source="mcp")
```

- 不假设任何写死的服务端字段：菜单键名按 `items` / `meals` 依次探测，取不到即降级；
- SSE（`text/event-stream`）响应按行解析 `data:` 载荷，取第一条合法 JSON-RPC 结果。

## 4. 降级策略（红线）

| 场景 | 行为 |
|---|---|
| 无 `MCD_MCP_TOKEN` | 不发起任何网络请求，直接用 `references/reference_menu.json`，产物标注"离线参考数据" |
| 网络失败 / 5xx / 超时 | 抛 `MCPUnavailable`，向用户如实说明，降级同上 |
| 工具返回字段缺失 | 金额/热量写 `-`，禁止用训练记忆补数 |
| 限流（429 类） | 等待后重试一次并告知用户，仍失败即降级 |

## 5. 安全约束

1. Token 绝不写入仓库、日志、对话导出（`workbuddy.md` 导出前须脱敏检查）；
2. 本作品不调用任何下单/支付类写工具；后续若接入，必须双重确认（对话层完整复述载荷 + 脚本层 `--confirm` 参数）；
3. 探测脚本输出自动脱敏：`Authorization` 头与 Session-Id 永不打印。

## 6. 实测记录（2026-10-22 已通）

- [x] initialize 握手成功（endpoint: https://mcp.mcd.cn）
- [x] tools/list 返回工具数：35
- [x] 菜单链路实测：query-nearby-stores（city 需"上海市"且 keyword 必填）→ query-meals（仅 code）→ query-meal-detail（名字）→ calculate-price（单位为分，1300 = ¥13.00）
- [x] 营养数据：list-nutrition-foods 返回 160 项官方营养表
- [x] 端到端：食养卡数据源自动切换为 mcp，卡面标注实测门店
- [x] 降级路径：无 Token 时走参考菜单并标注
- 详见 `references/mcp_tools.md` 踩坑实录
