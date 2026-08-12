"""
运营功能Schema
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any, Literal
from datetime import datetime
from decimal import Decimal


# ============ 活动相关 ============

class ActivityCreate(BaseModel):
    """创建活动"""
    title: str = Field(..., description="活动标题")
    activity_type: Literal["credit_gift", "coupon"] = Field(..., description="活动类型")
    description: Optional[str] = Field(None, description="活动描述")
    rules: Optional[Dict[str, Any]] = Field(None, description="活动规则（reward_type/reward_amount 存入此处）")
    start_time: datetime = Field(..., description="开始时间")
    end_time: datetime = Field(..., description="结束时间")
    target_users: Optional[Dict[str, Any]] = Field(None, description="目标用户条件")
    max_participants: Optional[int] = Field(None, description="最大参与人数")
    budget: Optional[Decimal] = Field(None, description="活动预算")
    # 兼容旧前端表单的顶层字段，自动合并到 rules
    reward_type: Optional[str] = Field(None, description="奖励类型（credits/coupon等）")
    reward_amount: Optional[int] = Field(None, description="奖励金额/积分")


class ActivityUpdate(BaseModel):
    """更新活动"""
    title: Optional[str] = None
    description: Optional[str] = None
    rules: Optional[Dict[str, Any]] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    status: Optional[str] = None
    target_users: Optional[Dict[str, Any]] = None
    max_participants: Optional[int] = None
    budget: Optional[Decimal] = None
    # 兼容旧前端表单的顶层字段，自动合并到 rules
    reward_type: Optional[str] = None
    reward_amount: Optional[int] = None


class ActivityResponse(BaseModel):
    """活动响应"""
    id: int
    title: str
    activity_type: str
    status: str
    description: Optional[str]
    rules: Optional[Dict[str, Any]]
    start_time: datetime
    end_time: datetime
    target_users: Optional[Dict[str, Any]]
    max_participants: Optional[int]
    current_participants: int
    budget: Optional[Decimal]
    cost: Decimal
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ActivityParticipate(BaseModel):
    """参与活动"""
    activity_id: int = Field(..., description="活动ID")


class ActivityParticipationResponse(BaseModel):
    """活动参与响应"""
    id: int
    activity_id: int
    user_id: int
    reward_type: Optional[str]
    reward_amount: Optional[int]
    reward_data: Optional[Dict[str, Any]]
    participated_at: datetime

    class Config:
        from_attributes = True


# ============ 优惠券相关 ============

class CouponCreate(BaseModel):
    """创建优惠券"""
    code: str = Field(..., description="优惠券码")
    name: str = Field(..., description="优惠券名称")
    coupon_type: Literal["recharge_discount", "recharge_bonus", "membership_discount", "general"] = Field(
        ..., description="优惠券类型（仅限合法 enum 值）"
    )
    discount_type: Literal["percent", "fixed"] = Field(..., description="折扣类型")
    discount_value: Decimal = Field(..., description="折扣值")
    min_amount: Optional[Decimal] = Field(None, description="最低消费金额")
    max_discount: Optional[Decimal] = Field(None, description="最大优惠金额")
    total_quantity: Optional[int] = Field(None, description="总发行量")
    per_user_limit: Optional[int] = Field(None, description="每人限领数量")
    valid_from: datetime = Field(..., description="有效期开始")
    valid_until: datetime = Field(..., description="有效期结束")
    description: Optional[str] = Field(None, description="使用说明")
    activity_id: Optional[int] = Field(None, description="关联活动ID")


class CouponUpdate(BaseModel):
    """更新优惠券"""
    name: Optional[str] = None
    discount_value: Optional[Decimal] = None
    min_amount: Optional[Decimal] = None
    max_discount: Optional[Decimal] = None
    total_quantity: Optional[int] = None
    per_user_limit: Optional[int] = None
    valid_from: Optional[datetime] = None
    valid_until: Optional[datetime] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None


class CouponResponse(BaseModel):
    """优惠券响应"""
    id: int
    code: str
    name: str
    coupon_type: str
    discount_type: str
    discount_value: Decimal
    min_amount: Optional[Decimal]
    max_discount: Optional[Decimal]
    total_quantity: Optional[int]
    per_user_limit: Optional[int]
    used_quantity: int
    valid_from: datetime
    valid_until: datetime
    description: Optional[str]
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class CouponReceive(BaseModel):
    """领取优惠券（按 URL 中的 coupon_id 定位，body 可选）"""
    coupon_code: Optional[str] = Field(None, description="优惠券码（可选，URL 已含）")


class CouponIssue(BaseModel):
    """发放优惠券给指定用户（管理员）"""
    user_ids: List[int] = Field(..., min_length=1, description="目标用户ID列表")


class CouponUse(BaseModel):
    """使用优惠券"""
    coupon_code: str = Field(..., description="优惠券码")
    order_type: str = Field(..., description="订单类型: recharge-充值, membership-会员")
    amount: Decimal = Field(..., description="订单金额")


class UserCouponResponse(BaseModel):
    """用户优惠券响应"""
    id: int
    coupon_id: int
    status: str
    used_at: Optional[datetime]
    received_at: datetime
    coupon: CouponResponse

    class Config:
        from_attributes = True


class CouponCalculateResponse(BaseModel):
    """优惠券计算响应"""
    original_amount: Decimal
    discount_amount: Decimal
    final_amount: Decimal
    coupon_info: Dict[str, Any]


# ============ 推广返利相关 ============

class ReferralCodeGenerate(BaseModel):
    """生成推荐码"""
    pass


class ReferralApprove(BaseModel):
    """审核通过推荐返利（管理员）"""
    reward_amount: Optional[Decimal] = Field(None, description="返利金额（默认 10 元）")


class ReferralApproveBatch(BaseModel):
    """批量审核通过推荐返利（管理员）"""
    record_ids: List[int] = Field(..., min_length=1, description="返利记录ID列表")
    reward_amount: Optional[Decimal] = Field(None, description="返利金额（默认 10 元）")


class ReferralCodeResponse(BaseModel):
    """推荐码响应"""
    referral_code: str
    referral_url: str


class ReferralRecordResponse(BaseModel):
    """推广记录响应"""
    id: int
    referrer_id: int
    referee_id: int
    referral_code: Optional[str]
    reward_type: Optional[str]
    reward_amount: Optional[Decimal]
    reward_credits: Optional[int]
    status: str
    trigger_event: Optional[str]
    trigger_amount: Optional[Decimal]
    coupon_id: Optional[int] = None
    reward_data: Optional[Dict[str, Any]] = None
    settled_at: Optional[datetime]
    created_at: datetime

    class Config:
        from_attributes = True


class ReferralRuleUpdate(BaseModel):
    """返利规则更新"""
    reward_type: Literal["credits", "register_credits", "coupon"] = "credits"
    credits_rate: Decimal = Field(Decimal("0.10"), ge=0, le=1, description="积分返利比例")
    register_credits: Optional[int] = Field(None, ge=1, description="邀请注册返利固定积分数量")
    coupon_id: Optional[int] = Field(None, description="优惠券返利发放的优惠券ID")
    is_enabled: bool = True


class ReferralStatisticsResponse(BaseModel):
    """推广统计响应"""
    total_referrals: int
    pending_referrals: int
    settled_referrals: int
    total_reward_amount: Decimal
    total_reward_credits: int
    referral_list: List[ReferralRecordResponse]


# ============ 统计相关 ============

class StatisticsQuery(BaseModel):
    """统计查询"""
    stat_type: str = Field("daily", description="统计类型: daily-日, weekly-周, monthly-月")
    start_date: Optional[datetime] = Field(None, description="开始日期")
    end_date: Optional[datetime] = Field(None, description="结束日期")


class OperationStatisticsResponse(BaseModel):
    """运营统计响应"""
    id: int
    stat_date: datetime
    stat_type: str
    new_users: int
    active_users: int
    paying_users: int
    recharge_amount: Decimal
    recharge_count: int
    membership_amount: Decimal
    membership_count: int
    credits_consumed: int
    credits_recharged: int
    credits_rewarded: int
    total_creations: int
    writing_count: int
    image_count: int
    video_count: int
    ppt_count: int
    referral_count: int
    referral_reward: Decimal
    activity_participants: int
    activity_cost: Decimal
    created_at: datetime

    class Config:
        from_attributes = True


class DashboardStatisticsResponse(BaseModel):
    """仪表盘统计响应"""
    # 今日数据
    today_new_users: int
    today_active_users: int
    today_recharge_amount: Decimal
    today_creations: int
    
    # 累计数据
    total_users: int
    total_members: int
    total_recharge_amount: Decimal
    total_creations: int
    
    # 趋势数据
    user_trend: List[Dict[str, Any]]
    revenue_trend: List[Dict[str, Any]]
    creation_trend: List[Dict[str, Any]]
    
    # 排行榜
    top_creators: List[Dict[str, Any]]
    top_referrers: List[Dict[str, Any]]
