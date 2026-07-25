"""
数据库初始化脚本
"""
import sys
from pathlib import Path

# 添加项目根目录到Python路径
backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

from app.core.database import engine
from sqlalchemy import text


def init_db():
    """初始化数据库"""
    print("开始初始化数据库...")

    # 直接用 Base.metadata.create_all —— 真实 FK 约束会一并创建
    # （models/ 里已加 ForeignKey(..., ondelete="CASCADE"/"RESTRICT")）
    print("正在创建所有表（含外键约束）...")
    from app.core.database import Base

    # 禁用外键检查让 DROP/重建顺序更稳
    with engine.connect() as conn:
        conn.execute(text("SET FOREIGN_KEY_CHECKS = 0"))
        conn.commit()

    # 如果表已存在则先 drop（仅供重建场景，默认空库不会触发）
    Base.metadata.drop_all(bind=engine)
    # 重新创建（带 FK 约束）
    Base.metadata.create_all(bind=engine)

    print("[SUCCESS] All tables created (with FK constraints)")

    # 重新启用外键检查
    with engine.connect() as conn:
        conn.execute(text("SET FOREIGN_KEY_CHECKS = 1"))
        conn.commit()

    print("\n[SUCCESS] Database initialization completed!")
    print("外键策略（按 docs/DATABASE.md 设计）:")
    print("  CASCADE:  user→creations / platform_accounts / publish_records / plugin_invocations / user_plugins / ...")
    print("  CASCADE:  creation→creation_versions / publish_records / plugin_invocations")
    print("  RESTRICT: ai_models ← creations.model_id  （被引用禁删）")
    print("  RESTRICT: platform_accounts ← publish_records.platform_account_id  （被引用禁删）")


if __name__ == "__main__":
    init_db()
