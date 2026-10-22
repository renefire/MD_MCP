# 麦门食养局 · McDonald's Five-Elements Butler

> 以**真实八字五行算法**替你决定这一顿麦当劳。不是随机抽签——同一生辰、同一天，全世界算出同一个套餐。

🏆 2026 麦当劳程序员创意开发大赛参赛作品（使用 [腾讯 WorkBuddy](https://www.workbuddy.cn) 开发）

## 这是什么

市面上的"运势点餐"多为伪玄学随机数。本作品用的是**确定性、可开源验证**的简化八字五行模型：

```
公历生辰（+时辰）
    ↓  scripts/bazi_wuxing.py        ← 干支历法算法（立春界年柱 / 节气月柱 / 锚点日柱 / 五虎遁时柱）
四柱八字 + 五行分布
    ↓  简化强弱判法                    ← 日主+印星份数 → 身强/弱/中和 → 喜用神与忌神
宜补五行 + 慎点五行
    ↓  scripts/mcp_client.py          ← 麦当劳官方 MCP 实时菜单/价格（无 Token 自动降级参考菜单）
今日宜吃 / 慎点 / 吉时
    ↓  scripts/make_card.py
单文件 HTML 五行食养卡（可直接转发朋友圈）
```

## 为什么是"真术数"

- 算法公开可验证：`bazi_wuxing.py` 内置历法锚点 `2000-01-01 12:00 = 己卯 丙子 戊午 戊午`，任何人可复算；
- 确定性传播钩子：把生日发给朋友，同一天算出的结果一致，天然引发"你算的和我一样吗"的讨论；
- 诚实的简化声明：节气边界 ±1 天近似、地支取本气、喜用神为启发式——README 敢写，README 里没有魔法。

## 快速开始（离线即可玩）

```bash
# 1. 离线排盘（无需 Token）
python scripts/bazi_wuxing.py --date 1988-06-15 --hour 10

# 2. 生成五行食养卡（无 Token 自动用参考菜单，卡片底部如实标注）
python scripts/make_card.py --date 1988-06-15 --hour 10 --name 你的名字 -o 我的食养卡.html

# 3. 接入官方实时数据（免费）
#    open.mcd.cn → 手机号登录 → 控制台 → 激活 → 复制 Token
export MCD_MCP_TOKEN="你的Token"
python scripts/make_card.py --date 1988-06-15 --hour 10 --name 你的名字 -o 我的食养卡.html
```

零第三方依赖，纯 Python 标准库。

## 与官方 MCP 的关系

通过 MCP 协议调用麦当劳中国开放能力（菜单/门店/价格等，以 `tools/list` 实际返回为准）。全部调用可审计：
- Token 只从环境变量读取，不落盘、不入库；
- 查询失败明确降级并标注数据来源，禁止用缓存或训练记忆冒充实时数据。

详见 [MCP_INTEGRATION.md](MCP_INTEGRATION.md)。

## 目录结构

```
mcd-shiyangju/
├── skill/SKILL.md                 # WorkBuddy 技能定义（五步工作流 + 六条红线）
├── scripts/
│   ├── bazi_wuxing.py             # 八字五行核心算法（含验证锚点）
│   ├── mcp_client.py              # stdlib-only MCP 客户端（含降级策略）
│   └── make_card.py               # 单文件 HTML 食养卡生成器
├── references/
│   ├── reference_menu.json        # 离线参考菜单（仅降级演示用）
│   └── mcp_tools.md               # MCP 工具链实测记录
├── CONTEST_DECLARATION.md         # 参赛声明
├── MCP_INTEGRATION.md             # MCP 集成说明
├── workbuddy.md                   # WorkBuddy 开发对话导出（专项奖材料）
└── 示例食养卡.html                 # 开箱即看的演示产物
```

## 免责声明

本项目的五行映射为**餐饮娱乐向的创意演绎**（先按寒热温度、再按五味、主食归土），不是中医或命理排盘软件；输出仅供娱乐，不构成医疗、养生建议。算法简化点均在代码注释与 SKILL.md 中如实披露。
