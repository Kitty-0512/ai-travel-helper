# Vue 3 + TypeScript + Vite

This template should help get you started developing with Vue 3 and TypeScript in Vite. The template uses Vue 3 `<script setup>` SFCs, check out the [script setup docs](https://v3.vuejs.org/api/sfc-script-setup.html#sfc-script-setup) to learn more.

Learn more about the recommended Project Setup and IDE Support in the [Vue Docs TypeScript Guide](https://vuejs.org/guide/typescript/overview.html#project-setup).
✈️ AI Travel Assistant

一个基于 Vue3 + Vite + AI大模型 + 高德地图 的智能旅行规划系统。

🚀 在线体验

👉 https://kitty-0512.github.io/ai-travel-helper/

📌 项目简介

本项目是一个 AI 驱动的旅行规划工具，用户只需输入：

目的地
旅行天数
旅行风格（美食 / 自然 / 文化等）

系统即可自动生成：

🧠 AI 行程规划
🗺️ 地图路线展示（高德地图）
📍 景点标记与路径规划
📄 PDF 行程导出
⚙️ 技术栈
Vue 3（Composition API）
Vite
TypeScript
TailwindCSS
高德地图 AMap JS API
DeepSeek / OpenAI API（AI生成行程）
html2canvas + jsPDF（PDF导出）
✨ 核心功能
🧠 AI 行程生成

基于大模型自动生成每日旅行计划。

🗺️ 地图路线规划

支持：

驾车路线
步行路线
骑行路线
直线连线模式
📍 景点可视化

自动解析 AI 输出，生成地图标记点。

📄 行程导出

一键导出 PDF 行程单。

📱 移动端适配

支持手机浏览器直接使用。

🧩 项目亮点
AI + 地图结合的真实应用场景
自动解析自然语言生成结构化行程
支持多路线算法切换
可扩展为“智能出行 Agent”
📦 本地运行
npm install
npm run dev
🌐 部署
npm run build
npm run deploy

🧠 后续优化方向
接入多模型（GPT / DeepSeek / Claude）
加入酒店/餐厅推荐
增加用户收藏系统
加入实时天气数据
做成完整“AI旅行Agent”
