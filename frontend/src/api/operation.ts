import request from './request'

// 活动相关接口
export interface Activity {
  id: number
  title: string
  description: string
  activity_type: string
  status: string
  reward_type: string
  reward_amount: number
  start_time: string
  end_time: string
  max_participants: number | null
  current_participants: number
  rules: any
  budget: number | null
  target_users: any
  created_at: string
}

export interface ActivityParticipation {
  id: number
  activity_id: number
  user_id: number
  reward_amount: number
  participated_at: string
}

// 优惠券相关接口
export interface Coupon {
  id: number
  code: string
  name: string
  description: string
  coupon_type: string
  discount_type: string
  discount_value: number
  min_amount: number
  max_discount: number | null
  total_quantity: number
  per_user_limit: number | null
  used_quantity: number
  valid_from: string
  valid_until: string
  is_active: boolean
  created_at: string
}

export interface UserCoupon {
  id: number
  user_id: number
  coupon_id: number
  coupon: Coupon
  status: string
  received_at: string
  used_at: string | null
  expired_at: string
}

// 推广相关接口
export interface ReferralRecord {
  id: number
  referrer_id: number
  referee_id: number
  referral_code: string | null
  reward_type: string | null
  reward_amount: number
  reward_credits: number | null
  status: string
  trigger_event: string | null
  trigger_amount: number | null
  settled_at: string | null
  created_at: string
}

export interface ReferralStatistics {
  total_referrals: number
  completed_referrals: number
  pending_referrals: number
  total_rewards: number
  pending_rewards: number
  total_reward_credits: number
  coupon_rewards: number
  referral_code: string
}

// 统计相关接口
export interface OperationStatistics {
  new_users: number
  active_users: number
  total_members: number
  total_creations: number
  total_revenue: number
  user_retention_rate: number
  referral_conversion_rate: number
  recharge_amount: number
  recharge_count: number
  membership_amount: number
  membership_count: number
  credit_consume: number
  generation_count: number
  activity_participants: number
  coupon_used: number
  referral_count: number
  referral_rewards: number
  revenue_trend_pct: number
  users_trend_pct: number
  members_trend_pct: number
  creations_trend_pct: number
  revenue_trend: { dates: string[]; amounts: number[] }
  users_trend: { dates: string[]; counts: number[] }
  user_trend: { dates: string[]; new_users: number[]; active_users: number[] }
  members_trend: { dates: string[]; counts: number[] }
  creations_trend: { dates: string[]; counts: number[] }
  revenue_details: Array<Record<string, any>>
  user_details: Array<Record<string, any>>
  creation_details: Array<Record<string, any>>
  creation_distribution: Array<{ name: string; value: number }>
  payment_distribution: Array<{ name: string; value: number }>
}

// 活动管理
export const getActivities = (params?: {
  skip?: number
  limit?: number
  status?: string
  activity_type?: string
}) => {
  return request.get<{ data: { items: Activity[]; total: number } }>('/v1/operation/activities', { params })
}

export const getActivity = (activityId: number) => {
  return request.get<Activity>(`/v1/operation/activities/${activityId}`)
}

export const createActivity = (data: {
  title: string
  description: string
  activity_type: string
  reward_type: string
  reward_amount: number
  start_time: string
  end_time: string
  max_participants?: number
  budget?: number
  target_users?: any
  rules?: any
}) => {
  return request.post<Activity>('/v1/operation/activities', data)
}

export const updateActivity = (activityId: number, data: Partial<Activity>) => {
  return request.put<Activity>(`/v1/operation/activities/${activityId}`, data)
}

export const deleteActivity = (activityId: number) => {
  return request.delete(`/v1/operation/activities/${activityId}`)
}

export const participateActivity = (activityId: number) => {
  return request.post<ActivityParticipation>(`/v1/operation/activities/${activityId}/participate`, { activity_id: activityId })
}

export const getActivityParticipations = (activityId: number, params?: {
  skip?: number
  limit?: number
}) => {
  return request.get<ActivityParticipation[]>(`/v1/operation/activities/${activityId}/participations`, { params })
}

// 优惠券管理
export const getCoupons = (params?: {
  skip?: number
  limit?: number
  coupon_type?: string
  is_active?: boolean
}) => {
  return request.get<{ data: { items: Coupon[]; total: number } }>('/v1/operation/coupons', { params })
}

export const getCoupon = (couponId: number) => {
  return request.get<Coupon>(`/v1/operation/coupons/${couponId}`)
}

export const createCoupon = (data: {
  code: string
  name: string
  description?: string
  coupon_type: string
  discount_type: string
  discount_value: number
  min_amount?: number
  max_discount?: number
  total_quantity?: number
  valid_from: string
  valid_until: string
}) => {
  return request.post<Coupon>('/v1/operation/coupons', data)
}

export const updateCoupon = (couponId: number, data: Partial<Coupon>) => {
  return request.put<Coupon>(`/v1/operation/coupons/${couponId}`, data)
}

export const deleteCoupon = (couponId: number) => {
  return request.delete(`/v1/operation/coupons/${couponId}`)
}

export const issueCoupon = (couponId: number, userIds: number[]) => {
  return request.post(`/v1/operation/coupons/${couponId}/issue`, { user_ids: userIds })
}

export const voidCoupon = (couponId: number) => {
  return request.post(`/v1/operation/coupons/${couponId}/void`)
}

export const receiveCoupon = (couponId: number) => {
  return request.post<UserCoupon>(`/v1/operation/coupons/${couponId}/receive`)
}

export const getUserCoupons = (params?: {
  skip?: number
  limit?: number
  status?: string
}) => {
  return request.get<UserCoupon[]>('/v1/operation/user/coupons', { params })
}

// 优惠券试算
export const calculateCouponDiscount = (data: {
  coupon_code: string
  original_amount: number
}) => {
  return request.post<{
    original_amount: number
    discount_amount: number
    final_amount: number
  }>('/v1/operation/coupons/calculate', data)
}

// 推广管理
export const getReferralCode = () => {
  return request.get<{ referral_code: string }>('/v1/operation/referral/code')
}

export const getReferralRecords = (params?: {
  skip?: number
  limit?: number
  status?: string
}) => {
  return request.get<ReferralRecord[]>('/v1/operation/referral/records', { params })
}

export const getReferralStatistics = () => {
  return request.get<ReferralStatistics>('/v1/operation/referral/statistics')
}

export const approveReferral = (recordId: number, rewardAmount?: number) => {
  return request.post(`/v1/operation/referral/${recordId}/approve`, rewardAmount != null ? { reward_amount: rewardAmount } : {})
}

export const approveReferralsBatch = (recordIds: number[], rewardAmount?: number) => {
  return request.post('/v1/operation/referral/approve-batch', {
    record_ids: recordIds,
    reward_amount: rewardAmount,
  })
}

export const getReferralRule = () => {
  return request.get<{ reward_type: string; credits_rate: number; register_credits: number; coupon_id: number | null; is_enabled: boolean }>('/v1/operation/referral/rule')
}

export const updateReferralRule = (data: {
  reward_type: string
  credits_rate?: number
  register_credits?: number
  coupon_id?: number | null
  is_enabled?: boolean
}) => {
  return request.put('/v1/operation/referral/rule', data)
}

// 数据统计
export const getOperationStatistics = (params?: {
  stat_type?: string
  start_date?: string
  end_date?: string
}) => {
  return request.get<{ data: OperationStatistics }>('/v1/operation/statistics', { params })
}

export const getDashboardStatistics = () => {
  return request.get<{ data: {
    total_users: number
    today_new_users: number
    total_creations: number
    today_creations: number
    total_members: number
    total_revenue: number
    today_revenue: number
    active_users: number
  } }>('/v1/operation/dashboard')
}
