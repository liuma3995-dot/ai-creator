<template>
  <div class="user-status-section">
    <el-row :gutter="20">
      <el-col :xs="24" :sm="12" :md="8">
        <el-card class="status-card credit-card">
          <div class="card-header">
            <el-icon class="card-icon"><Coin /></el-icon>
            <span class="card-title">我的积分</span>
          </div>
          <div v-if="userStore.isLoggedIn" class="card-content">
            <div class="main-value">{{ userStore.user?.credits || 0 }}</div>
            <el-button type="primary" size="small" @click="goToRecharge">立即充值</el-button>
          </div>
          <div v-else class="card-content">
            <div class="main-value">— —</div>
            <el-button type="primary" size="small" @click="goToLogin">立即登录</el-button>
          </div>
        </el-card>
      </el-col>
      <el-col :xs="24" :sm="12" :md="8">
        <el-card class="status-card member-card">
          <div class="card-header">
            <el-icon class="card-icon"><Trophy /></el-icon>
            <span class="card-title">会员状态</span>
          </div>
          <div v-if="userStore.isLoggedIn" class="card-content">
            <div class="member-status">
              <span v-if="userStore.user?.membership_type === 'free'" class="member-badge free">免费用户</span>
              <span v-else-if="userStore.user?.membership_type === 'basic'" class="member-badge basic">基础会员</span>
              <span v-else-if="userStore.user?.membership_type === 'pro'" class="member-badge pro">专业会员</span>
              <span v-else class="member-badge vip">VIP会员</span>
            </div>
            <el-button v-if="userStore.user?.membership_type === 'free'" type="warning" size="small" @click="goToMembership">
              开通会员
            </el-button>
            <div v-else class="expire-info">到期时间：{{ formatDate(userStore.user?.member_expires_at) }}</div>
          </div>
          <div v-else class="card-content">
            <div class="member-status">
              <span class="member-badge free">未登录</span>
            </div>
            <el-button type="warning" size="small" @click="goToLogin">登录查看</el-button>
          </div>
        </el-card>
      </el-col>
      <el-col :xs="24" :sm="24" :md="8">
        <el-card class="status-card activity-card">
          <div class="card-header">
            <el-icon class="card-icon"><Present /></el-icon>
            <span class="card-title">限时优惠</span>
          </div>
          <div v-if="!userStore.isLoggedIn" class="card-content">
            <div class="activity-text">新用户注册即送 1000 积分</div>
            <el-button type="danger" size="small" @click="goToRegister">立即注册</el-button>
          </div>
          <div v-else class="card-content">
            <div class="activity-text">充值积分最高赠送200元超值套餐</div>
            <el-button type="danger" size="small" @click="goToRecharge">立即参与</el-button>
          </div>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
import { onMounted } from 'vue'
import { Coin, Present, Trophy } from '@element-plus/icons-vue'
import { useRouter } from 'vue-router'
import { useUserStore } from '@/store/user'

const router = useRouter()
const userStore = useUserStore()

const goToRecharge = () => {
  router.push('/credit/recharge')
}

const goToMembership = () => {
  router.push('/credit/membership')
}

const goToRegister = () => {
  router.push('/register')
}

const goToLogin = () => {
  router.push('/login')
}

const formatDate = (date: string | undefined) => {
  if (!date) return '未知'
  return new Date(date).toLocaleDateString('zh-CN')
}

onMounted(() => {
  // 首页“我的积分”统一走 store 刷新入口，保证打开首页时显示最新积分
  if (userStore.isLoggedIn) {
    userStore.refreshCredits()
  }
})
</script>

<style scoped lang="scss">
.user-status-section {
  .status-card {
    height: 100%;
    border-radius: 22px;
    border: 1px solid rgba(37, 99, 235, 0.12);
    background: rgba(255, 255, 255, 0.82);
    box-shadow: 0 16px 34px rgba(15, 23, 42, 0.08);
    backdrop-filter: blur(14px);
    transition: all 0.25s ease;
    display: flex;
    flex-direction: column;

    &:hover {
      transform: translateY(-4px);
      box-shadow: 0 22px 40px rgba(37, 99, 235, 0.12);
    }

    // 让 el-card 自己变成 flex，el-card__body 才能撑满高度
    :deep(.el-card) {
      height: 100%;
      display: flex;
      flex-direction: column;
    }

    // el-card__body 撑满 el-card 高度，并自己也是 flex 列容器
    :deep(.el-card__body) {
      padding: 22px;
      flex: 1;
      display: flex;
      flex-direction: column;
      min-height: 0;       // 防止 flex 子项因内容溢出撑爆父容器
    }
  }

  .card-header {
    display: flex;
    align-items: center;
    gap: 10px;
    margin-bottom: 16px;
  }

  .card-icon {
    width: 38px;
    height: 38px;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    border-radius: 12px;
    background: linear-gradient(135deg, rgba(37, 99, 235, 0.14), rgba(56, 189, 248, 0.16));
    color: #2563eb;
    font-size: 18px;
  }

  .card-title {
    color: #64748b;
    font-size: 14px;
    font-weight: 600;
  }

  .card-content {
    display: flex;
    flex-direction: column;
    gap: 12px;
    flex: 1;                                /* 撑满 card-body 剩余高度 */
    min-height: 0;
  }

  // 把按钮推到 card-content 底部，三张卡片按钮垂直对齐
  .card-content :deep(.el-button) {
    margin-top: auto;
  }

  .main-value {
    font-size: 34px;
    font-weight: 700;
    color: #0f172a;
  }

  .member-badge {
    display: inline-flex;
    align-items: center;
    padding: 6px 12px;
    border-radius: 999px;
    font-size: 13px;
    font-weight: 700;

    &.free {
      background: rgba(148, 163, 184, 0.14);
      color: #475569;
    }

    &.basic,
    &.pro,
    &.vip {
      background: linear-gradient(135deg, #2563eb 0%, #0ea5e9 50%, #38bdf8 100%);
      color: #fff;
      box-shadow: 0 12px 22px rgba(37, 99, 235, 0.16);
    }
  }

  .expire-info {
    color: #64748b;
    font-size: 12px;
  }

  .activity-text {
    color: #0f172a;
    font-size: 14px;
    font-weight: 600;
  }

  // 三种按钮统一高度、字体、圆角（消除 type 间 padding 微差）
  :deep(.el-button--primary),
  :deep(.el-button--warning),
  :deep(.el-button--danger) {
    border: none;
    border-radius: 12px;
    height: 36px;
    line-height: 1;
    padding: 0 16px;
    font-size: 13px;
    font-weight: 600;
    display: flex;
    align-items: center;
    justify-content: center;
    width: 100%;
  }
}

@media (max-width: 768px) {
  .user-status-section :deep(.el-col) {
    margin-bottom: 12px;
  }
}
</style>
