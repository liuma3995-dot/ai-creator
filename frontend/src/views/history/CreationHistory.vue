<template>
  <div class="creation-history">
    <section class="page-hero">
      <div>
        <p class="eyebrow">Creation Archive</p>
        <h1>创作历史</h1>
        <p class="description">查看历史创作记录，按工具类型和时间快速筛选，并继续编辑已有内容。</p>
      </div>
    </section>

    <el-card class="glass-card filter-card">
      <template #header>
        <div class="panel-head"><div><h3>筛选条件</h3><p>按工具、时间和关键词快速定位历史内容。</p></div></div>
      </template>
      <el-form :inline="true" :model="filterForm" class="filter-form">
        <el-form-item label="工具类型">
          <el-select v-model="filterForm.toolType" placeholder="全部" clearable class="field-150">
            <el-option label="公众号文章" value="wechat_article" />
            <el-option label="小红书笔记" value="xiaohongshu_note" />
            <el-option label="公文写作" value="official_document" />
            <el-option label="营销文案" value="marketing_copy" />
          </el-select>
        </el-form-item>
        <el-form-item label="创建时间">
          <el-date-picker v-model="filterForm.dateRange" type="daterange" range-separator="至" start-placeholder="开始日期" end-placeholder="结束日期" class="field-240" />
        </el-form-item>
        <el-form-item label="搜索">
          <el-input v-model="filterForm.keyword" placeholder="标题或内容关键词" clearable class="field-220">
            <template #prefix><el-icon><Search /></el-icon></template>
          </el-input>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="handleSearch"><el-icon><Search /></el-icon>搜索</el-button>
          <el-button @click="handleReset">重置</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <el-card class="glass-card list-card">
      <template #header>
        <div class="panel-head panel-row"><div><h3>历史记录</h3><p>支持查看详情、继续编辑和删除记录。</p></div></div>
      </template>

      <div class="table-view">
        <el-table v-loading="loading" :data="creationList" style="width: 100%" @row-click="handleRowClick">
          <el-table-column prop="title" label="标题" min-width="220">
            <template #default="{ row }">
              <div class="title-cell">
                <el-icon :color="getToolColor(row.tool_type)"><component :is="getToolIcon(row.tool_type)" /></el-icon>
                <span>{{ row.title || '未命名内容' }}</span>
              </div>
            </template>
          </el-table-column>
          <el-table-column prop="tool_type" label="工具类型" width="140">
            <template #default="{ row }"><el-tag :type="getToolTagType(row.tool_type)" size="small" effect="plain">{{ getToolName(row.tool_type) }}</el-tag></template>
          </el-table-column>
          <el-table-column label="内容预览" min-width="300">
            <template #default="{ row }"><div class="content-preview">{{ getContentPreview(row.output_content || row.content) }}</div></template>
          </el-table-column>
          <el-table-column prop="created_at" label="创建时间" width="180">
            <template #default="{ row }">{{ formatDate(row.created_at) }}</template>
          </el-table-column>
          <el-table-column label="操作" width="220" fixed="right">
            <template #default="{ row }">
              <el-button size="small" @click.stop="handleView(row)">查看</el-button>
              <el-button size="small" @click.stop="handleEdit(row)">编辑</el-button>
              <el-button size="small" type="danger" @click.stop="handleDelete(row)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
      </div>

      <div class="card-view">
        <div v-for="row in creationList" :key="row.id" class="history-item">
          <div class="history-top">
            <div class="title-cell">
              <el-icon :color="getToolColor(row.tool_type)"><component :is="getToolIcon(row.tool_type)" /></el-icon>
              <span>{{ row.title || '未命名内容' }}</span>
            </div>
            <el-tag :type="getToolTagType(row.tool_type)" size="small" effect="plain">{{ getToolName(row.tool_type) }}</el-tag>
          </div>
          <div class="history-preview">{{ getContentPreview(row.output_content || row.content) }}</div>
          <div class="history-meta">{{ formatDate(row.created_at) }}</div>
          <div class="history-actions">
            <el-button size="small" @click="handleView(row)">查看</el-button>
            <el-button size="small" @click="handleEdit(row)">编辑</el-button>
            <el-button size="small" type="danger" @click="handleDelete(row)">删除</el-button>
          </div>
        </div>
      </div>

      <div class="pagination-container">
        <el-pagination v-model:current-page="pagination.page" v-model:page-size="pagination.pageSize" :total="pagination.total" :page-sizes="[10,20,50,100]" layout="total, sizes, prev, pager, next, jumper" @size-change="handleSizeChange" @current-change="handlePageChange" />
      </div>
    </el-card>

    <el-dialog v-model="showDetailDialog" :title="currentCreation?.title || '创作详情'" width="min(960px, 96vw)" destroy-on-close>
      <div v-if="currentCreation" class="detail-content">
        <el-descriptions :column="2" border v-loading="loadingDetail">
          <el-descriptions-item label="工具类型">{{ getToolName(currentCreation.tool_type) }}</el-descriptions-item>
          <el-descriptions-item label="创建时间">{{ formatDate(currentCreation.created_at) }}</el-descriptions-item>
          <el-descriptions-item label="更新时间">{{ formatDate(currentCreation.updated_at) }}</el-descriptions-item>
          <el-descriptions-item label="字数/页数">{{ getWordCount(currentCreation) }}</el-descriptions-item>
        </el-descriptions>
        <el-divider />
        <div class="content-display" v-html="renderedContent"></div>
      </div>
      <template #footer>
        <el-button @click="showDetailDialog = false">关闭</el-button>
        <el-button type="primary" @click="handleCopyContent">复制内容</el-button>
        <el-button type="success" @click="handleEditFromDetail">继续编辑</el-button>
        <el-button type="warning" @click="showConverterDialog = true">
          <el-icon><Switch /></el-icon>
          转换平台
        </el-button>
      </template>
    </el-dialog>

    <!-- 多平台转换弹窗 -->
    <el-dialog v-model="showConverterDialog" title="多平台内容转换" width="min(800px, 96vw)" destroy-on-close>
      <PlatformConverter
        v-if="currentCreation"
        :creation-id="currentCreation.id"
        :original-title="currentCreation.title"
        :original-content="currentCreation.output_content || currentCreation.content"
        :original-platform="currentCreation.tool_type"
        @converted="handleConverted"
      />
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Document, Edit, Search, Switch } from '@element-plus/icons-vue'
import * as creationsApi from '@/api/creations'
import { getSavedPPT } from '@/api/ppt'
import { markdownToHtml } from '@/services/markdownRenderer'
import PlatformConverter from '@/components/converter/PlatformConverter.vue'
import dayjs from 'dayjs'

const router = useRouter()
const loading = ref(false)
const loadingDetail = ref(false)
const showDetailDialog = ref(false)
const showConverterDialog = ref(false)
const creationList = ref<any[]>([])
const currentCreation = ref<any>(null)

const renderedContent = computed(() => {
  const creation = currentCreation.value
  if (!creation) return ''
  const toolType = creation.tool_type || creation.creation_type || ''
  const text = creation.output_content || creation.content || ''

  if (isPptType(toolType)) {
    // PPT 大纲：output_content 是 JSON，解析成可读列表
    if (text && text.trim().startsWith('{')) {
      try {
        const outline = JSON.parse(text)
        const slides: any[] = outline.slides || []
        const slideHtml = slides.map((slide, index) => {
          const bullets = Array.isArray(slide.bullets)
            ? `<ul>${slide.bullets.map((b: string) => `<li>${escapeHtml(b)}</li>`).join('')}</ul>`
            : ''
          return `<div style="margin:8px 0"><b>${index + 1}. ${escapeHtml(slide.title || '')}</b>${bullets}</div>`
        }).join('')
        return `<h3>${escapeHtml(outline.title || '')}</h3>${outline.subtitle ? `<p>${escapeHtml(outline.subtitle)}</p>` : ''}${slideHtml}`
      } catch {
        return '<p>PPT 大纲数据格式异常</p>'
      }
    }
    // 已保存的 PPT 编辑器数据
    const slides = creation.output_data?.slides
    if (Array.isArray(slides) && slides.length > 0) {
      return `<p>已保存的 PPT（${slides.length} 页），点击「继续编辑」进入编辑器查看和修改。</p>`
    }
    return '<p>该 PPT 记录暂无内容数据</p>'
  }

  if (toolType === 'image') {
    const images = creation.output_data?.images
    if (Array.isArray(images) && images.length > 0) {
      return images.map((src: string) => `<img src="${src}" style="max-width:100%;border-radius:8px;margin:8px 0"/>`).join('')
    }
    return '<p>暂无图片</p>'
  }

  if (toolType === 'video') {
    const url = creation.output_data?.video_url
    return url ? `<video src="${url}" controls style="max-width:100%"></video>` : '<p>暂无视频</p>'
  }

  return markdownToHtml(text || '')
})

const escapeHtml = (value: string) => String(value ?? '')
  .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
  .replace(/"/g, '&quot;').replace(/'/g, '&#39;')

const filterForm = reactive({ toolType: '', dateRange: null as any, keyword: '' })
const pagination = reactive({ page: 1, pageSize: 20, total: 0 })

const toolNameMap: Record<string, string> = {
  wechat_article: '公众号', xiaohongshu_note: '小红书', official_document: '公文', marketing_copy: '营销', academic_paper: '论文', press_release: '新闻', video_script: '视频', story_novel: '故事', business_plan: '商业', work_report: '报告', resume: '简历', lesson_plan: '教案', content_rewrite: '改写', translation: '翻译',
  rewrite: '内容改写',
  image: '图片生成', video: '视频生成', ppt: 'PPT生成', ppt_editor: 'PPT生成', ppt_outline: 'PPT生成'
}
const toolIconMap: Record<string, any> = { wechat_article: Document, xiaohongshu_note: Edit, official_document: Document, marketing_copy: Edit, academic_paper: Document, press_release: Document, video_script: Edit, story_novel: Edit, business_plan: Document, work_report: Document, resume: Document, lesson_plan: Document, content_rewrite: Edit, rewrite: Edit, translation: Edit }
const toolColorMap: Record<string, string> = { wechat_article: '#07c160', xiaohongshu_note: '#ff2442', official_document: '#409eff', marketing_copy: '#f56c6c', academic_paper: '#909399', press_release: '#67c23a', video_script: '#e6a23c', story_novel: '#c71585', business_plan: '#1e90ff', work_report: '#409eff', resume: '#67c23a', lesson_plan: '#e6a23c', content_rewrite: '#909399', rewrite: '#909399', translation: '#409eff', image: '#7c3aed', video: '#0ea5e9', ppt: '#f97316' }
const fetchCreations = async () => {
  loading.value = true
  try {
    const params: any = { skip: (pagination.page - 1) * pagination.pageSize, limit: pagination.pageSize }
    if (filterForm.toolType) params.tool_type = filterForm.toolType
    if (filterForm.keyword) params.search = filterForm.keyword
    if (filterForm.dateRange && filterForm.dateRange.length === 2) {
      params.start_date = dayjs(filterForm.dateRange[0]).format('YYYY-MM-DD')
      params.end_date = dayjs(filterForm.dateRange[1]).format('YYYY-MM-DD')
    }
    const response = await creationsApi.getCreations(params)
    creationList.value = response.items || []
    pagination.total = response.total || 0
  } catch (error: any) {
    ElMessage.error(error.message || '获取创作列表失败')
  } finally {
    loading.value = false
  }
}

const handleSearch = () => { pagination.page = 1; fetchCreations() }
const handleReset = () => { filterForm.toolType = ''; filterForm.dateRange = null; filterForm.keyword = ''; pagination.page = 1; fetchCreations() }
const handlePageChange = (page: number) => { pagination.page = page; fetchCreations() }
const handleSizeChange = (size: number) => { pagination.pageSize = size; pagination.page = 1; fetchCreations() }
const handleRowClick = (row: any) => handleView(row)
const handleView = async (row: any) => {
  // 查看详情应拉取完整记录，而不是直接使用列表行数据
  loadingDetail.value = true
  try {
    const detail = await creationsApi.getCreation(row.id)
    currentCreation.value = detail
    showDetailDialog.value = true
  } catch (error: any) {
    ElMessage.error(error.message || '获取创作详情失败')
  } finally {
    loadingDetail.value = false
  }
}

const writingToolTypes = [
  'wechat_article', 'xiaohongshu_note', 'official_document', 'marketing_copy', 'academic_paper',
  'press_release', 'video_script', 'story_novel', 'business_plan', 'work_report', 'resume',
  'lesson_plan', 'content_rewrite', 'rewrite', 'translation',
]

const isPptType = (toolType: string) => ['ppt', 'ppt_editor', 'ppt_outline'].includes(toolType)

const handleEdit = async (row: any) => {
  const toolType = row.tool_type || row.creation_type || ''

  // 写作类：进入 AI 写作编辑页并回填该记录
  if (writingToolTypes.includes(toolType)) {
    router.push({ name: 'WritingEditor', params: { toolType }, query: { id: row.id } })
    return
  }

  // PPT：大纲记录回填 PPT 生成页；编辑器保存的记录进入 PPT 编辑器
  if (isPptType(toolType)) {
    if (row.tool_type === 'ppt_editor') {
      try {
        const res = await getSavedPPT(row.id)
        const data = res.data
        localStorage.setItem('pptist_slides', JSON.stringify(data.slides))
        if (data.template_id) localStorage.setItem('pptist_template_id', data.template_id)
        router.push('/ppt/editor')
      } catch (error: any) {
        ElMessage.error(error.response?.data?.detail || '加载已保存 PPT 失败')
      }
      return
    }
    router.push({ path: '/ppt', query: { outline_id: String(row.id) } })
    return
  }

  if (toolType === 'image') { router.push('/image'); return }
  if (toolType === 'video') { router.push('/video'); return }
  ElMessage.warning('暂不支持编辑该类型的记录')
}
const handleEditFromDetail = () => { if (currentCreation.value) { showDetailDialog.value = false; handleEdit(currentCreation.value) } }

const handleDelete = async (row: any) => {
  try {
    await ElMessageBox.confirm('确认删除这条创作记录吗？删除后无法恢复。', '确认删除', { confirmButtonText: '确认', cancelButtonText: '取消', type: 'warning' })
    await creationsApi.deleteCreation(row.id)
    ElMessage.success('删除成功')
    fetchCreations()
  } catch (error: any) {
    if (error !== 'cancel') ElMessage.error(error.message || '删除失败')
  }
}

const handleCopyContent = async () => {
  if (!currentCreation.value) return
  try {
    const text = (currentCreation.value.output_content || currentCreation.value.content || '').replace(/<[^>]+>/g, '')
    await navigator.clipboard.writeText(text)
    ElMessage.success('内容已复制到剪贴板')
  } catch {
    ElMessage.error('复制失败，请手动复制')
  }
}

const handleConverted = (results: any[]) => {
  ElMessage.success(`成功转换到 ${results.length} 个平台`)
  showConverterDialog.value = false
  fetchCreations() // 刷新列表以显示新创建的记录
}

const getToolName = (toolType: string) => toolNameMap[toolType] || toolType || '未知工具'
const getToolIcon = (toolType: string) => toolIconMap[toolType] || Document
const getToolColor = (toolType: string) => toolColorMap[toolType] || '#409eff'
const getToolTagType = (toolType: string): '' | 'success' | 'info' | 'warning' | 'danger' => {
  const map: Record<string, '' | 'success' | 'info' | 'warning' | 'danger'> = {
    wechat_article: 'success', xiaohongshu_note: 'danger', official_document: '', marketing_copy: 'warning', academic_paper: 'info', press_release: 'success', video_script: 'warning', story_novel: '', business_plan: '', work_report: '', resume: 'success', lesson_plan: 'warning', content_rewrite: 'info', translation: '',
    rewrite: 'info',
    image: '', video: 'info', ppt: 'warning'
  }
  return map[toolType] || ''
}
const getContentPreview = (content: string) => (content || '').replace(/[#*`\[\]()_~>-]/g, '').replace(/\s+/g, ' ').trim().slice(0, 120)
const getWordCount = (creation: any) => {
  const text = creation?.output_content || creation?.content || ''
  const toolType = creation?.tool_type || creation?.creation_type || ''
  if (isPptType(toolType)) {
    const slides = creation?.output_data?.slides
    if (Array.isArray(slides) && slides.length > 0) return `${slides.length} 页`
    // PPT 大纲：output_content 是 JSON，解析后按页数展示
    if (text) {
      try {
        const outline = JSON.parse(text)
        if (Array.isArray(outline.slides) && outline.slides.length > 0) return `${outline.slides.length} 页`
      } catch {
        return '-'
      }
    }
    return '-'
  }
  if (text) return `${text.replace(/[#*`\[\]()_~>-]/g, '').replace(/\s+/g, '').length} 字`
  if (toolType === 'image') return '图片'
  if (toolType === 'video') return '视频'
  return '0 字'
}
const formatDate = (value: string) => value ? dayjs(value).format('YYYY-MM-DD HH:mm') : '-'

onMounted(() => { fetchCreations() })
</script>

<style scoped lang="scss">
.creation-history{display:flex;flex-direction:column;gap:24px;padding:28px}.page-hero{padding:30px;border:1px solid rgba(148,163,184,.2);border-radius:30px;background:radial-gradient(circle at top right,rgba(125,211,252,.38),transparent 28%),linear-gradient(135deg,rgba(239,246,255,.94),rgba(255,255,255,.92));box-shadow:0 24px 60px rgba(15,23,42,.08)}.eyebrow{margin:0 0 10px;font-size:13px;font-weight:700;letter-spacing:.2em;text-transform:uppercase;color:#2563eb}.page-hero h1{margin:0;font-size:clamp(30px,4vw,42px);color:#12304a}.description{margin:14px 0 0;max-width:760px;font-size:15px;line-height:1.75;color:#60758e}.glass-card{border:1px solid rgba(148,163,184,.2);border-radius:26px;background:rgba(255,255,255,.9);box-shadow:0 20px 44px rgba(15,23,42,.07)}.panel-head{display:flex;justify-content:space-between;gap:16px}.panel-head h3{margin:0;font-size:20px;color:#12304a}.panel-head p{margin:8px 0 0;font-size:14px;color:#62748a}.filter-form :deep(.el-form-item){margin-bottom:12px}.field-150{width:150px}.field-220{width:220px}.field-240{width:240px}.title-cell{display:flex;align-items:center;gap:8px}.title-cell .el-icon{font-size:18px}.title-cell span{flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.content-preview,.history-preview{color:#60758e;line-height:1.7;display:-webkit-box;-webkit-box-orient:vertical;overflow:hidden;-webkit-line-clamp:2}.pagination-container{display:flex;justify-content:flex-end;margin-top:20px}.card-view{display:none}.history-item{padding:18px;border:1px solid rgba(148,163,184,.18);border-radius:20px;background:linear-gradient(180deg,rgba(248,250,252,.96),rgba(239,246,255,.82))}.history-top,.history-actions{display:flex;align-items:center;justify-content:space-between;gap:12px}.history-meta{margin-top:12px;font-size:13px;color:#66788a}.detail-content .content-display{margin-top:20px;padding:20px;background:linear-gradient(180deg,rgba(248,250,252,.96),rgba(239,246,255,.82));border-radius:18px;min-height:300px;max-height:520px;overflow:auto;line-height:1.8}.detail-content .content-display :deep(blockquote){margin:12px 0;padding:10px 16px;border-left:4px solid #3b82f6;background:rgba(239,246,255,.9)}.detail-content .content-display :deep(pre){padding:14px;border-radius:14px;background:#0f172a;color:#e2e8f0;overflow:auto}.detail-content .content-display :deep(img){max-width:100%;height:auto;border-radius:12px}@media (max-width:768px){.creation-history{padding:16px}.filter-form{display:block}.field-150,.field-220,.field-240{width:100%}.table-view{display:none}.card-view{display:flex;flex-direction:column;gap:14px}.pagination-container{justify-content:center}.history-top,.history-actions,.panel-head{flex-direction:column;align-items:flex-start}}
</style>
