# OAuth功能单元测试

## 测试概述

本目录包含OAuth功能的完整单元测试，覆盖以下模块：

- **OAuth服务测试** (`test_oauth_service.py`)
  - 平台管理
  - 账号管理
  - Cookie加密解密
  - Playwright浏览器自动化

- **OAuth API测试** (`test_oauth_api.py`)
  - 平台API端点
  - 账号API端点
  - OAuth流程API
  - LiteLLM代理API

## 安装测试依赖

```bash
cd backend
pip install -r requirements-test.txt
```

## 运行测试

### 运行所有测试
```bash
pytest
```

### 运行特定测试文件
```bash
pytest tests/test_oauth_service.py
pytest tests/test_oauth_api.py
```

### 运行特定测试类
```bash
pytest tests/test_oauth_service.py::TestOAuthService
pytest tests/test_oauth_api.py::TestOAuthAPI
```

### 运行特定测试方法
```bash
pytest tests/test_oauth_service.py::TestOAuthService::test_get_platforms
```

### 查看测试覆盖率
```bash
pytest --cov=app --cov-report=html
```

覆盖率报告将生成在 `htmlcov/index.html`

### 详细输出
```bash
pytest -v -s
```

### 只运行失败的测试
```bash
pytest --lf
```

## 测试结构

```
tests/
├── __init__.py              # 测试包初始化
├── conftest.py              # Pytest配置和fixtures
├── test_oauth_service.py    # OAuth服务测试
├── test_oauth_api.py        # OAuth API测试
└── README.md                # 本文件
```

## Fixtures说明

### 数据库Fixtures
- `engine`: 测试数据库引擎（session级别）
- `db_session`: 测试数据库会话（function级别）
- `client`: FastAPI测试客户端

### 测试数据Fixtures
- `test_user`: 测试用户
- `test_platform`: 测试平台配置
- `test_oauth_account`: 测试OAuth账号
- `auth_headers`: 认证请求头

### Mock Fixtures
- `mock_playwright`: Mock的Playwright对象

## 测试覆盖范围

### OAuth服务测试
- ✅ 获取平台列表
- ✅ 根据ID获取平台
- ✅ 获取用户账号列表
- ✅ 根据ID获取账号
- ✅ 创建OAuth账号
- ✅ 更新账号Cookie
- ✅ 删除账号
- ✅ 检查账号有效性
- ✅ 获取账号Cookie
- ✅ 数据加密解密

### OAuth API测试
- ✅ 获取平台列表API
- ✅ 获取平台详情API
- ✅ 获取用户账号列表API
- ✅ 获取账号详情API
- ✅ 启动OAuth流程API
- ✅ 执行OAuth操作API
- ✅ 完成OAuth流程API
- ✅ 删除账号API
- ✅ 检查账号有效性API
- ✅ 聊天完成API
- ✅ 错误处理测试

## 注意事项

1. **测试数据库**
   - 使用SQLite内存数据库进行测试
   - 每个测试函数都会回滚数据库事务
   - 测试结束后自动清理数据库文件

2. **Mock对象**
   - Playwright相关操作使用Mock对象
   - LiteLLM API调用使用Mock对象
   - 避免实际的网络请求和浏览器操作

3. **异步测试**
   - 使用`@pytest.mark.asyncio`标记异步测试
   - 配置文件中已启用`asyncio_mode = auto`

4. **测试隔离**
   - 每个测试函数独立运行
   - 使用fixtures确保测试数据隔离
   - 避免测试之间的相互影响

## 持续集成

可以在CI/CD流程中集成测试：

```yaml
# .github/workflows/test.yml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Set up Python
        uses: actions/setup-python@v2
        with:
          python-version: '3.10'
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install -r requirements-test.txt
      - name: Run tests
        run: pytest --cov=app --cov-report=xml
      - name: Upload coverage
        uses: codecov/codecov-action@v2
```

## 故障排查

### 测试失败
1. 检查数据库连接配置
2. 确认所有依赖已安装
3. 查看详细错误信息：`pytest -v -s`

### 导入错误
1. 确认项目根目录在Python路径中
2. 检查`conftest.py`中的路径配置

### 异步测试问题
1. 确认已安装`pytest-asyncio`
2. 检查`pytest.ini`中的`asyncio_mode`配置

## 扩展测试

添加新测试时：

1. 在相应的测试文件中添加测试类或方法
2. 使用现有的fixtures或创建新的fixtures
3. 遵循命名规范：`test_*`
4. 添加清晰的文档字符串
5. 确保测试独立且可重复运行

## 运营管理模块测试

覆盖前端“运营管理”菜单下的全部 7 个子模块（活动、优惠券、推广、数据统计、用户管理、流量统计、调用监控）。

### 测试文件

```
tests/
├── test_operation_service.py   # 服务层：活动/优惠券/推广/统计业务规则
├── test_operation_api.py       # operation 路由 API：权限、404、响应结构
├── test_admin_users_api.py     # 用户管理 API
├── test_traffic_api.py         # 流量统计 API（mock Redis）
└── test_model_usage_api.py     # 调用监控 API
```

### 运行方式

```bash
cd backend
venv\Scripts\python -m pytest tests/test_operation_service.py tests/test_operation_api.py tests/test_admin_users_api.py tests/test_traffic_api.py tests/test_model_usage_api.py -v
```

### 关键说明

1. **权限矩阵**：管理员接口统一覆盖匿名（401/403）、普通用户（403）、管理员（200）三条路径。
2. **Redis**：流量统计的埋点上报与缓存统计会调用 `tracker_service`，测试通过 `mock_tracker` fixture 替换，不依赖真实 Redis。
3. **种子数据**：`client` fixture 启动应用时会初始化基础数据（价格配置、插件、种子管理员），统计类断言请与库内实际数量对比，勿写死 0。
4. **SQLite 兼容**：`init_db()` 已按数据库方言跳过 MySQL 专用语句，SQLite 测试环境可正常启动。

## 运营管理集成测试

集成测试使用真实 MySQL（`ai_creator_test` 测试库）与 Redis（db 1），验证跨模块协作链路。MySQL 测试库不可用时自动跳过。

### 测试文件

```
tests/integration/
├── conftest.py                              # MySQL/Redis fixtures、用例间数据清理
├── test_activity_credit_integration.py      # 活动参与 → 积分发放链路
├── test_traffic_integration.py              # 埋点 Redis → 后台同步 → 查询链路
├── test_admin_users_integration.py          # 用户管理全链路
├── test_statistics_integration.py           # 统计跨模块聚合口径
└── test_model_usage_integration.py          # AI 调用 → 监控日志链路
```

### 运行方式

```bash
cd backend
venv\Scripts\python -m pytest tests/integration -m integration -v
```

前置条件：MySQL 已创建 `ai_creator_test` 测试库（`CREATE DATABASE ai_creator_test CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci`）；Memurai/Redis 运行中。

### 集成测试注意事项

1. **数据隔离**：只用独立测试库，每个用例结束后清空全部表；后台同步线程不启动，由测试手动触发同步方法。
2. **隔离级别**：测试引擎使用 READ COMMITTED，保证验证会话能立即看到 API 会话提交的数据；跨会话修改的 ORM 对象需先 `expire_all()` 再查询。
3. **Decimal 序列化**：FastAPI 会把 Decimal 序列化为字符串（如 `"total_tokens": "15"`），断言按数值比较（`float(...)`）。
4. **时间边界**：系统时钟存在回拨抖动，时间相关测试数据使用相对当前时间的固定偏移，避免边界断言偶发失败。

### 已知缺口（代码未接线，暂不做集成测试目标）

- **注册 → 推荐绑定**：`auth /register` 未调用 `ReferralService.process_referral`，注册时不会建立推荐关系。
- **优惠券 → 订单抵扣**：`credit.py` 无 coupon 引用，`use_coupon` 只标记状态、不参与充值/会员订单金额计算。

上述两条链路补代码后，再补充对应集成测试。

## 参考资料

- [Pytest文档](https://docs.pytest.org/)
- [FastAPI测试](https://fastapi.tiangolo.com/tutorial/testing/)
- [SQLAlchemy测试](https://docs.sqlalchemy.org/en/14/orm/session_transaction.html)
