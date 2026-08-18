"""
运营管理API路由
"""
from typing import Optional, Any, Dict

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.user import User


def _enrich_activity(activity: Any) -> Dict[str, Any]:
    """把 rules JSON 里的 reward_type/reward_amount 提取为顶层字段，方便前端按列渲染"""
    d = ActivityResponse.model_validate(activity).model_dump()
    rules = activity.rules or {}
    d['reward_type'] = rules.get('reward_type')
    d['reward_amount'] = int(rules.get('reward_amount') or rules.get('credits') or 0)
    return d
from app.schemas.common import success_response, PaginatedResponse
from app.schemas.operation import (
    ActivityCreate, ActivityUpdate, ActivityParticipate, ActivityResponse,
    ActivityParticipationResponse,
    CouponCreate, CouponUpdate, CouponReceive, CouponIssue, CouponUse, CouponResponse,
    UserCouponResponse,
    ReferralCodeGenerate, ReferralApprove, ReferralApproveBatch, StatisticsQuery,
    ReferralRecordResponse, ReferralRuleUpdate
)
from app.services.operation_service import OperationService
from app.utils.deps import get_current_user, get_admin_user

router = APIRouter(tags=["运营管理"])
admin_router = APIRouter(tags=["运营管理-管理端"])


# ==================== 活动管理 ====================

@admin_router.post("/activities")
async def create_activity(
    activity: ActivityCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user)
):
    """创建运营活动（管理员）"""

    service = OperationService(db)
    result = await service.create_activity(activity, current_user.id)
    return success_response(data=_enrich_activity(result))


@router.get("/activities")
async def get_activities(
    status: Optional[str] = None,
    activity_type: Optional[str] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取活动列表"""
    service = OperationService(db)
    activities, total = await service.get_activities(
        status=status,
        activity_type=activity_type,
        skip=skip,
        limit=limit
    )
    return success_response(data=PaginatedResponse(
        items=[_enrich_activity(a) for a in activities],
        total=total,
        page=skip // limit + 1 if limit > 0 else 1,
        page_size=limit,
        total_pages=(total + limit - 1) // limit if limit > 0 else 0
    ))


@router.get("/activities/{activity_id}")
async def get_activity(
    activity_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取活动详情"""
    service = OperationService(db)
    activity = await service.get_activity(activity_id)
    if not activity:
        raise HTTPException(status_code=404, detail="活动不存在")
    return success_response(data=_enrich_activity(activity))


@admin_router.put("/activities/{activity_id}")
async def update_activity(
    activity_id: int,
    activity: ActivityUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user)
):
    """更新活动（管理员）"""

    service = OperationService(db)
    result = await service.update_activity(activity_id, activity)
    if not result:
        raise HTTPException(status_code=404, detail="活动不存在")
    return success_response(data=_enrich_activity(result))


@admin_router.delete("/activities/{activity_id}")
async def delete_activity(
    activity_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user)
):
    """删除活动（管理员）"""
    
    service = OperationService(db)
    success = await service.delete_activity(activity_id)
    if not success:
        raise HTTPException(status_code=404, detail="活动不存在")
    return success_response(data={"message": "删除成功"})


@router.post("/activities/{activity_id}/participate")
async def participate_activity(
    activity_id: int,
    participate: ActivityParticipate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """参与活动"""
    service = OperationService(db)
    result = await service.participate_activity(activity_id, current_user.id, participate)
    return success_response(data=result)


@admin_router.get("/activities/{activity_id}/participations")
async def get_activity_participations(
    activity_id: int,
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user)
):
    """获取活动参与记录（管理员）"""
    
    service = OperationService(db)
    participations, total = await service.get_activity_participations(
        activity_id=activity_id,
        skip=skip,
        limit=limit
    )
    return success_response(data=PaginatedResponse(
        items=[ActivityParticipationResponse.model_validate(p).model_dump() for p in participations],
        total=total,
        page=skip // limit + 1 if limit > 0 else 1,
        page_size=limit,
        total_pages=(total + limit - 1) // limit if limit > 0 else 0
    ))


# ==================== 优惠券管理 ====================

@admin_router.post("/coupons")
async def create_coupon(
    coupon: CouponCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user)
):
    """创建优惠券（管理员）"""
    
    service = OperationService(db)
    result = await service.create_coupon(coupon)
    return success_response(data=result)


@router.get("/coupons")
async def get_coupons(
    coupon_type: Optional[str] = None,
    is_active: Optional[bool] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取优惠券列表"""
    service = OperationService(db)
    coupons, total = await service.get_coupons(
        coupon_type=coupon_type,
        is_active=is_active,
        skip=skip,
        limit=limit
    )
    return success_response(data=PaginatedResponse(
        items=[CouponResponse.model_validate(c) for c in coupons],
        total=total,
        page=skip // limit + 1 if limit > 0 else 1,
        page_size=limit,
        total_pages=(total + limit - 1) // limit if limit > 0 else 0
    ))


@router.get("/coupons/{coupon_id}")
async def get_coupon(
    coupon_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取优惠券详情"""
    service = OperationService(db)
    coupon = await service.get_coupon(coupon_id)
    if not coupon:
        raise HTTPException(status_code=404, detail="优惠券不存在")
    return success_response(data=coupon)


@admin_router.put("/coupons/{coupon_id}")
async def update_coupon(
    coupon_id: int,
    coupon: CouponUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user)
):
    """更新优惠券（管理员）"""
    
    service = OperationService(db)
    result = await service.update_coupon(coupon_id, coupon)
    if not result:
        raise HTTPException(status_code=404, detail="优惠券不存在")
    return success_response(data=result)


@admin_router.delete("/coupons/{coupon_id}")
async def delete_coupon(
    coupon_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user)
):
    """删除优惠券（管理员）"""
    
    service = OperationService(db)
    success = await service.delete_coupon(coupon_id)
    if not success:
        raise HTTPException(status_code=404, detail="优惠券不存在")
    return success_response(data={"message": "删除成功"})


@router.post("/coupons/{coupon_id}/receive")
async def receive_coupon(
    coupon_id: int,
    receive: Optional[CouponReceive] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """领取优惠券"""
    service = OperationService(db)
    result = await service.receive_coupon(coupon_id, current_user.id, receive)
    return success_response(data=result)


@admin_router.post("/coupons/{coupon_id}/issue")
async def issue_coupon(
    coupon_id: int,
    issue: CouponIssue,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user)
):
    """发放优惠券给指定用户（管理员，支持批量）"""
    service = OperationService(db)
    issued = await service.issue_coupon(coupon_id, issue.user_ids)
    return success_response(data={"issued": issued})


@admin_router.post("/coupons/{coupon_id}/void")
async def void_coupon(
    coupon_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user)
):
    """作废优惠券（管理员）：停用并作废所有未使用的用户券"""
    service = OperationService(db)
    result = await service.void_coupon(coupon_id)
    return success_response(data={"id": result.id, "is_active": result.is_active})


@router.get("/user/coupons")
async def get_user_coupons(
    status: Optional[str] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取用户优惠券列表"""
    service = OperationService(db)
    coupons, total = await service.get_user_coupons(
        user_id=current_user.id,
        status=status,
        skip=skip,
        limit=limit
    )
    return success_response(data=PaginatedResponse(
        items=[UserCouponResponse.model_validate(c).model_dump() for c in coupons],
        total=total,
        page=skip // limit + 1 if limit > 0 else 1,
        page_size=limit,
        total_pages=(total + limit - 1) // limit if limit > 0 else 0
    ))


@router.post("/coupons/use")
async def use_coupon(
    use: CouponUse,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """使用优惠券"""
    service = OperationService(db)
    result = await service.use_coupon(current_user.id, use)
    return success_response(data=result)


@router.post("/coupons/calculate")
async def calculate_coupon_discount(
    calculate: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """计算优惠券折扣"""
    coupon_code = calculate.get("coupon_code")
    original_amount = calculate.get("original_amount")
    if not coupon_code or original_amount is None:
        raise HTTPException(status_code=400, detail="缺少参数: coupon_code / original_amount")
    service = OperationService(db)
    result = await service.calculate_coupon_discount(
        user_id=current_user.id,
        coupon_code=coupon_code,
        original_amount=original_amount,
    )
    return success_response(data=result)


# ==================== 推荐奖励 ====================

@router.post("/referral/generate")
async def generate_referral_code(
    generate: ReferralCodeGenerate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """生成推荐码"""
    service = OperationService(db)
    result = await service.generate_referral_code(current_user.id, generate)
    return success_response(data=result)


@router.get("/referral/code")
async def get_referral_code(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取我的推荐码"""
    service = OperationService(db)
    code = await service.get_user_referral_code(current_user.id)
    if not code:
        raise HTTPException(status_code=404, detail="推荐码不存在")
    return success_response(data=code)


@router.get("/referral/records")
async def get_referral_records(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取推荐记录"""
    service = OperationService(db)
    referrer_id = None if current_user.role == "admin" else current_user.id
    records, total = await service.get_referral_records(
        referrer_id=referrer_id,
        skip=skip,
        limit=limit
    )
    return success_response(data=PaginatedResponse(
        items=[ReferralRecordResponse.model_validate(r).model_dump() for r in records],
        total=total,
        page=skip // limit + 1 if limit > 0 else 1,
        page_size=limit,
        total_pages=(total + limit - 1) // limit if limit > 0 else 0
    ))


@router.get("/referral/statistics")
async def get_referral_statistics(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取推广统计：管理员查看全平台，普通用户查看自己的"""
    service = OperationService(db)
    if current_user.role == "admin":
        statistics = await service.get_referral_statistics_admin()
    else:
        statistics = await service.get_referral_statistics(current_user.id)
    return success_response(data=statistics)


@admin_router.get("/referral/rule")
async def get_referral_rule(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user)
):
    """获取平台返利规则（管理员）"""
    service = OperationService(db)
    rule = await service.get_referral_rule()
    return success_response(data={
        "reward_type": rule.reward_type,
        "credits_rate": float(rule.credits_rate),
        "register_credits": rule.register_credits,
        "coupon_id": rule.coupon_id,
        "is_enabled": rule.is_enabled,
    })


@admin_router.put("/referral/rule")
async def update_referral_rule(
    rule_data: ReferralRuleUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user)
):
    """更新平台返利规则（管理员）"""
    service = OperationService(db)
    rule = await service.update_referral_rule(rule_data)
    return success_response(data={
        "reward_type": rule.reward_type,
        "credits_rate": float(rule.credits_rate),
        "register_credits": rule.register_credits,
        "coupon_id": rule.coupon_id,
        "is_enabled": rule.is_enabled,
    })


@admin_router.post("/referral/approve-batch")
async def approve_referrals_batch(
    approve: ReferralApproveBatch,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user)
):
    """批量审核通过推荐返利（管理员）"""

    service = OperationService(db)
    settled = await service.approve_referrals_batch(
        approve.record_ids, approve.reward_amount
    )
    return success_response(data={"settled": settled})


@admin_router.post("/referral/{record_id}/approve")
async def approve_referral(
    record_id: int,
    approve: Optional[ReferralApprove] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user)
):
    """审核通过一条推荐返利（管理员）"""

    service = OperationService(db)
    reward_amount = approve.reward_amount if approve else None
    result = await service.approve_referral(record_id, reward_amount)
    return success_response(data={
        "record_id": result.id,
        "status": result.status.value,
        "reward_amount": float(result.reward_amount or 0),
    })


# ==================== 运营统计 ====================

@admin_router.get("/statistics")
async def get_operation_statistics(
    query: StatisticsQuery = Depends(),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user)
):
    """获取运营统计（管理员）"""
    
    service = OperationService(db)
    statistics = await service.get_operation_statistics(query)
    return success_response(data=statistics)


@admin_router.get("/dashboard")
async def get_dashboard_statistics(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user)
):
    """获取仪表盘统计（管理员）"""

    service = OperationService(db)
    statistics = await service.get_dashboard_statistics()
    return success_response(data=statistics)
