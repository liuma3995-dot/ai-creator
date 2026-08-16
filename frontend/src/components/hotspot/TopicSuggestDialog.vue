<template>
  <el-dialog
    v-model="dialogVisible"
    title="AI 选题建议"
    width="640px"
    :close-on-click-modal="false"
  >
    <div class="suggest-dialog">
      <div class="hot-title">
        <el-icon><TrendCharts /></el-icon>
        <span>{{ hotTitle }}</span>
      </div>

      <div v-if="modelOptions.length" class="model-select-row">
        <span class="model-label">使用模型：</span>
        <el-select
          v-model="selectedModelId"
          size="small"
          style="width: 240px"
          @change="loadSuggestions"
        >
          <el-option
            v-for="m in modelOptions"
            :key="m.id"
            :label="modelLabel(m)"
            :value="m.id"
          />
        </el-select>
      </div>
      <div v-else class="model-empty-hint">
        暂无文本模型，请先到 <router-link to="/settings">个人设置</router-link> 中添加
      </div>

      <div v-if="loading" class="loading-state">
        <el-icon class="loading-icon"><Loading /></el-icon>
        <p>AI 正在分析热点，生成选题建议...</p>
      </div>

      <template v-else-if="suggestions">
        <div v-if="suggestions.is_fallback" class="fallback-hint">
          AI 分析失败，当前为模板建议，可重试或切换模型
        </div>
        <div v-else-if="suggestions.model" class="model-info">
          由 {{ suggestions.model.name }}（{{ suggestions.model.provider }}）生成
        </div>

        <div class="background-section">
          <h4>热点背景</h4>
          <p>{{ suggestions.background }}</p>
        </div>

        <div class="keywords-section">
          <h4>相关关键词</h4>
          <div class="keywords">
            <el-tag v-for="keyword in suggestions.keywords" :key="keyword" size="small">
              {{ keyword }}
            </el-tag>
          </div>
        </div>

        <div class="angles-section">
          <h4>创作角度建议</h4>
          <div class="angles-list">
            <div
              v-for="(angle, index) in suggestions.angles"
              :key="index"
              class="angle-card"
            >
              <div class="angle-header">
                <span class="angle-index">{{ index + 1 }}</span>
                <span class="angle-name">{{ angle.angle }}</span>
              </div>
              <div class="angle-title">
                <el-icon><Document /></el-icon>
                {{ angle.title_suggestion }}
              </div>
              <div class="angle-direction">
                {{ angle.content_direction }}
              </div>
              <div class="angle-meta">
                <div class="audience">
                  <span class="label">目标受众：</span>
                  {{ angle.target_audience }}
                </div>
              </div>
              <div class="tools-actions">
                <span class="label">选择工具开始写作：</span>
                <el-button
                  v-for="tool in angle.recommended_tools"
                  :key="tool"
                  size="small"
                  type="primary"
                  @click.stop="selectToolAndWrite(tool, angle)"
                >
                  {{ getToolName(tool) }}
                </el-button>
              </div>
            </div>
          </div>
        </div>
      </template>

      <div v-else class="error-state">
        <el-icon><WarningFilled /></el-icon>
        <p>{{ errorMessage || '获取选题建议失败，请重试' }}</p>
        <el-button type="primary" @click="loadSuggestions">重新获取</el-button>
      </div>
    </div>

    <template #footer>
      <el-button @click="dialogVisible = false">关闭</el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, watch, computed } from 'vue'
import { TrendCharts, Loading, Document, WarningFilled } from '@element-plus/icons-vue'
import { getTopicSuggestions } from '@/api/hotspot'
import { getAIModels } from '@/api/models'
import type { TopicSuggestResponse } from '@/api/hotspot'
import type { AIModel } from '@/types'

const props = defineProps<{
  visible: boolean
  hotTitle: string
  hotUrl?: string
}>()

const emit = defineEmits<{
  (e: 'update:visible', value: boolean): void
  (e: 'select', data: { toolType: string; title: string; direction: string; keywords?: string[]; additionalDescription?: string }): void
}>()

const dialogVisible = computed({
  get: () => props.visible,
  set: (value) => emit('update:visible', value),
})

const loading = ref(false)
const suggestions = ref<TopicSuggestResponse | null>(null)
const errorMessage = ref('')
const modelOptions = ref<AIModel[]>([])
const selectedModelId = ref<number | undefined>(undefined)

const modelLabel = (model: AIModel) => {
  if (model.model_name && model.model_name !== model.name) {
    return `${model.name} (${model.model_name})`
  }
  return model.name
}

// 加载可用的文本模型（默认选中默认模型或第一个）
const loadModels = async () => {
  try {
    const res = await getAIModels('text')
    modelOptions.value = (Array.isArray(res) ? res : (res as any).data || []).filter(
      (m: AIModel) => m.is_active !== false
    )
    const defaultModel = modelOptions.value.find((m) => m.is_default) || modelOptions.value[0]
    selectedModelId.value = defaultModel?.id
  } catch {
    modelOptions.value = []
  }
}

// 工具名称映射
const toolNameMap: Record<string, string> = {
  wechat_article: '公众号文章',
  xiaohongshu_note: '小红书笔记',
  video_script: '短视频脚本',
  news_article: '新闻稿',
  marketing_copy: '营销文案',
  official_document: '公文写作',
  academic_paper: '论文写作',
}

const getToolName = (toolType: string) => {
  return toolNameMap[toolType] || toolType
}

// 加载选题建议
const loadSuggestions = async () => {
  if (!props.hotTitle || !selectedModelId.value) return

  loading.value = true
  suggestions.value = null
  errorMessage.value = ''

  try {
    const res = await getTopicSuggestions({
      hot_title: props.hotTitle,
      url: props.hotUrl,
      model_id: selectedModelId.value,
    })
    suggestions.value = res
  } catch (error) {
    console.error('获取选题建议失败:', error)
    errorMessage.value = (error as any).response?.data?.message || '获取选题建议失败，请重试'
  } finally {
    loading.value = false
  }
}

// 选择工具并开始写作
const selectToolAndWrite = (toolType: string, angle: any) => {
  if (!suggestions.value) return

  // 构建补充说明，包含热点背景、创作方向和参考链接
  const baseDescription = `【热点背景】${suggestions.value.background}\n\n【创作方向】${angle.content_direction}`
  
  // 添加参考链接
  const urlText = props.hotUrl ? `\n\n参考链接：${props.hotUrl}` : ''
  const additionalDescription = baseDescription + urlText

  emit('select', {
    toolType,
    title: angle.title_suggestion,
    direction: angle.content_direction,
    keywords: suggestions.value.keywords,
    additionalDescription,
  })
  dialogVisible.value = false
}

// 监听弹窗打开
watch(
  () => props.visible,
  (visible) => {
    if (visible && props.hotTitle) {
      loadModels().then(() => {
        if (selectedModelId.value) {
          loadSuggestions()
        }
      })
    }
  }
)
</script>

<style scoped lang="scss">
.suggest-dialog {
  .hot-title {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 12px 16px;
    background: linear-gradient(135deg, #fef3c7, #fde68a);
    border-radius: 8px;
    margin-bottom: 20px;
    font-size: 15px;
    font-weight: 500;
    color: #92400e;

    .el-icon {
      color: #f59e0b;
    }
  }

  .model-select-row {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 16px;

    .model-label {
      font-size: 13px;
      color: #475569;
      white-space: nowrap;
    }
  }

  .model-empty-hint {
    margin-bottom: 16px;
    padding: 10px 12px;
    background: #fefce8;
    border: 1px solid #fde68a;
    border-radius: 8px;
    font-size: 13px;
    color: #92400e;

    a {
      color: #3b82f6;
    }
  }

  .model-info {
    margin-bottom: 16px;
    font-size: 12px;
    color: #64748b;
  }

  .fallback-hint {
    margin-bottom: 16px;
    padding: 10px 12px;
    background: #fff7ed;
    border: 1px solid #fdba74;
    border-radius: 8px;
    font-size: 13px;
    color: #c2410c;
  }

  .loading-state {
    text-align: center;
    padding: 40px 0;

    .loading-icon {
      font-size: 32px;
      color: #3b82f6;
      animation: spin 1s linear infinite;
    }

    p {
      margin-top: 12px;
      color: #64748b;
    }
  }

  .error-state {
    text-align: center;
    padding: 40px 0;

    .el-icon {
      font-size: 48px;
      color: #f59e0b;
    }

    p {
      margin: 12px 0 16px;
      color: #64748b;
    }
  }

  .background-section,
  .keywords-section,
  .angles-section {
    margin-bottom: 20px;

    h4 {
      font-size: 14px;
      font-weight: 600;
      color: #334155;
      margin-bottom: 8px;
    }
  }

  .background-section p {
    font-size: 14px;
    line-height: 1.6;
    color: #64748b;
    margin: 0;
  }

  .keywords {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
  }

  .angles-list {
    display: flex;
    flex-direction: column;
    gap: 12px;
  }

  .angle-card {
    padding: 16px;
    border: 2px solid #e2e8f0;
    border-radius: 12px;
    cursor: pointer;
    transition: all 0.2s;

    &:hover {
      border-color: #93c5fd;
      background: #f0f9ff;
    }

    &.selected {
      border-color: #3b82f6;
      background: #eff6ff;
    }

    .angle-header {
      display: flex;
      align-items: center;
      gap: 8px;
      margin-bottom: 8px;

      .angle-index {
        width: 24px;
        height: 24px;
        display: flex;
        align-items: center;
        justify-content: center;
        background: #3b82f6;
        color: white;
        border-radius: 6px;
        font-size: 12px;
        font-weight: 600;
      }

      .angle-name {
        font-size: 15px;
        font-weight: 600;
        color: #1e293b;
      }
    }

    .angle-title {
      display: flex;
      align-items: center;
      gap: 6px;
      font-size: 14px;
      color: #3b82f6;
      margin-bottom: 8px;

      .el-icon {
        flex-shrink: 0;
      }
    }

    .angle-direction {
      font-size: 13px;
      line-height: 1.5;
      color: #64748b;
      margin-bottom: 12px;
    }

    .angle-meta {
      display: flex;
      flex-direction: column;
      gap: 6px;
      font-size: 12px;

      .label {
        color: #94a3b8;
      }

      .tools {
        display: flex;
        align-items: center;
        gap: 6px;
        flex-wrap: wrap;
      }

      .audience {
        color: #64748b;
      }
    }
  }
}

@keyframes spin {
  from {
    transform: rotate(0deg);
  }
  to {
    transform: rotate(360deg);
  }
}
</style>
