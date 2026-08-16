/**
 * AIPPT 数据桥接：跨页面传递 PPT 生成数据
 *
 * 背景：上传模板的布局数据可能很大（大量元素 / base64 图片），
 * localStorage 默认配额约 5MB，直接 setItem 会抛 QuotaExceededError。
 * 方案：优先内存缓存（SPA 路由跳转不刷新页面），localStorage 仅作兜底。
 */

let memoryData: any = null

export function saveAIPPTData(data: any): void {
  memoryData = data
  try {
    localStorage.setItem('pptist_aippt_data', JSON.stringify(data))
  } catch (e) {
    console.warn('[aippt] localStorage 存储超限，已改用内存缓存', e)
  }
}

export function loadAIPPTData(): any {
  if (memoryData !== null) return memoryData
  try {
    const dataJson = localStorage.getItem('pptist_aippt_data')
    return dataJson ? JSON.parse(dataJson) : null
  } catch (e) {
    console.error('[aippt] 读取 AIPPT 数据失败:', e)
    return null
  }
}

export function clearAIPPTData(): void {
  memoryData = null
  try {
    localStorage.removeItem('pptist_aippt_data')
  } catch (e) {
    console.warn('[aippt] 清理 AIPPT 数据失败:', e)
  }
}
