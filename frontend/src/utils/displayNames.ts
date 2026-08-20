/**
 * 展示层中文名映射
 * 将后端返回的英文枚举（工具类型/支付方式）统一转换为中文展示名，
 * 避免交易记录、统计图表等处出现晦涩英文。
 */

export const TOOL_TYPE_NAMES: Record<string, string> = {
  wechat_article: '公众号文章',
  xiaohongshu_note: '小红书笔记',
  official_document: '公文写作',
  paper: '论文写作',
  academic_paper: '论文写作',
  marketing_copy: '营销文案',
  news_article: '新闻软文',
  press_release: '新闻软文',
  video_script: '短视频脚本',
  story: '故事小说',
  story_novel: '故事小说',
  business_plan: '商业计划书',
  work_report: '工作报告',
  resume: '简历求职',
  lesson_plan: '教案课件',
  rewrite: '内容改写',
  content_rewrite: '内容改写',
  translation: '多语翻译',
  viral_analyze: '爆款分析',
  viral_imitate: '爆款模仿',
  image: '图片生成',
  video: '视频生成',
  ppt: 'PPT生成',
  ppt_editor: 'PPT生成',
  ppt_outline: 'PPT生成',
}

export const PAYMENT_NAMES: Record<string, string> = {
  alipay: '支付宝',
  wechat: '微信支付',
  wechat_pay: '微信支付',
}

export function formatToolName(name?: string): string {
  if (!name) return '未知'
  return TOOL_TYPE_NAMES[name] || PAYMENT_NAMES[name] || name
}

export function formatDescription(desc?: string): string {
  if (!desc) return ''
  let text = desc
  const keys = Object.keys(TOOL_TYPE_NAMES).sort((a, b) => b.length - a.length)
  for (const key of keys) {
    text = text.replace(new RegExp(`\\b${key}\\b`, 'g'), TOOL_TYPE_NAMES[key])
  }
  return text
}
