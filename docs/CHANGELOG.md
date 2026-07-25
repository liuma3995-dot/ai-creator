# Changelog

所有对项目有可见影响的改动都会记录在此文件。

格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，
版本号遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

## [1.0.1] - 2026-07-23

### Fixed

#### 1. `DELETE /api/v1/creations/{id}` 返回 500 Internal Server Error

**症状**：用户点击"删除创作记录" → 弹窗确认 → 提示"服务器内部错误"

**根因**：模型层 `creations.model_id` 是普通 `BigInteger` 列，没有声明 `ForeignKey`；通过 `relationship(primaryjoin=..., remote_side=...)` 模拟外键关联。SQLAlchemy 推断级联方向时把删除创作的对象关联误判为"清空 AIModel 的主键"，抛出：

```
AssertionError: Dependency rule on column 'creations.model_id' tried
to blank-out primary key column 'ai_models.id' on instance '<AIModel>'
```

**修复**：
- 9 个 `models/*.py` 文件加 `ForeignKey("...", ondelete="CASCADE"/"RESTRICT")` 真实外键
- 移除 `relationship` 上多余的 `primaryjoin` / `remote_side`，让 ORM 自动推断
- `ai_models.id` 由 `Integer` 改为 `BigInteger`，与其他主键类型一致（解决 MySQL "Referencing column and referenced column are incompatible" 错误）

**新增的数据完整性保护**（25 个外键，DB 层强制）：
- **23 个 CASCADE**：用户删除 → 自动清理其创作 / AI 模型 / 平台账号 / 发布记录 / 积分流水 / 会员订单 / 充值订单 / 插件安装 / 插件选择 / 插件调用日志 / 插件评价 / OAuth 凭据 / OAuth 调用日志 / 活动参与 / 优惠券领取 / 推广记录
- **2 个 RESTRICT**：删除被创作引用的 `ai_models` 行 / 删除被发布记录引用的 `platform_accounts` 行 — DB 直接拒绝（MySQL `ERROR 1451`）
- 删创作自动级联清理 `creation_versions` / `publish_records` / `plugin_invocations` 中的关联行

**验证**：
- ✅ `DELETE /api/v1/creations/{id}` → HTTP 200 `{"message":"删除成功"}`
- ✅ CASCADE：删 creation → 对应 versions 从 1 变 0
- ✅ RESTRICT：尝试 `DELETE FROM ai_models WHERE id=1`（有创作引用）→ `ERROR 1451`

#### 2. `POST /api/v1/creations` 返回 500（前端所有"新建创作"按钮失效）

**症状**：在写作 / 生图 / 视频 / PPT 等所有生成功能页面点击"生成"或"创建"后弹出"服务器内部错误"

**根因**：`backend/app/api/v1/creations.py` 的 `create_creation` 函数引用了 schema 里不存在的字段：
```python
creation_type=creation_data.content_type,  # ❌ schema 是 creation_type
```
抛出：
```
AttributeError: 'CreationCreate' object has no attribute 'content_type'
```

**修复**：一行字符更正 — `content_type` → `creation_type`，与 Pydantic schema `CreationBase.creation_type` 对齐

### Changed

#### 数据库初始化脚本重写

**变更**：`backend/scripts/init_db.py` 不再"主动剥离外键约束"

**原因**：原实现读取 `Base.metadata` 后手动重建 `MetaData()` 并跳过所有外键约束，使得模型层的 `ForeignKey()` 形同虚设。这次 FK 修复需要真实的 DB 级约束，所以脚本改为直接 `Base.metadata.create_all(engine)`。

#### 数据库文档扩充

**变更**：`docs/DATABASE.md` 的"外键约束"段从 5 行扩展到完整 FK 表（23 CASCADE + 2 RESTRICT），新增 `DELETE /api/v1/creations/{id}` 接口行为说明小节

---

## 升级指南

### 从 1.0.0 升级到 1.0.1

**数据库**（必须）：

```bash
# 1. 删除数据库重新创建（FK 约束会从模型自动生成）
mysql -u root -p -e "DROP DATABASE ai_creator; CREATE DATABASE ai_creator CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"

# 2. 重新初始化
cd backend && python scripts/init_db.py
```

⚠️ 现有数据会丢失。如果需要保留数据，请手动：

```sql
-- 查看所有 FK 状态
SELECT TABLE_NAME, CONSTRAINT_NAME FROM information_schema.KEY_COLUMN_USAGE
WHERE TABLE_SCHEMA='ai_creator' AND REFERENCED_TABLE_NAME IS NOT NULL;

-- 手工迁移方法：导出 → DROP → CREATE → 导入
mysqldump ai_creator > backup.sql  # 保存当前数据
# 按上面步骤重建库后再导入
```

**应用代码**：

- 无 API 变更（DELETE 端点语义从"删失败"变成"删成功 + 自动级联"）
- 无 schema 变更
- 前端无变更

---

[1.0.0]: 见 Git 提交历史
