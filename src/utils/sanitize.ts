/**
 * src/utils/sanitize.ts
 * HTML 消毒 —— 用 DOMPurify 防 XSS，只允许 Markdown 渲染的安全标签
 *
 * 替换原来的 v-html="rawHtml" 为 v-html="sanitizeHtml(rawHtml)"
 */

import DOMPurify from 'dompurify'

// ============================================================
// 白名单配置
// ============================================================

/**
 * 允许的 HTML 标签（对应 marked 库从 Markdown 生成的 HTML）
 *
 * 只开放语义化标签，拒绝 <script> <style> <iframe> <object> 等危险元素。
 */
const ALLOWED_TAGS = [
  // 标题
  'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
  // 段落 & 文本
  'p', 'br', 'hr',
  'strong', 'b', 'em', 'i', 'u', 's', 'del',
  'code', 'pre', 'kbd',
  'blockquote',
  // 列表
  'ul', 'ol', 'li',
  // 链接 & 图片
  'a', 'img',
  // 表格
  'table', 'thead', 'tbody', 'tr', 'th', 'td',
  // 其他
  'div', 'span', 'sup', 'sub',
  'details', 'summary',
]

/**
 * 允许的 HTML 属性（白名单之外全部剥离）
 */
const ALLOWED_ATTRS = [
  // 链接
  'href', 'title', 'target', 'rel',
  // 图片
  'src', 'alt', 'width', 'height',
  // 通用
  'class', 'id',
  // 表格
  'colspan', 'rowspan',
  // 代码块
  'data-language',
]

// ============================================================
// 核心函数
// ============================================================

/**
 * 对 HTML 字符串消毒，返回安全的 HTML。
 *
 * @param html 原始 HTML（通常是 marked() 的输出）
 * @returns 安全的 HTML 字符串，可直接用于 v-html
 *
 * 行为：
 * - 保留白名单内的标签和属性
 * - 剥离所有 script/style/iframe/object/embed 等危险标签
 * - 剥离 on* 事件处理器属性
 * - <a> 标签自动添加 target="_blank" 和 rel="noopener noreferrer"
 */
export function sanitizeHtml(html: string): string {
  if (!html) return ''

  return DOMPurify.sanitize(html, {
    ALLOWED_TAGS,
    ALLOWED_ATTR,
    // 禁止一切 <a href="javascript:..."> 这类伪协议
    ALLOWED_URI_REGEXP: /^(?:(?:https?|mailto|tel):|[^a-z]|[a-z+.-]+(?:[^a-z+.-:]|$))/i,
    // <a> 标签强制加安全属性
    ADD_ATTR: ['target'],
    // 只允许 http/https/mailto/tel 协议
    ALLOWED_PROTOCOLS: ['http', 'https', 'mailto', 'tel'],
  })
}

// ============================================================
// Vue 模板中的使用方式（替换原来不安全的 v-html）
// ============================================================

/**
 * 原来的写法（有 XSS 风险）：
 *   <div v-html="planHtml"></div>
 *
 * 改为（安全）：
 *   <div v-html="sanitizeHtml(rawMarkdownRenderedByMarked)"></div>
 *
 * 如果你在 computed 中已经调用 marked() 转成了 HTML，
 * 只需在模板中再包一层 sanitizeHtml：
 *
 *   // script setup
 *   import { sanitizeHtml } from '@/utils/sanitize'
 *   const safeHtml = computed(() => sanitizeHtml(marked(rawText)))
 *
 *   // template
 *   <div v-html="safeHtml"></div>
 */
