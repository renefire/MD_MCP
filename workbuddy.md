# workbuddy.md — 腾讯 WorkBuddy 开发对话导出（专项奖申报材料）

> 本文件用于申报"真实使用腾讯 WorkBuddy 开发"专项奖（3000 积分）。
> 提交前必须：① 确认对话记录完整（从立项到交付）；② 脱敏检查（Token、密钥、个人隐私一律删除）。

## 开发过程摘要（占位，用 WorkBuddy 导出的对话替换）

### 第一轮：立项与竞品调研
- 指令：检索麦当劳 MCP 大赛规则与已有参赛作品，评估赛道饱和度
- 结论：运势抽签赛道已有 2+ 作品（伪玄学随机），"真术数"方向空缺，确立差异化主线

### 第二轮：算法与骨架
- 指令：实现八字五行排盘算法（含验证锚点）+ 菜单五行映射
- 产出：scripts/bazi_wuxing.py、references/reference_menu.json
- 关键决策：简化判法（身强泄克/身弱生扶/中和补缺）+ 诚实披露简化点

### 第三轮：MCP 客户端与食养卡
- 指令：stdlib-only MCP 客户端（降级策略红线）+ 单文件 HTML 食养卡
- 产出：scripts/mcp_client.py、scripts/make_card.py、示例食养卡.html
- 实测抓 bug：五虎遁月干未对 12 取模（子月算错），锚点用例回归修复

### 第四轮：待办
- [ ] 申请 MCP Token 并实测 tools/list、菜单工具字段结构
- [ ] 更新 MCP_INTEGRATION.md 实测记录
- [x] 开源 GitHub 仓库：https://github.com/renefire/MD_MCP
- [ ] 活动页面 Issue 模板报名

<!-- 用 WorkBuddy「导出对话」功能产出完整 MD 后，粘贴替换本节并删除此注释行 -->
