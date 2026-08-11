"""
运营功能服务
"""
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from decimal import Decimal
import secrets
import string

from app.models.operation import (
    Activity, ActivityParticipation, Coupon, UserCoupon, ReferralRecord, OperationStatistics,
    ActivityType, ActivityStatus, CouponType, CouponStatus, ReferralStatus
)
from app.models.user import User
from app.models.credit import CreditTransaction, TransactionType, PaymentStatus, RechargeOrder
from app.schemas.operation import (
    ActivityCreate, ActivityUpdate, CouponCreate, CouponUpdate
)
from app.core.exceptions import BusinessException, NotFoundException


class ActivityService:
    """活动服务"""
    
    @staticmethod
    def _merge_reward_into_data(data: dict) -> dict:
        """把顶层 reward_type/reward_amount 合并进 rules JSON，再剔除顶层键"""
        if 'reward_type' not in data and 'reward_amount' not in data:
            return data
        rules = dict(data.get('rules') or {})
        if data.get('reward_type') is not None:
            rules['reward_type'] = data['reward_type']
        if data.get('reward_amount') is not None:
            rules['reward_amount'] = data['reward_amount']
        data['rules'] = rules
        data.pop('reward_type', None)
        data.pop('reward_amount', None)
        return data

    @staticmethod
    def create_activity(db: Session, activity_data: ActivityCreate, creator_id: int) -> Activity:
        """创建活动"""
        data = ActivityService._merge_reward_into_data(activity_data.model_dump())
        activity = Activity(
            **data,
            created_by=creator_id,
            status=ActivityStatus.DRAFT
        )
        db.add(activity)
        db.commit()
        db.refresh(activity)
        return activity

    @staticmethod
    def update_activity(db: Session, activity_id: int, activity_data: ActivityUpdate) -> Activity:
        """更新活动"""
        activity = db.query(Activity).filter(Activity.id == activity_id).first()
        if not activity:
            raise NotFoundException("活动不存在")

        update_data = activity_data.model_dump(exclude_unset=True)

        # 处理 reward_type/reward_amount —— 合并到现有 rules
        if 'reward_type' in update_data or 'reward_amount' in update_data:
            rules = dict(activity.rules or {})
            if 'reward_type' in update_data and update_data['reward_type'] is not None:
                rules['reward_type'] = update_data['reward_type']
            if 'reward_amount' in update_data and update_data['reward_amount'] is not None:
                rules['reward_amount'] = update_data['reward_amount']
            update_data['rules'] = rules
            update_data.pop('reward_type', None)
            update_data.pop('reward_amount', None)

        for key, value in update_data.items():
            setattr(activity, key, value)

        db.commit()
        db.refresh(activity)
        return activity
    
    @staticmethod
    def get_activity(db: Session, activity_id: int) -> Optional[Activity]:
        """获取活动详情"""
        return db.query(Activity).filter(Activity.id == activity_id).first()
    
    @staticmethod
    def list_activities(
        db: Session,
        status: Optional[str] = None,
        activity_type: Optional[str] = None,
        skip: int = 0,
        limit: int = 20
    ) -> tuple[List[Activity], int]:
        """获取活动列表"""
        query = db.query(Activity)
        
        if status:
            query = query.filter(Activity.status == status)
        if activity_type:
            query = query.filter(Activity.activity_type == activity_type)
        
        total = query.count()
        activities = query.order_by(Activity.created_at.desc()).offset(skip).limit(limit).all()
        
        return activities, total
    
    @staticmethod
    def participate_activity(db: Session, activity_id: int, user_id: int) -> ActivityParticipation:
        """参与活动"""
        # 检查活动是否存在且有效
        activity = db.query(Activity).filter(Activity.id == activity_id).first()
        if not activity:
            raise BusinessException("活动不存在")
        
        if activity.status != ActivityStatus.ACTIVE:
            raise BusinessException("活动未开始或已结束")
        
        now = datetime.now()
        if now < activity.start_time or now > activity.end_time:
            raise BusinessException("不在活动时间范围内")
        
        # 检查是否已参与
        existing = db.query(ActivityParticipation).filter(
            ActivityParticipation.activity_id == activity_id,
            ActivityParticipation.user_id == user_id
        ).first()
        if existing:
            raise BusinessException("已参与过该活动")
        
        # 检查参与人数限制
        if activity.max_participants:
            if activity.current_participants >= activity.max_participants:
                raise BusinessException("活动参与人数已满")
        
        # 根据活动类型发放奖励
        reward_type = None
        reward_amount = None
        reward_data = None
        
        if activity.activity_type == ActivityType.CREDIT_GIFT:
            # 积分赠送
            reward_type = "credits"
            # 兼容两种存储：rules.reward_amount（前端表单合并）与 rules.credits（旧格式）
            reward_amount = (
                activity.rules.get("reward_amount", activity.rules.get("credits", 0))
                if activity.rules else 0
            )
            
            # 增加用户积分
            user = db.query(User).filter(User.id == user_id).first()
            user.credits += reward_amount
            
            # 记录积分交易
            transaction = CreditTransaction(
                user_id=user_id,
                transaction_type=TransactionType.REWARD,
                amount=reward_amount,
                balance_before=user.credits - reward_amount,
                balance_after=user.credits,
                description=f"参与活动：{activity.title}",
                related_id=activity_id,
                related_type="activity"
            )
            db.add(transaction)
        
        # 创建参与记录
        participation = ActivityParticipation(
            activity_id=activity_id,
            user_id=user_id,
            reward_type=reward_type,
            reward_amount=reward_amount,
            reward_data=reward_data
        )
        db.add(participation)
        
        # 更新活动参与人数和成本
        activity.current_participants += 1
        if reward_amount:
            activity.cost += Decimal(str(reward_amount * 0.01))  # 假设1积分=0.01元
        
        db.commit()
        db.refresh(participation)
        
        return participation


class CouponService:
    """优惠券服务"""
    
    @staticmethod
    def create_coupon(db: Session, coupon_data: CouponCreate) -> Coupon:
        """创建优惠券"""
        # 检查优惠券码是否已存在
        existing = db.query(Coupon).filter(Coupon.code == coupon_data.code).first()
        if existing:
            raise BusinessException("优惠券码已存在")
        
        coupon = Coupon(**coupon_data.model_dump())
        db.add(coupon)
        db.commit()
        db.refresh(coupon)
        return coupon
    
    @staticmethod
    def update_coupon(db: Session, coupon_id: int, coupon_data: CouponUpdate) -> Coupon:
        """更新优惠券"""
        coupon = db.query(Coupon).filter(Coupon.id == coupon_id).first()
        if not coupon:
            raise NotFoundException("优惠券不存在")
        
        update_data = coupon_data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(coupon, key, value)
        
        db.commit()
        db.refresh(coupon)
        return coupon
    
    @staticmethod
    def get_coupon_by_code(db: Session, code: str) -> Optional[Coupon]:
        """根据优惠券码获取优惠券"""
        return db.query(Coupon).filter(Coupon.code == code).first()
    
    @staticmethod
    def list_coupons(
        db: Session,
        coupon_type: Optional[str] = None,
        is_active: Optional[bool] = None,
        skip: int = 0,
        limit: int = 20
    ) -> tuple[List[Coupon], int]:
        """获取优惠券列表"""
        query = db.query(Coupon)
        
        if coupon_type:
            query = query.filter(Coupon.coupon_type == coupon_type)
        if is_active is not None:
            query = query.filter(Coupon.is_active == is_active)
        
        total = query.count()
        coupons = query.order_by(Coupon.created_at.desc()).offset(skip).limit(limit).all()
        
        return coupons, total
    
    @staticmethod
    def receive_coupon(db: Session, coupon_id: int, user_id: int) -> UserCoupon:
        """领取优惠券"""
        coupon = db.query(Coupon).filter(Coupon.id == coupon_id).first()
        if not coupon:
            raise BusinessException("优惠券不存在")

        if not coupon.is_active:
            raise BusinessException("优惠券已失效")
        now = datetime.now()
        if now < coupon.valid_from or now > coupon.valid_until:
            raise BusinessException("不在领取有效期内")

        # 检查领取数量：配置了每人限领则按数量限制，否则每人限领 1 张
        existing_count = db.query(UserCoupon).filter(
            UserCoupon.coupon_id == coupon_id,
            UserCoupon.user_id == user_id
        ).count()
        if coupon.per_user_limit:
            if existing_count >= coupon.per_user_limit:
                raise BusinessException("已达每人限领数量")
        elif existing_count > 0:
            raise BusinessException("已领取过该优惠券")

        # 检查领取数量限制：按已创建的 UserCoupon 行数 vs total_quantity
        if coupon.total_quantity:
            claimed = db.query(UserCoupon).filter(UserCoupon.coupon_id == coupon_id).count()
            if claimed >= coupon.total_quantity:
                raise BusinessException("优惠券已被领完")

        # 创建用户优惠券
        user_coupon = UserCoupon(
            user_id=user_id,
            coupon_id=coupon_id,
            status=CouponStatus.UNUSED,
            received_at=datetime.now(),
        )
        db.add(user_coupon)

        db.commit()
        db.refresh(user_coupon)
        return user_coupon
    
    @staticmethod
    def use_coupon(db: Session, user_coupon_id: int, order_amount: Decimal) -> Dict[str, Any]:
        """标记用户的优惠券为已使用并返回折扣额（内部计算工具）"""
        user_coupon = db.query(UserCoupon).filter(UserCoupon.id == user_coupon_id).first()
        if not user_coupon:
            raise BusinessException("用户优惠券不存在")
        if user_coupon.status != CouponStatus.UNUSED:
            raise BusinessException("该优惠券已使用或已过期")

        coupon = user_coupon.coupon
        if not coupon.is_active:
            raise BusinessException("优惠券已失效")
        if datetime.now() > coupon.valid_until:
            user_coupon.status = CouponStatus.EXPIRED
            db.commit()
            raise BusinessException("优惠券已过期")
        if coupon.min_amount and Decimal(str(order_amount)) < coupon.min_amount:
            raise BusinessException(f"订单金额需满{coupon.min_amount}元")

        amount = Decimal(str(order_amount))
        if coupon.discount_type == 'percent':
            discount = amount * (coupon.discount_value / Decimal('100'))
            if coupon.max_discount:
                discount = min(discount, coupon.max_discount)
        elif coupon.discount_type == 'fixed':
            discount = min(coupon.discount_value, amount)
        else:
            discount = Decimal('0')

        user_coupon.status = CouponStatus.USED
        user_coupon.used_at = datetime.now()
        db.commit()

        return {
            "discount_amount": float(discount),
            "final_amount": float(amount - discount),
        }

    @staticmethod
    def calculate_order_discount(
        db: Session,
        coupon_code: str,
        order_amount: Decimal,
        order_type: str,
    ) -> Decimal:
        """校验优惠券并计算订单折扣（不写库）"""
        coupon = db.query(Coupon).filter(
            Coupon.code == coupon_code,
            Coupon.is_active == True,
        ).first()
        if not coupon:
            raise BusinessException("优惠券不存在或未启用")

        allowed_types = {
            "recharge": (
                CouponType.RECHARGE_DISCOUNT,
                CouponType.RECHARGE_BONUS,
                CouponType.GENERAL,
            ),
            "membership": (
                CouponType.MEMBERSHIP_DISCOUNT,
                CouponType.GENERAL,
            ),
        }
        if coupon.coupon_type not in allowed_types.get(order_type, ()):
            raise BusinessException("该优惠券类型不适用于此订单")

        now = datetime.now()
        if now < coupon.valid_from or now > coupon.valid_until:
            raise BusinessException("优惠券不在有效期内")

        amount = Decimal(str(order_amount))
        if coupon.min_amount and amount < coupon.min_amount:
            raise BusinessException(f"订单金额需满{coupon.min_amount}元")

        if coupon.discount_type == "percent":
            discount = amount * (coupon.discount_value / Decimal("100"))
            if coupon.max_discount:
                discount = min(discount, coupon.max_discount)
        elif coupon.discount_type == "fixed":
            discount = min(coupon.discount_value, amount)
        else:
            discount = Decimal("0")
        return discount

    @staticmethod
    def mark_order_coupon_used(
        db: Session,
        user_id: int,
        coupon_code: str,
        order_id: int,
    ) -> None:
        """订单创建后把优惠券标记为已使用并关联订单"""
        coupon = db.query(Coupon).filter(Coupon.code == coupon_code).first()
        if coupon:
            db.add(UserCoupon(
                user_id=user_id,
                coupon_id=coupon.id,
                status=CouponStatus.USED,
                used_at=datetime.now(),
                order_id=order_id,
            ))


class ReferralService:
    """推荐返利服务"""
    
    @staticmethod
    def generate_referral_code(db: Session, user_id: int) -> str:
        """生成推荐码"""
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise BusinessException("用户不存在")
        
        if user.referral_code:
            return user.referral_code
        
        # 生成唯一推荐码
        while True:
            code = ''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(8))
            existing = db.query(User).filter(User.referral_code == code).first()
            if not existing:
                break
        
        user.referral_code = code
        db.commit()
        
        return code
    
    @staticmethod
    def process_referral(db: Session, referee_id: int, referral_code: str) -> ReferralRecord:
        """处理推荐关系"""
        # 查找推荐人
        referrer = db.query(User).filter(User.referral_code == referral_code).first()
        if not referrer:
            raise BusinessException("推荐码无效")
        
        if referrer.id == referee_id:
            raise BusinessException("不能使用自己的推荐码")
        
        # 检查是否已被推荐
        existing = db.query(ReferralRecord).filter(ReferralRecord.referee_id == referee_id).first()
        if existing:
            raise BusinessException("已使用过推荐码")
        
        # 创建推荐记录
        record = ReferralRecord(
            referrer_id=referrer.id,
            referee_id=referee_id,
            status=ReferralStatus.PENDING
        )
        db.add(record)
        db.commit()
        db.refresh(record)
        
        return record
    
    @staticmethod
    def complete_referral(db: Session, record_id: int, reward_amount: Decimal) -> ReferralRecord:
        """完成推荐返利"""
        record = db.query(ReferralRecord).filter(ReferralRecord.id == record_id).first()
        if not record:
            raise BusinessException("推荐记录不存在")
        
        if record.status != ReferralStatus.PENDING:
            raise BusinessException("推荐记录状态异常")
        
        # 发放返利
        referrer = db.query(User).filter(User.id == record.referrer_id).first()
        referrer.credits += int(reward_amount * 100)  # 转换为积分
        
        # 记录积分交易
        transaction = CreditTransaction(
            user_id=record.referrer_id,
            transaction_type=TransactionType.REWARD,
            amount=int(reward_amount * 100),
            balance_before=referrer.credits - int(reward_amount * 100),
            balance_after=referrer.credits,
            description=f"推荐返利",
            related_id=record_id,
            related_type="referral"
        )
        db.add(transaction)
        
        # 更新推荐记录
        record.status = ReferralStatus.SETTLED
        record.reward_amount = reward_amount
        record.settled_at = datetime.now()
        
        db.commit()
        db.refresh(record)
        
        return record


class OperationService:
    """运营服务统一入口"""
    
    def __init__(self, db: Session):
        self.db = db
        self.activity_service = ActivityService()
        self.coupon_service = CouponService()
        self.referral_service = ReferralService()
    
    # Activity methods
    async def create_activity(self, activity_data: ActivityCreate, creator_id: int) -> Activity:
        return self.activity_service.create_activity(self.db, activity_data, creator_id)
    
    async def update_activity(self, activity_id: int, activity_data: ActivityUpdate) -> Activity:
        return self.activity_service.update_activity(self.db, activity_id, activity_data)
    
    async def get_activity(self, activity_id: int) -> Optional[Activity]:
        return self.activity_service.get_activity(self.db, activity_id)
    
    async def get_activities(self, status: Optional[str] = None, activity_type: Optional[str] = None, 
                            skip: int = 0, limit: int = 20) -> tuple[List[Activity], int]:
        return self.activity_service.list_activities(self.db, status, activity_type, skip, limit)
    
    async def delete_activity(self, activity_id: int) -> bool:
        activity = self.db.query(Activity).filter(Activity.id == activity_id).first()
        if activity:
            self.db.delete(activity)
            self.db.commit()
            return True
        return False
    
    async def participate_activity(self, activity_id: int, user_id: int, participate: Any) -> ActivityParticipation:
        return self.activity_service.participate_activity(self.db, activity_id, user_id)
    
    async def get_activity_participations(self, activity_id: int, skip: int = 0, limit: int = 20) -> tuple[List[ActivityParticipation], int]:
        query = self.db.query(ActivityParticipation).filter(ActivityParticipation.activity_id == activity_id)
        total = query.count()
        participations = query.offset(skip).limit(limit).all()
        return participations, total
    
    # Coupon methods
    async def create_coupon(self, coupon_data: CouponCreate) -> Coupon:
        return self.coupon_service.create_coupon(self.db, coupon_data)
    
    async def update_coupon(self, coupon_id: int, coupon_data: CouponUpdate) -> Coupon:
        return self.coupon_service.update_coupon(self.db, coupon_id, coupon_data)
    
    async def get_coupon(self, coupon_id: int) -> Optional[Coupon]:
        return self.db.query(Coupon).filter(Coupon.id == coupon_id).first()
    
    async def get_coupons(self, coupon_type: Optional[str] = None, is_active: Optional[bool] = None,
                         skip: int = 0, limit: int = 20) -> tuple[List[Coupon], int]:
        return self.coupon_service.list_coupons(self.db, coupon_type, is_active, skip, limit)
    
    async def delete_coupon(self, coupon_id: int) -> bool:
        coupon = self.db.query(Coupon).filter(Coupon.id == coupon_id).first()
        if coupon:
            self.db.delete(coupon)
            self.db.commit()
            return True
        return False

    async def issue_coupon(self, coupon_id: int, user_ids: List[int]) -> int:
        """管理员向指定用户发放优惠券（已领取过则跳过）"""
        coupon = self.db.query(Coupon).filter(Coupon.id == coupon_id).first()
        if not coupon:
            raise NotFoundException("优惠券不存在")

        issued = 0
        for uid in user_ids:
            existing = self.db.query(UserCoupon).filter(
                UserCoupon.coupon_id == coupon_id,
                UserCoupon.user_id == uid,
            ).first()
            if existing:
                continue
            self.db.add(UserCoupon(
                user_id=uid,
                coupon_id=coupon_id,
                status=CouponStatus.UNUSED,
                received_at=datetime.now(),
            ))
            issued += 1
        self.db.commit()
        return issued

    async def void_coupon(self, coupon_id: int) -> Coupon:
        """管理员作废优惠券：停用券本身，并把所有未使用的用户券置为已作废"""
        coupon = self.db.query(Coupon).filter(Coupon.id == coupon_id).first()
        if not coupon:
            raise NotFoundException("优惠券不存在")

        coupon.is_active = False
        self.db.query(UserCoupon).filter(
            UserCoupon.coupon_id == coupon_id,
            UserCoupon.status == CouponStatus.UNUSED,
        ).update({UserCoupon.status: CouponStatus.VOIDED})
        self.db.commit()
        self.db.refresh(coupon)
        return coupon
    
    async def receive_coupon(self, coupon_id: int, user_id: int, receive: Any) -> UserCoupon:
        return self.coupon_service.receive_coupon(self.db, coupon_id, user_id)
    
    async def get_user_coupons(self, user_id: int, status: Optional[str] = None,
                              skip: int = 0, limit: int = 20) -> tuple[List[UserCoupon], int]:
        query = self.db.query(UserCoupon).filter(UserCoupon.user_id == user_id)
        if status:
            query = query.filter(UserCoupon.status == status)
        total = query.count()
        coupons = query.offset(skip).limit(limit).all()
        return coupons, total
    
    async def calculate_coupon_discount(self, user_id: int, coupon_code: str, original_amount: Decimal) -> Dict[str, Any]:
        """按 code 试算折扣（不写入 DB）"""
        coupon = self.db.query(Coupon).filter(
            Coupon.code == coupon_code,
            Coupon.is_active == True,
        ).first()
        if not coupon:
            raise BusinessException("优惠券不存在或未启用")

        amount = Decimal(str(original_amount))
        if coupon.discount_type == 'percent':
            discount_amount = amount * (coupon.discount_value / Decimal('100'))
            if coupon.max_discount:
                discount_amount = min(discount_amount, coupon.max_discount)
        elif coupon.discount_type == 'fixed':
            discount_amount = min(coupon.discount_value, amount)
        else:
            discount_amount = Decimal('0')

        return {
            "coupon_code": coupon.code,
            "original_amount": float(amount),
            "discount_amount": float(discount_amount),
            "final_amount": float(amount - discount_amount),
        }

    async def use_coupon(self, user_id: int, use: Any) -> Dict[str, Any]:
        """使用优惠券（按 code 定位 + 写入 UserCoupon）"""
        code = use.coupon_code if hasattr(use, 'coupon_code') else use.get('coupon_code')
        amount = Decimal(str(use.amount if hasattr(use, 'amount') else use.get('amount')))
        order_type = use.order_type if hasattr(use, 'order_type') else use.get('order_type', 'recharge')

        coupon = self.db.query(Coupon).filter(
            Coupon.code == code,
            Coupon.is_active == True,
        ).first()
        if not coupon:
            raise BusinessException("优惠券不存在或未启用")
        if coupon.coupon_type not in (
            CouponType.RECHARGE_DISCOUNT,
            CouponType.RECHARGE_BONUS,
            CouponType.MEMBERSHIP_DISCOUNT,
        ):
            raise BusinessException("该优惠券类型暂不支持直接使用")

        user_coupon = UserCoupon(
            user_id=user_id,
            coupon_id=coupon.id,
            status=CouponStatus.USED,
            used_at=datetime.now(),
        )
        self.db.add(user_coupon)

        if coupon.discount_type == 'percent':
            discount_amount = amount * (coupon.discount_value / Decimal('100'))
            if coupon.max_discount:
                discount_amount = min(discount_amount, coupon.max_discount)
        elif coupon.discount_type == 'fixed':
            discount_amount = min(coupon.discount_value, amount)
        else:
            discount_amount = Decimal('0')

        final_amount = max(Decimal('0'), amount - discount_amount)
        self.db.commit()
        self.db.refresh(user_coupon)

        return {
            "original_amount": float(amount),
            "discount_amount": float(discount_amount),
            "final_amount": float(final_amount),
            "order_type": order_type,
            "coupon_code": code,
            "user_coupon_id": user_coupon.id,
        }
    
    # Referral methods
    async def generate_referral_code(self, user_id: int, generate: Any) -> Dict[str, str]:
        code = self.referral_service.generate_referral_code(self.db, user_id)
        return {"referral_code": code, "referral_url": f"https://your-domain.com/register?ref={code}"}
    
    async def get_referral_records(self, referrer_id: int, status: Optional[str] = None,
                                  skip: int = 0, limit: int = 20) -> tuple[List[ReferralRecord], int]:
        query = self.db.query(ReferralRecord).filter(ReferralRecord.referrer_id == referrer_id)
        if status:
            query = query.filter(ReferralRecord.status == status)
        total = query.count()
        records = query.offset(skip).limit(limit).all()
        return records, total
    
    async def get_referral_statistics(self, user_id: int) -> Dict[str, Any]:
        user = self.db.query(User).filter(User.id == user_id).first()
        referral_code = user.referral_code if user and user.referral_code else ""

        total_referrals = self.db.query(ReferralRecord).filter(ReferralRecord.referrer_id == user_id).count()
        completed_referrals = self.db.query(ReferralRecord).filter(
            ReferralRecord.referrer_id == user_id,
            ReferralRecord.status == ReferralStatus.SETTLED
        ).count()
        total_rewards = self.db.query(func.sum(ReferralRecord.reward_amount)).filter(
            ReferralRecord.referrer_id == user_id,
            ReferralRecord.status == ReferralStatus.SETTLED
        ).scalar() or Decimal('0')
        pending_amount = self.db.query(func.sum(ReferralRecord.reward_amount)).filter(
            ReferralRecord.referrer_id == user_id,
            ReferralRecord.status == ReferralStatus.PENDING
        ).scalar() or Decimal('0')

        return {
            "total_referrals": total_referrals,
            "completed_referrals": completed_referrals,
            "pending_referrals": total_referrals - completed_referrals,
            "total_rewards": float(total_rewards),
            "pending_rewards": float(pending_amount),
            "referral_code": referral_code,
        }

    async def get_user_referral_code(self, user_id: int) -> Optional[Dict[str, str]]:
        """获取用户的推荐码；若不存在则自动生成"""
        user = self.db.query(User).filter(User.id == user_id).first()
        if not user:
            return None

        if not user.referral_code:
            code = self.referral_service.generate_referral_code(self.db, user_id)
        else:
            code = user.referral_code

        return {
            "referral_code": code,
            "referral_url": f"http://localhost:5173/register?ref={code}",
        }

    async def approve_referral(
        self,
        record_id: int,
        reward_amount: Optional[Decimal] = None,
    ) -> ReferralRecord:
        """管理员审核通过一条返利记录"""
        amount = reward_amount if reward_amount is not None else Decimal("10")
        return self.referral_service.complete_referral(self.db, record_id, amount)

    async def approve_referrals_batch(
        self,
        record_ids: List[int],
        reward_amount: Optional[Decimal] = None,
    ) -> int:
        """管理员批量审核返利（跳过非待发放记录）"""
        amount = reward_amount if reward_amount is not None else Decimal("10")
        settled = 0
        for rid in record_ids:
            try:
                self.referral_service.complete_referral(self.db, rid, amount)
                settled += 1
            except BusinessException:
                continue
        return settled
    
    # Statistics methods
    async def get_statistics(self, start_date: Optional[datetime] = None, 
                           end_date: Optional[datetime] = None) -> Dict[str, Any]:
        """获取运营统计数据"""
        from app.models.creation import Creation
        from app.models.credit import RechargeOrder, MembershipOrder
        
        # 设置默认时间范围（最近30天）
        if not end_date:
            end_date = datetime.now()
        if not start_date:
            start_date = end_date - timedelta(days=30)
        
        # 用户统计
        new_users = self.db.query(User).filter(
            User.created_at >= start_date,
            User.created_at <= end_date
        ).count()
        
        active_users = self.db.query(func.count(func.distinct(Creation.user_id))).filter(
            Creation.created_at >= start_date,
            Creation.created_at <= end_date
        ).scalar() or 0
        
        # 充值统计
        recharge_stats = self.db.query(
            func.count(RechargeOrder.id).label('count'),
            func.sum(RechargeOrder.amount).label('amount')
        ).filter(
            RechargeOrder.created_at >= start_date,
            RechargeOrder.created_at <= end_date,
            RechargeOrder.payment_status == PaymentStatus.PAID
        ).first()
        
        # 会员统计
        membership_stats = self.db.query(
            func.count(MembershipOrder.id).label('count'),
            func.sum(MembershipOrder.amount).label('amount')
        ).filter(
            MembershipOrder.created_at >= start_date,
            MembershipOrder.created_at <= end_date,
            MembershipOrder.payment_status == PaymentStatus.PAID
        ).first()
        
        # 积分消耗统计
        credit_consume = self.db.query(func.sum(CreditTransaction.amount)).filter(
            CreditTransaction.created_at >= start_date,
            CreditTransaction.created_at <= end_date,
            CreditTransaction.transaction_type == TransactionType.CONSUME
        ).scalar() or 0
        
        # 创作统计
        generation_count = self.db.query(Creation).filter(
            Creation.created_at >= start_date,
            Creation.created_at <= end_date
        ).count()
        
        # 活动统计
        activity_participants = self.db.query(ActivityParticipation).filter(
            ActivityParticipation.participated_at >= start_date,
            ActivityParticipation.participated_at <= end_date
        ).count()
        
        # 优惠券统计
        coupon_used = self.db.query(UserCoupon).filter(
            UserCoupon.used_at >= start_date,
            UserCoupon.used_at <= end_date,
            UserCoupon.status == CouponStatus.USED
        ).count()
        
        # 推荐统计
        referral_count = self.db.query(ReferralRecord).filter(
            ReferralRecord.created_at >= start_date,
            ReferralRecord.created_at <= end_date
        ).count()
        
        referral_rewards = self.db.query(func.sum(ReferralRecord.reward_amount)).filter(
            ReferralRecord.created_at >= start_date,
            ReferralRecord.created_at <= end_date,
            ReferralRecord.status == ReferralStatus.SETTLED
        ).scalar() or Decimal('0')

        # ===== 日期维度趋势（供前端图表与明细） =====
        from app.models.creation import Creation
        from sqlalchemy import func as sa_func

        def _day_key(v):
            return v.strftime('%Y-%m-%d') if hasattr(v, 'strftime') else str(v)

        recharge_by_day = dict(
            (_day_key(r.d), float(r.amt or 0))
            for r in self.db.query(
                sa_func.date(RechargeOrder.created_at).label('d'),
                sa_func.coalesce(sa_func.sum(RechargeOrder.amount), 0).label('amt'),
            ).filter(
                RechargeOrder.created_at >= start_date,
                RechargeOrder.created_at <= end_date,
                RechargeOrder.payment_status == PaymentStatus.PAID,
            ).group_by(sa_func.date(RechargeOrder.created_at)).all()
        )
        membership_by_day = dict(
            (_day_key(m.d), float(m.amt or 0))
            for m in self.db.query(
                sa_func.date(MembershipOrder.created_at).label('d'),
                sa_func.coalesce(sa_func.sum(MembershipOrder.amount), 0).label('amt'),
            ).filter(
                MembershipOrder.created_at >= start_date,
                MembershipOrder.created_at <= end_date,
                MembershipOrder.payment_status == PaymentStatus.PAID,
            ).group_by(sa_func.date(MembershipOrder.created_at)).all()
        )
        users_by_day = dict(
            (_day_key(u.d), u.c)
            for u in self.db.query(
                sa_func.date(User.created_at).label('d'),
                sa_func.count(User.id).label('c'),
            ).filter(
                User.created_at >= start_date,
                User.created_at <= end_date,
            ).group_by(sa_func.date(User.created_at)).all()
        )
        creations_by_day = dict(
            (_day_key(cr.d), cr.c)
            for cr in self.db.query(
                sa_func.date(Creation.created_at).label('d'),
                sa_func.count(Creation.id).label('c'),
            ).filter(
                Creation.created_at >= start_date,
                Creation.created_at <= end_date,
            ).group_by(sa_func.date(Creation.created_at)).all()
        )
        active_users_by_day = dict(
            (_day_key(d), c)
            for d, c in self.db.query(
                sa_func.date(Creation.created_at).label('d'),
                sa_func.count(sa_func.distinct(Creation.user_id)).label('c'),
            ).filter(
                Creation.created_at >= start_date,
                Creation.created_at <= end_date,
            ).group_by(sa_func.date(Creation.created_at)).all()
        )
        memberships_count_by_day = dict(
            (_day_key(m.d), m.c)
            for m in self.db.query(
                sa_func.date(MembershipOrder.created_at).label('d'),
                sa_func.count(MembershipOrder.id).label('c'),
            ).filter(
                MembershipOrder.created_at >= start_date,
                MembershipOrder.created_at <= end_date,
                MembershipOrder.payment_status == PaymentStatus.PAID,
            ).group_by(sa_func.date(MembershipOrder.created_at)).all()
        )

        # 按日期补齐连续序列（含两端）
        dates = []
        current = start_date.date() if hasattr(start_date, 'date') else start_date
        end = end_date.date() if hasattr(end_date, 'date') else end_date
        while current <= end:
            dates.append(current)
            current += timedelta(days=1)
        date_strs = [d.strftime('%Y-%m-%d') for d in dates]

        revenue_trend = {
            "dates": date_strs,
            "amounts": [
                round(recharge_by_day.get(d, 0) + membership_by_day.get(d, 0), 2)
                for d in date_strs
            ],
        }
        users_trend = {
            "dates": date_strs,
            "counts": [users_by_day.get(d, 0) for d in date_strs],
        }
        members_trend = {
            "dates": date_strs,
            "counts": [memberships_count_by_day.get(d, 0) for d in date_strs],
        }
        creations_trend = {
            "dates": date_strs,
            "counts": [creations_by_day.get(d, 0) for d in date_strs],
        }
        revenue_details = [
            {
                "date": d,
                "recharge_amount": recharge_by_day.get(d, 0),
                "membership_amount": membership_by_day.get(d, 0),
            }
            for d in date_strs
        ]
        user_details = [
            {
                "date": d,
                "new_users": users_by_day.get(d, 0),
                "active_users": active_users_by_day.get(d, 0),
            }
            for d in date_strs
        ]
        creation_details = [
            {"date": d, "count": creations_by_day.get(d, 0)}
            for d in date_strs
        ]
        creation_distribution = [
            {
                "name": getattr(t, "value", str(t)),
                "value": c,
            }
            for t, c in self.db.query(
                Creation.creation_type,
                sa_func.count(Creation.id),
            ).filter(
                Creation.created_at >= start_date,
                Creation.created_at <= end_date,
            ).group_by(Creation.creation_type).all()
        ]
        payment_distribution = [
            {
                "name": str(p or "unknown"),
                "value": c,
            }
            for p, c in self.db.query(
                RechargeOrder.payment_method,
                sa_func.count(RechargeOrder.id),
            ).filter(
                RechargeOrder.created_at >= start_date,
                RechargeOrder.created_at <= end_date,
                RechargeOrder.payment_status == PaymentStatus.PAID,
            ).group_by(RechargeOrder.payment_method).all()
        ]

        # 留存率与转化率（口径：窗口内活跃/新增、已结算/总推荐）
        total_revenue = float(recharge_stats.amount or 0) + float(membership_stats.amount or 0)
        total_members = self.db.query(User).filter(User.is_member == True).count()
        settled_referrals = self.db.query(ReferralRecord).filter(
            ReferralRecord.created_at >= start_date,
            ReferralRecord.created_at <= end_date,
            ReferralRecord.status == ReferralStatus.SETTLED,
        ).count()
        user_retention_rate = round(active_users / new_users * 100, 1) if new_users else 0
        referral_conversion_rate = round(settled_referrals / referral_count * 100, 1) if referral_count else 0
        
        return {
            "new_users": new_users,
            "active_users": active_users,
            "total_members": total_members,
            "total_creations": generation_count,
            "total_revenue": total_revenue,
            "user_retention_rate": user_retention_rate,
            "referral_conversion_rate": referral_conversion_rate,
            "recharge_amount": float(recharge_stats.amount or 0),
            "recharge_count": recharge_stats.count or 0,
            "membership_amount": float(membership_stats.amount or 0),
            "membership_count": membership_stats.count or 0,
            "credit_consume": abs(credit_consume),
            "generation_count": generation_count,
            "activity_participants": activity_participants,
            "coupon_used": coupon_used,
            "referral_count": referral_count,
            "referral_rewards": float(referral_rewards),
            "revenue_trend": revenue_trend,
            "users_trend": users_trend,
            "user_trend": {
                "dates": date_strs,
                "new_users": [users_by_day.get(d, 0) for d in date_strs],
                "active_users": [active_users_by_day.get(d, 0) for d in date_strs],
            },
            "members_trend": members_trend,
            "creations_trend": creations_trend,
            "revenue_details": revenue_details,
            "user_details": user_details,
            "creation_details": creation_details,
            "creation_distribution": creation_distribution,
            "payment_distribution": payment_distribution,
        }
    
    async def get_user_statistics(self, user_id: int, start_date: Optional[datetime] = None, 
                                 end_date: Optional[datetime] = None) -> Dict[str, Any]:
        """获取用户运营统计数据"""
        from app.models.creation import Creation
        
        # 设置默认时间范围（最近30天）
        if not end_date:
            end_date = datetime.now()
        if not start_date:
            start_date = end_date - timedelta(days=30)
        
        # 创作统计
        total_creations = self.db.query(Creation).filter(
            Creation.user_id == user_id,
            Creation.created_at >= start_date,
            Creation.created_at <= end_date
        ).count()
        
        # 活动参与统计
        activities_participated = self.db.query(ActivityParticipation).filter(
            ActivityParticipation.user_id == user_id,
            ActivityParticipation.participated_at >= start_date,
            ActivityParticipation.participated_at <= end_date
        ).count()
        
        activity_rewards = self.db.query(func.sum(ActivityParticipation.reward_amount)).filter(
            ActivityParticipation.user_id == user_id,
            ActivityParticipation.participated_at >= start_date,
            ActivityParticipation.participated_at <= end_date
        ).scalar() or 0
        
        # 优惠券统计
        coupons_received = self.db.query(UserCoupon).filter(
            UserCoupon.user_id == user_id,
            UserCoupon.received_at >= start_date,
            UserCoupon.received_at <= end_date
        ).count()
        
        coupons_used = self.db.query(UserCoupon).filter(
            UserCoupon.user_id == user_id,
            UserCoupon.used_at >= start_date,
            UserCoupon.used_at <= end_date,
            UserCoupon.status == CouponStatus.USED
        ).count()
        
        # 推荐统计
        referrals_made = self.db.query(ReferralRecord).filter(
            ReferralRecord.referrer_id == user_id,
            ReferralRecord.created_at >= start_date,
            ReferralRecord.created_at <= end_date
        ).count()
        
        referral_rewards = self.db.query(func.sum(ReferralRecord.reward_amount)).filter(
            ReferralRecord.referrer_id == user_id,
            ReferralRecord.settled_at >= start_date,
            ReferralRecord.settled_at <= end_date,
            ReferralRecord.status == ReferralStatus.SETTLED
        ).scalar() or Decimal('0')
        
        return {
            "total_creations": total_creations,
            "activities_participated": activities_participated,
            "activity_rewards": float(activity_rewards),
            "coupons_received": coupons_received,
            "coupons_used": coupons_used,
            "referrals_made": referrals_made,
            "referral_rewards": float(referral_rewards)
        }
    
    async def get_operation_statistics(self, query: Any) -> Dict[str, Any]:
        """获取运营统计数据（管理员用）"""
        start_date = query.start_date if hasattr(query, 'start_date') else None
        end_date = query.end_date if hasattr(query, 'end_date') else None
        return await self.get_statistics(start_date, end_date)
    
    async def get_dashboard_statistics(self) -> Dict[str, Any]:
        """获取仪表盘统计数据（管理员用）"""
        from app.models.creation import Creation
        from app.models.credit import RechargeOrder, MembershipOrder
        
        # 总用户数
        total_users = self.db.query(User).count()
        
        # 今日新增用户
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        today_new_users = self.db.query(User).filter(
            User.created_at >= today
        ).count()
        
        # 总创作数
        total_creations = self.db.query(Creation).count()
        
        # 今日创作数
        today_creations = self.db.query(Creation).filter(
            Creation.created_at >= today
        ).count()
        
        # 会员数
        total_members = self.db.query(User).filter(
            User.is_member == True
        ).count()
        
        # 总收入（充值 + 会员）
        total_recharge = self.db.query(func.sum(RechargeOrder.amount)).filter(
            RechargeOrder.payment_status == 'paid'
        ).scalar() or 0
        
        total_membership = self.db.query(func.sum(MembershipOrder.amount)).filter(
            MembershipOrder.payment_status == 'paid'
        ).scalar() or 0
        
        total_revenue = float(total_recharge) + float(total_membership)
        
        # 今日收入
        today_recharge = self.db.query(func.sum(RechargeOrder.amount)).filter(
            RechargeOrder.payment_status == 'paid',
            RechargeOrder.created_at >= today
        ).scalar() or 0
        
        today_membership = self.db.query(func.sum(MembershipOrder.amount)).filter(
            MembershipOrder.payment_status == 'paid',
            MembershipOrder.created_at >= today
        ).scalar() or 0
        
        today_revenue = float(today_recharge) + float(today_membership)
        
        # 活跃用户数（最近7天有创作的用户）
        week_ago = datetime.now() - timedelta(days=7)
        active_users = self.db.query(func.count(func.distinct(Creation.user_id))).filter(
            Creation.created_at >= week_ago
        ).scalar() or 0
        
        return {
            "total_users": total_users,
            "today_new_users": today_new_users,
            "total_creations": total_creations,
            "today_creations": today_creations,
            "total_members": total_members,
            "total_revenue": total_revenue,
            "today_revenue": today_revenue,
            "active_users": active_users
        }
