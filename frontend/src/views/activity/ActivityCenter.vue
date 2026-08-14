<template>
  <div class="activity-center">
    <div class="page-header">
      <h2>活动中心</h2>
      <p>参与活动赢取积分奖励，先到先得</p>
    </div>

    <el-skeleton v-if="loading" :rows="4" animated />

    <el-empty v-else-if="!activities.length" description="当前没有可参与的活动" />

    <div v-else class="activity-list">
      <el-card v-for="item in activities" :key="item.id" class="activity-card">
        <div class="activity-head">
          <el-tag :type="typeTag(item.activity_type)" effect="plain">{{ typeLabel(item.activity_type) }}</el-tag>
          <el-tag :type="timeState(item) === 'not_started' ? 'info' : 'success'" size="small" effect="plain">
            {{ timeState(item) === 'not_started' ? '未开始' : '进行中' }}
          </el-tag>
          <span class="time">{{ formatTime(item.start_time) }} ~ {{ formatTime(item.end_time) }}</span>
        </div>
        <h3>{{ item.title }}</h3>
        <p class="desc">{{ item.description || '暂无描述' }}</p>
        <div class="meta-row">
          <span class="reward" v-if="rewardText(item)">奖励：{{ rewardText(item) }}</span>
          <span class="count" v-if="item.max_participants">
            已参与 {{ item.current_participants }} / {{ item.max_participants }}
          </span>
          <span class="count" v-else>已参与 {{ item.current_participants }} 人</span>
        </div>
        <el-button
          type="primary"
          :disabled="participated.has(item.id) || isFull(item) || timeState(item) === 'not_started'"
          :loading="participatingId === item.id"
          @click="handleParticipate(item)"
        >
          {{
            participated.has(item.id)
              ? '已参与'
              : (isFull(item) ? '已满员' : (timeState(item) === 'not_started' ? '未开始' : '立即参与'))
          }}
        </el-button>
      </el-card>
    </div>
  </div>
</template>

<script setup lang="ts">
import {ref, onMounted} from 'vue'
import {ElMessage} from 'element-plus'
import {getActivities, participateActivity, type Activity} from '@/api/operation'
import {useUserStore} from '@/store/user'

const userStore = useUserStore()
const loading = ref(true)
const activities = ref<Activity[]>([])
const participated = ref<Set<number>>(new Set())
const participatingId = ref<number | null>(null)

const typeLabel = (t: string) => ({
  credit_gift: '积分赠送',
  coupon: '优惠券活动',
}[t] || t)

const typeTag = (t: string) => ({
  credit_gift: 'success',
  coupon: 'primary',
}[t] || 'info') as any

const formatTime = (s?: string) => (s ? s.replace('T', ' ').slice(0, 16) : '-')

const rewardText = (a: Activity) => {
  const type = a.reward_type || (a.rules && (a.rules as any).reward_type)
  const amount = a.reward_amount ?? (a.rules && (a.rules as any).reward_amount)
  if (type === 'credits' || type === 'credit') return `${amount} 积分`
  if (type === 'coupon') return '优惠券'
  if (amount != null) return `${amount}`
  return ''
}

const isFull = (a: Activity) => !!a.max_participants && a.current_participants >= a.max_participants

const timeState = (a: Activity): 'not_started' | 'ongoing' => {
  const now = Date.now()
  const start = a.start_time ? new Date(a.start_time).getTime() : 0
  return now < start ? 'not_started' : 'ongoing'
}

const loadActivities = async () => {
  loading.value = true
  try {
    const res: any = await getActivities({status: 'active', skip: 0, limit: 50})
    const list: Activity[] = res.data?.items || res.data || []
    const now = Date.now()
    activities.value = list.filter((a) => {
      if (a.status !== 'active') return false
      const end = a.end_time ? new Date(a.end_time).getTime() : Infinity
      // 已发布且未结束的活动都展示：未开始的显示“未开始”并禁用参与，已结束隐藏
      return now <= end
    })
  } catch (e) {
    ElMessage.error('加载活动列表失败')
  } finally {
    loading.value = false
  }
}

const handleParticipate = async (a: Activity) => {
  participatingId.value = a.id
  try {
    await participateActivity(a.id)
    participated.value.add(a.id)
    const rw = rewardText(a)
    ElMessage.success(rw ? `参与成功，获得 ${rw}` : '参与成功')
    // 刷新积分状态，让顶部状态栏和首页积分卡片同步最新余额
    await userStore.refreshCredits()
    loadActivities()
  } catch (e: any) {
    const msg = e?.response?.data?.message || e?.message || ''
    if (msg.includes('已参与')) {
      participated.value.add(a.id)
    }
    // 具体错误已由请求拦截器提示
  } finally {
    participatingId.value = null
  }
}

onMounted(loadActivities)
</script>

<style scoped>
.activity-center {
  max-width: 960px;
  margin: 0 auto;
}

.page-header {
  margin-bottom: 20px;
}

.page-header h2 {
  margin: 0 0 6px;
}

.page-header p {
  margin: 0;
  color: #909399;
  font-size: 14px;
}

.activity-list {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.activity-card .activity-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 10px;
}

.activity-card .time {
  color: #909399;
  font-size: 13px;
}

.activity-card h3 {
  margin: 0 0 8px;
}

.activity-card .desc {
  color: #606266;
  font-size: 14px;
  margin: 0 0 12px;
}

.activity-card .meta-row {
  display: flex;
  gap: 16px;
  margin-bottom: 14px;
  font-size: 13px;
}

.activity-card .reward {
  color: #e6a23c;
}

.activity-card .count {
  color: #909399;
}
</style>
