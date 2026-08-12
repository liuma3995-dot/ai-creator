<template>
  <div class="referral-management">
    <el-card>
      <template #header>
        <span>推广管理（全平台）</span>
      </template>
      <el-descriptions :column="5" border>
        <el-descriptions-item label="总推荐人数">{{ statistics.total_referrals }}</el-descriptions-item>
        <el-descriptions-item label="已结算">{{ statistics.completed_referrals }}</el-descriptions-item>
        <el-descriptions-item label="待结算">{{ statistics.pending_referrals }}</el-descriptions-item>
        <el-descriptions-item label="累计发放积分">{{ statistics.total_reward_credits }}</el-descriptions-item>
        <el-descriptions-item label="优惠券发放">{{ statistics.coupon_rewards }}</el-descriptions-item>
      </el-descriptions>
    </el-card>

    <el-card style="margin-top: 20px">
      <template #header>
        <div class="card-header">
          <span>返利规则</span>
          <el-switch v-model="ruleForm.is_enabled" active-text="启用" />
        </div>
      </template>
      <el-form :inline="true">
        <el-form-item label="返利方式">
          <el-select v-model="ruleForm.reward_type" style="width: 160px">
            <el-option label="积分返利" value="credits" />
            <el-option label="邀请注册返利" value="register_credits" />
            <el-option label="优惠券返利" value="coupon" />
          </el-select>
        </el-form-item>
        <el-form-item v-if="ruleForm.reward_type === 'credits'" label="返利比例（订单金额）">
          <el-input-number v-model="ruleForm.credits_rate" :min="0" :max="1" :step="0.01" :precision="2" />
        </el-form-item>
        <el-form-item v-if="ruleForm.reward_type === 'register_credits'" label="邀请注册积分">
          <el-input-number v-model="ruleForm.register_credits" :min="1" :step="10" />
        </el-form-item>
        <el-form-item v-if="ruleForm.reward_type === 'coupon'" label="发放优惠券">
          <el-select v-model="ruleForm.coupon_id" placeholder="选择优惠券" style="width: 260px">
            <el-option v-for="c in couponOptions" :key="c.id" :label="`${c.name}（${c.code}）`" :value="c.id" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="saveRule">保存规则</el-button>
        </el-form-item>
      </el-form>
      <div class="rule-tip">
        被推荐人完成首次充值或购买会员后，按此规则自动发放返利；每条推荐仅结算一次。
      </div>
    </el-card>

    <el-card style="margin-top: 20px">
      <template #header>
        <div class="card-header">
          <span>推广记录</span>
          <div>
            <el-button type="success" :disabled="!selectedRows.length" @click="handleBatchApprove">
              批量审核（{{ selectedRows.length }}）
            </el-button>
          </div>
        </div>
      </template>

      <el-form :inline="true" :model="searchForm">
        <el-form-item label="返利状态">
          <el-select v-model="searchForm.status" placeholder="全部" clearable style="width: 140px">
            <el-option label="待结算" value="pending" />
            <el-option label="已结算" value="settled" />
            <el-option label="已取消" value="cancelled" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="loadRecords">查询</el-button>
        </el-form-item>
      </el-form>

      <el-table :data="records" style="width: 100%" @selection-change="(rows: any[]) => selectedRows = rows">
        <el-table-column type="selection" width="45" />
        <el-table-column prop="id" label="ID" width="70" />
        <el-table-column prop="referrer_id" label="推荐人ID" width="90" />
        <el-table-column prop="referee_id" label="被推荐用户ID" width="110" />
        <el-table-column label="触发事件" width="110">
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
        <el-table-column prop="created_at" label="推广时间" width="175" />
        <el-table-column prop="settled_at" label="结算时间" width="175" />
        <el-table-column label="操作" width="90" fixed="right">
          <template #default="{ row }">
            <el-button v-if="row.status === 'pending'" type="success" size="small" @click="handleApprove(row)">
              审核
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <el-pagination
        v-model:current-page="pagination.page"
        v-model:page-size="pagination.pageSize"
        :total="pagination.total"
        layout="total, prev, pager, next"
        @current-change="loadRecords"
      />
    </el-card>
  </div>
</template>

<script setup lang="ts">
import {ref, reactive, onMounted} from 'vue'
import {ElMessage} from 'element-plus'
import * as operationApi from '@/api/operation'

const statistics = ref<any>({
  total_referrals: 0,
  completed_referrals: 0,
  pending_referrals: 0,
  total_reward_credits: 0,
  coupon_rewards: 0,
})
const records = ref<operationApi.ReferralRecord[]>([])
const selectedRows = ref<any[]>([])
const couponOptions = ref<operationApi.Coupon[]>([])
const searchForm = reactive({status: ''})
const pagination = reactive({page: 1, pageSize: 10, total: 0})
const ruleForm = reactive<{reward_type: string; credits_rate: number; register_credits: number; coupon_id: number | null; is_enabled: boolean}>({
  reward_type: 'credits',
  credits_rate: 0.1,
  register_credits: 50,
  coupon_id: null,
  is_enabled: true,
})

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

const loadStatistics = async () => {
  try {
    const res: any = await operationApi.getReferralStatistics()
    statistics.value = res.data || {}
  } catch (e) {
    ElMessage.error('加载推广统计失败')
  }
}

const loadRecords = async () => {
  try {
    const res: any = await operationApi.getReferralRecords({
      skip: (pagination.page - 1) * pagination.pageSize,
      limit: pagination.pageSize,
      status: searchForm.status || undefined,
    })
    records.value = res.data?.items || []
    pagination.total = res.data?.total || 0
  } catch (e) {
    ElMessage.error('加载推广记录失败')
  }
}

const loadRule = async () => {
  try {
    const res: any = await operationApi.getReferralRule()
    const d = res.data || {}
    ruleForm.reward_type = d.reward_type || 'credits'
    ruleForm.credits_rate = Number(d.credits_rate ?? 0.1)
    ruleForm.register_credits = Number(d.register_credits ?? 50)
    ruleForm.coupon_id = d.coupon_id ?? null
    ruleForm.is_enabled = d.is_enabled !== false
  } catch (e) {
    console.error('加载返利规则失败:', e)
  }
}

const saveRule = async () => {
  try {
    await operationApi.updateReferralRule({
      reward_type: ruleForm.reward_type,
      credits_rate: ruleForm.reward_type === 'credits' ? ruleForm.credits_rate : undefined,
      register_credits: ruleForm.reward_type === 'register_credits' ? ruleForm.register_credits : undefined,
      coupon_id: ruleForm.reward_type === 'coupon' ? ruleForm.coupon_id : null,
      is_enabled: ruleForm.is_enabled,
    })
    ElMessage.success('返利规则已保存')
  } catch (e: any) {
    ElMessage.error(e.response?.data?.message || '保存规则失败')
  }
}

const loadCouponOptions = async () => {
  try {
    const res: any = await operationApi.getCoupons({skip: 0, limit: 100})
    const items: operationApi.Coupon[] = res.data?.items || res.data || []
    couponOptions.value = items.filter((c) => c.is_active !== false)
  } catch (e) {
    console.error('加载优惠券失败:', e)
  }
}

const handleApprove = async (row: any) => {
  try {
    await operationApi.approveReferral(row.id)
    ElMessage.success('已审核通过')
    loadRecords()
    loadStatistics()
  } catch (e: any) {
    ElMessage.error(e.response?.data?.message || '审核失败')
  }
}

const handleBatchApprove = async () => {
  if (!selectedRows.value.length) return
  try {
    const ids = selectedRows.value.filter((r) => r.status === 'pending').map((r) => r.id)
    if (!ids.length) return ElMessage.warning('没有可审核的记录')
    const res: any = await operationApi.approveReferralsBatch(ids)
    ElMessage.success(`已审核 ${res.data?.settled ?? ids.length} 条`)
    loadRecords()
    loadStatistics()
  } catch (e: any) {
    ElMessage.error(e.response?.data?.message || '批量审核失败')
  }
}

onMounted(() => {
  loadStatistics()
  loadRecords()
  loadRule()
  loadCouponOptions()
})
</script>

<style scoped>
.referral-management {
  padding: 20px;
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.rule-tip {
  color: #909399;
  font-size: 12px;
}

.el-pagination {
  margin-top: 20px;
  justify-content: center;
}
</style>
