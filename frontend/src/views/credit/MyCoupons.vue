<template>
  <div class="my-coupons page-shell">
    <section class="page-hero">
      <div>
        <p class="eyebrow">Coupons</p>
        <h1>我的优惠券</h1>
        <p class="description">参与活动领取的优惠券，可在积分充值与会员购买时抵扣。</p>
      </div>
    </section>

    <el-card class="coupon-card glass-card">
      <template #header>
        <div class="card-header">
          <span>优惠券列表</span>
          <el-radio-group v-model="statusFilter" size="small" @change="loadCoupons">
            <el-radio-button value="">全部</el-radio-button>
            <el-radio-button value="unused">未使用</el-radio-button>
            <el-radio-button value="used">已使用</el-radio-button>
            <el-radio-button value="expired">已过期</el-radio-button>
            <el-radio-button value="voided">已作废</el-radio-button>
          </el-radio-group>
        </div>
      </template>

      <el-skeleton v-if="loading" :rows="3" animated />
      <el-empty v-else-if="!coupons.length" description="暂无优惠券" />

      <div v-else class="coupon-list">
        <div v-for="uc in coupons" :key="uc.id" class="coupon-item" :class="{ disabled: uc.status !== 'unused' }">
          <div class="coupon-main">
            <div class="coupon-name">{{ uc.coupon.name }}</div>
            <div class="coupon-code">券码：{{ uc.coupon.code }}</div>
            <div class="coupon-meta">
              <el-tag size="small" effect="plain">{{ typeLabel(uc.coupon.coupon_type) }}</el-tag>
              <span class="discount">{{ discountText(uc.coupon) }}</span>
            </div>
            <div class="validity">
              有效期：{{ formatTime(uc.coupon.valid_from) }} ~ {{ formatTime(uc.coupon.valid_until) }}
            </div>
          </div>
          <div class="coupon-side">
            <el-tag :type="statusTag(uc.status)" size="small">{{ statusLabel(uc.status) }}</el-tag>
            <el-button
              v-if="uc.status === 'unused' && usable(uc)"
              type="primary"
              size="small"
              @click="goUse(uc)"
            >去使用</el-button>
          </div>
        </div>
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import {ref, onMounted} from 'vue'
import {useRouter} from 'vue-router'
import {ElMessage} from 'element-plus'
import {getUserCoupons, type UserCoupon} from '@/api/operation'

const router = useRouter()
const loading = ref(true)
const statusFilter = ref('')
const coupons = ref<UserCoupon[]>([])

const typeLabel = (t: string) => ({
  recharge_discount: '充值折扣',
  recharge_bonus: '充值赠送',
  membership_discount: '会员折扣',
  general: '通用',
}[t] || t)

const statusLabel = (s: string) => ({
  unused: '未使用',
  used: '已使用',
  expired: '已过期',
  voided: '已作废',
}[s] || s)

const statusTag = (s: string) => ({
  unused: 'success',
  used: 'info',
  expired: 'danger',
  voided: 'warning',
}[s] || 'info') as any

const discountText = (c: any) => {
  const value = Number(c.discount_value || 0)
  const base = c.discount_type === 'percent' ? `${value}% 优惠` : `减 ${value} 元`
  return c.min_amount ? `${base}（满 ${c.min_amount} 元可用）` : base
}

const formatTime = (s?: string) => (s ? s.replace('T', ' ').slice(0, 16) : '-')

const usable = (uc: UserCoupon) => {
  const now = Date.now()
  const from = uc.coupon.valid_from ? new Date(uc.coupon.valid_from).getTime() : 0
  const until = uc.coupon.valid_until ? new Date(uc.coupon.valid_until).getTime() : Infinity
  return uc.status === 'unused' && uc.coupon.is_active !== false && now >= from && now <= until
}

const goUse = (uc: UserCoupon) => {
  const code = uc.coupon.code
  if (uc.coupon.coupon_type === 'membership_discount') {
    router.push({path: '/credit/membership', query: {coupon: code}})
  } else {
    router.push({path: '/credit/recharge', query: {coupon: code}})
  }
}

const loadCoupons = async () => {
  loading.value = true
  try {
    const res: any = await getUserCoupons({status: statusFilter.value || undefined, skip: 0, limit: 100})
    coupons.value = res.data?.items || res.data || []
  } catch (e) {
    ElMessage.error('加载优惠券失败')
  } finally {
    loading.value = false
  }
}

onMounted(loadCoupons)
</script>

<style scoped lang="scss">
.my-coupons {
  max-width: 900px;
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

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.coupon-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.coupon-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 16px;
  border: 1px solid #e4e7ed;
  border-radius: 10px;

  &.disabled {
    opacity: 0.65;
  }
}

.coupon-name {
  font-size: 15px;
  font-weight: 600;
}

.coupon-code {
  margin-top: 4px;
  color: #909399;
  font-size: 12px;
}

.coupon-meta {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-top: 8px;
}

.discount {
  color: #e6a23c;
  font-size: 13px;
}

.validity {
  margin-top: 6px;
  color: #c0c4cc;
  font-size: 12px;
}

.coupon-side {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 8px;
}
</style>
