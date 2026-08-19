import request from './request'
import type { LoginForm, RegisterForm, TokenResponse, User } from '@/types'

// 用户登录
export function login(data: LoginForm) {
  return request.post<TokenResponse>('/v1/auth/login', data)
}

// 管理员登录（独立 admin 令牌，T1 安全加固）
export function adminLogin(data: LoginForm) {
  return request.post<TokenResponse>('/v1/auth/admin/login', data)
}

// 用户注册
export function register(data: RegisterForm) {
  return request.post('/v1/auth/register', data)
}

// 获取当前用户信息
export function getUserInfo() {
  return request.get<User>('/v1/auth/me')
}

// 刷新Token
export function refreshToken(refresh_token: string) {
  return request.post<TokenResponse>('/v1/auth/refresh', { refresh_token })
}

// 刷新管理员Token
export function adminRefreshToken(refresh_token: string) {
  return request.post<TokenResponse>('/v1/auth/admin/refresh', { refresh_token })
}

// 更新用户信息
export function updateUserInfo(data: Partial<User>) {
  return request.put<User>('/v1/auth/me', data)
}

// 修改密码
export function changePassword(data: { old_password: string; new_password: string }) {
  return request.post('/v1/auth/change-password', data)
}

// 请求密码重置
export function requestPasswordReset(data: { email: string }) {
  return request.post('/v1/auth/password-reset/request', data)
}

// 确认密码重置
export function confirmPasswordReset(data: { token: string; new_password: string }) {
  return request.post('/v1/auth/password-reset/confirm', data)
}
