import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { User } from '@/types'
import * as authApi from '@/api/auth'
import * as creditApi from '@/api/credit'

export const useUserStore = defineStore('user', () => {
  const token = ref<string>('')
  const refreshToken = ref<string>('')
  const adminToken = ref<string>('')
  const adminRefreshToken = ref<string>('')
  const userInfo = ref<User | null>(null)

  // 兼容性计算属性
  const user = computed(() => userInfo.value)
  const isLoggedIn = computed(() => {
    // 用户令牌或管理员令牌任一存在即视为已登录（T1）
    return !!token.value || !!localStorage.getItem('token') ||
        !!adminToken.value || !!localStorage.getItem('adminToken')
  })
  const isAdmin = computed(() => (userInfo.value?.role || '').toLowerCase() === 'admin')

  // 登录
  const login = async (username: string, password: string) => {
    const response = await authApi.login({ username, password }) as any
    // 响应格式: { code: 200, message: "success", data: { access_token, refresh_token, user, ... } }
    const data = response.data
    
    token.value = data.access_token
    refreshToken.value = data.refresh_token
    
    // 保存到本地存储
    localStorage.setItem('token', data.access_token)
    localStorage.setItem('refreshToken', data.refresh_token)
    
    // 登录响应中已经包含用户信息，直接使用
    if (data.user) {
      userInfo.value = data.user as User
      localStorage.setItem('userInfo', JSON.stringify(userInfo.value))
    }
  }

  // 注册
  const register = async (username: string, email: string, password: string) => {
    await authApi.register({ username, email, password, confirm_password: password })
  }

  // 获取用户信息
  const getUserInfo = async () => {
    const response = await authApi.getUserInfo() as any
    // 响应格式: { code: 200, message: "success", data: { user info } }
    userInfo.value = response.data as User
    localStorage.setItem('userInfo', JSON.stringify(userInfo.value))
  }

  // ===== 积分/会员状态统一刷新入口 =====
  // 所有会导致积分变化或需要展示最新积分的场景，统一调用本方法：
  // 充值支付、活动参与、推广返利到账、积分消费、页面切回首页/顶部导航等。
  const refreshCredits = async () => {
    // 仅持有 admin 令牌时，用户侧接口无令牌可用，跳过避免 401 弹窗（T1 严格分离）
    if (!token.value && !localStorage.getItem('token')) {
      return
    }
    try {
      const response = await creditApi.getCreditBalance() as any
      // 响应格式: { code: 200, message: "success", data: { credits, is_member, ... } }
      const data = response.data
      if (userInfo.value && data) {
        userInfo.value.credits = data.credits
        userInfo.value.is_member = data.is_member
        userInfo.value.member_expired_at = data.member_expired_at
        localStorage.setItem('userInfo', JSON.stringify(userInfo.value))
      }
    } catch (error) {
      console.error('更新积分信息失败:', error)
    }
  }

  // 管理员登录（独立 admin 令牌，T1 安全加固）
  const adminLogin = async (username: string, password: string) => {
    const response = await authApi.adminLogin({ username, password }) as any
    const data = response.data

    adminToken.value = data.access_token
    adminRefreshToken.value = data.refresh_token

    localStorage.setItem('adminToken', data.access_token)
    localStorage.setItem('adminRefreshToken', data.refresh_token)

    if (data.user) {
      userInfo.value = data.user as User
      localStorage.setItem('userInfo', JSON.stringify(userInfo.value))
    }

    // 同一账号同时登录用户端，拿到用户令牌：管理接口用 admin 令牌，
    // 用户侧接口（积分/会员/首页等）用用户令牌，避免 “Not authenticated”
    try {
      const userResp = await authApi.login({ username, password }) as any
      const userData = userResp.data
      token.value = userData.access_token
      refreshToken.value = userData.refresh_token
      localStorage.setItem('token', userData.access_token)
      localStorage.setItem('refreshToken', userData.refresh_token)
    } catch (e) {
      console.error('管理员同步获取用户令牌失败:', e)
    }
  }
  // 兼容旧调用方
  const updateCreditInfo = refreshCredits

  // 登出
  const logout = () => {
    token.value = ''
    refreshToken.value = ''
    adminToken.value = ''
    adminRefreshToken.value = ''
    userInfo.value = null
    localStorage.removeItem('token')
    localStorage.removeItem('refreshToken')
    localStorage.removeItem('adminToken')
    localStorage.removeItem('adminRefreshToken')
    localStorage.removeItem('userInfo')
  }

  // 从本地存储恢复用户信息
  const restoreUser = () => {
    const savedToken = localStorage.getItem('token')
    const savedRefreshToken = localStorage.getItem('refreshToken')
    const savedAdminToken = localStorage.getItem('adminToken')
    const savedAdminRefreshToken = localStorage.getItem('adminRefreshToken')
    const savedUserInfo = localStorage.getItem('userInfo')
    
    if (savedToken) {
      token.value = savedToken
      // 有 token 时以服务器为准刷新用户信息，避免本地旧角色/会员/积分状态偏差
      getUserInfo().catch(() => {
        logout()
      })
    }
    if (savedRefreshToken) {
      refreshToken.value = savedRefreshToken
    }
    if (savedAdminToken) {
      adminToken.value = savedAdminToken
    }
    if (savedAdminRefreshToken) {
      adminRefreshToken.value = savedAdminRefreshToken
    }
    if (savedUserInfo) {
      try {
        userInfo.value = JSON.parse(savedUserInfo)
      } catch (e) {
        console.error('解析用户信息失败:', e)
      }
    }
  }

  return {
    token,
    refreshToken,
    adminToken,
    adminRefreshToken,
    userInfo,
    user,
    isLoggedIn,
    isAdmin,
    login,
    adminLogin,
    register,
    getUserInfo,
    refreshCredits,
    updateCreditInfo,
    logout,
    restoreUser
  }
})
