<template>
  <div class="my-referral page-shell">
    <section class="page-hero">
      <div>
        <p class="eyebrow">Referral</p>
        <h1>我的推广</h1>
        <p class="description">分享推荐码给好友，好友注册并完成首次充值或购买会员，你将获得返利奖励。</p>
      </div>
    </section>

    <el-card class="code-card glass-card">
      <div class="code-row">
        <div>
          <div class="label">我的推荐码</div>
          <div class="code">{{ info.referral_code || '加载中...' }}</div>
          <div class="url">{{ info.referral_url }}</div>
        </div>
        <div class="code-actions">
          <el-button type="primary" @click="copyCode">复制推荐码</el-button>
          <el-button @click="copyLink">复制分享链接</el-button>
        </div>
      </div>
    </el-card>

    <section class="stats-row">
      <el-card class="stat-card">
        <div class="stat-value">{{ stats.total_referrals }}</div>
        <div class="stat-label">推荐人数</div>
      </el-card>
      <el-card class="stat-card">
        <div class="stat-value">{{ stats.completed_referrals }}</div>
        <div class="stat-label">已完成返利</div>
      </el-card>
      <el-card class="stat-card">
        <div class="stat-value">{{ stats.pending_referrals }}</div>
        <div class="stat-label">待结算</div>
      </el-card>
      <el-card class="stat-card">
        <div class="stat-value">{{ stats.total_reward_credits }}</div>
        <div class="stat-label">积分返利累计</div>
      </el-card>
      <el-card class="stat-card">
        <div class="stat-value">{{ stats.coupon_rewards }}</div>
        <div class="stat-label">优惠券返利</div>
      </el-card>
    </section>

    <el-card class="records-card glass-card">
      <template #header>
        <div class="card-header">
          <span>推广记录</span>
          <el-button text type="primary" @click="loadRecords">刷新</el-button>
        </div>
      </template>
      <el-table :data="records" v-loading="loading">
        <el-table-column prop="referee_id" label="被推荐用户" width="120" />
        <el-table-column label="触发事件" width="130">
          <template #default="{ row }">
            <el-tag size="small" effect="plain">{{ triggerLabel(row.trigger_event) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="返利内容">
          <template #default="{ row }">{{ rewardText(row) }}</template>
        </el-table-column>
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="statusTag(row.status)" size="small">{{ statusLabel(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="推广时间" width="180" />
        <el-table-column prop="settled_at" label="结算时间" width="180" />
      </el-table>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import {ref, onMounted} from 'vue'
import {ElMessage} from 'element-plus'
import {getReferralCode, getReferralRecords, getReferralStatistics} from '@/api/operation'
import {useUserStore} from '@/store/user'

const userStore = useUserStore()
const loading = ref(false)
const info = ref<{referral_code: string; referral_url: string}>({referral_code: '', referral_url: ''})
const stats = ref<any>({
  total_referrals: 0,
  completed_referrals: 0,
  pending_referrals: 0,
  total_rewards: 0,
  total_reward_credits: 0,
  coupon_rewards: 0,
})
const records = ref<any[]>([])

const triggerLabel = (t: string) => ({
  register: '注册',
  first_recharge: '首次充值',
  membership: '购买会员',
}[t] || t || '-')

const statusLabel = (s: string) => ({
  pending: '待结算',
  settled: '已结算',
  cancelled: '已取消',
}[s] || s)

const statusTag = (s: string) => ({
  pending: 'warning',
  settled: 'success',
  cancelled: 'danger',
}[s] || 'info') as any

const rewardText = (row: any) => {
  if (row.reward_type === 'coupon') {
    return `优惠券${row.reward_data?.coupon_code ? `（${row.reward_data.coupon_code}）` : ''}`
  }
  if (row.reward_type === 'register_credits') {
    return `${row.reward_credits ?? 0} 积分（邀请注册）`
  }
  if (row.reward_type === 'credits') {
    return `${row.reward_credits ?? 0} 积分`
  }
  return '-'
}

const loadCode = async () => {
  try {
    const res: any = await getReferralCode()
    info.value = res.data || res
  } catch (e) {
    // 无推荐码时提示生成
  }
}

const loadStats = async () => {
  try {
    const res: any = await getReferralStatistics()
    stats.value = res.data || {}
    // 返利到账可能发生在其他页面/标签页，进入本页时统一刷新积分状态
    await userStore.refreshCredits()
  } catch (e) {
    console.error('加载推广统计失败:', e)
  }
}

const loadRecords = async () => {
  loading.value = true
  try {
    const res: any = await getReferralRecords({skip: 0, limit: 50})
    records.value = res.data?.items || res.data || []
  } catch (e) {
    ElMessage.error('加载推广记录失败')
  } finally {
    loading.value = false
  }
}

const copyCode = async () => {
  if (!info.value.referral_code) return ElMessage.warning('推荐码尚未生成')
  try {
    await navigator.clipboard.writeText(info.value.referral_code)
    ElMessage.success('推荐码已复制')
  } catch {
    ElMessage.error('复制失败，请手动复制')
  }
}

const copyLink = async () => {
  if (!info.value.referral_url) return ElMessage.warning('分享链接尚未生成')
  try {
    await navigator.clipboard.writeText(info.value.referral_url)
    ElMessage.success('分享链接已复制')
  } catch {
    ElMessage.error('复制失败，请手动复制')
  }
}

onMounted(() => {
  loadCode()
  loadStats()
  loadRecords()
  // 从其他标签页注册返回本页时，自动刷新统计与记录
  window.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'visible') {
      loadStats()
      loadRecords()
      userStore.refreshCredits()
    }
  })
})
</script>

<style scoped lang="scss">
.my-referral {
  max-width: 960px;
  margin: 0 auto;
}

.page-hero {
  margin-bottom: 20px;

  h1 {
    margin: 0 0 6px;
  }

  .description {
    margin: 0;
    color: #909399;
    font-size: 14px;
  }
}

.code-card {
  margin-bottom: 20px;

  .code-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
  }

  .label {
    color: #909399;
    font-size: 13px;
  }

  .code {
    font-size: 28px;
    font-weight: 700;
    letter-spacing: 2px;
    margin: 6px 0;
  }

  .url {
    color: #c0c4cc;
    font-size: 12px;
  }
}

.stats-row {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  gap: 14px;
  margin-bottom: 20px;

  .stat-value {
    font-size: 24px;
    font-weight: 700;
  }

  .stat-label {
    color: #909399;
    font-size: 13px;
    margin-top: 4px;
  }
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
</style>
