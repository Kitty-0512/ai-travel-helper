# Demo Screenshots

本地真实跑通 Agent 后用 Playwright 截取（`scripts/capture-readme-screens.mjs`）。

| 文件 | 说明 |
|------|------|
| `01-empty.png` | 初始空状态，流程豆豆未开始 |
| `02-form-ready.png` | 已填杭州 / 3 天 / 风格，可点生成 |
| `03-generating-flow.png` | 豆豆第 1 步「理解需求」，右侧执行状态 |
| `04-tools.png` | 生成早期状态（截取时机偏早时可能与 03 接近） |
| `05-result.png` | 豆豆进入「生成行程」，工具调用 + 流式正文 |
| `06-map.png` | 行程文案 + 地图工作台同屏 |

左侧 **Agent 执行流程** 四步：理解需求 → 调用工具 → 生成行程 → 完成。
