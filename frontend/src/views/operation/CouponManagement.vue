<template>
  <div class="coupon-management">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>优惠券管理</span>
          <el-button type="primary" @click="showCreateDialog">创建优惠券</el-button>
        </div>
      </template>

      <el-form :inline="true" :model="searchForm">
        <el-form-item label="优惠券类型" style="width: 20%">
          <el-select v-model="searchForm.coupon_type" placeholder="全部" clearable>
            <el-option label="充值折扣券" value="recharge_discount" />
            <el-option label="充值赠送券" value="recharge_bonus" />
            <el-option label="会员折扣券" value="membership_discount" />
            <el-option label="通用券" value="general" />
          </el-select>
        </el-form-item>
        <el-form-item label="状态" style="width: 20%">
          <el-select v-model="searchForm.is_active" placeholder="全部" clearable>
            <el-option label="启用" :value="true" />
            <el-option label="禁用" :value="false" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="loadCoupons">查询</el-button>
        </el-form-item>
      </el-form>

      <el-table :data="coupons" style="width: 100%">
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="code" label="优惠券码" />
        <el-table-column prop="name" label="优惠券名称" />
        <el-table-column prop="coupon_type" label="类型">
          <template #default="{ row }">
            <el-tag v-if="row.coupon_type === 'recharge_discount'">充值折扣</el-tag>
            <el-tag v-else-if="row.coupon_type === 'recharge_bonus'" type="warning">充值赠送</el-tag>
            <el-tag v-else type="success">会员折扣</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="discount_value" label="折扣">
          <template #default="{ row }">
            <span v-if="row.discount_type === 'fixed'">{{ row.discount_value }}元</span>
            <span v-else>{{ row.discount_value }}%</span>
          </template>
        </el-table-column>
        <el-table-column label="使用情况">
          <template #default="{ row }">
            {{ row.used_quantity }} / {{ row.total_quantity }}
          </template>
        </el-table-column>
        <el-table-column prop="is_active" label="状态">
          <template #default="{ row }">
            <el-tag v-if="row.is_active" type="success">启用</el-tag>
            <el-tag v-else type="danger">禁用</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="340">
          <template #default="{ row }">
            <el-button size="small" @click="viewCoupon(row)">查看</el-button>
            <el-button size="small" type="primary" @click="editCoupon(row)">编辑</el-button>
            <el-button size="small" type="success" @click="showIssueDialog(row)">发放</el-button>
            <el-button size="small" type="warning" @click="voidCouponAction(row)">作废</el-button>
            <el-button size="small" type="danger" @click="deleteCoupon(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>

      <el-pagination
        v-model:current-page="pagination.page"
        v-model:page-size="pagination.pageSize"
        :total="pagination.total"
        layout="total, prev, pager, next"
        @current-change="loadCoupons"
      />
    </el-card>

    <!-- 创建/编辑优惠券对话框 -->
    <el-dialog v-model="dialogVisible" :title="dialogTitle" width="600px">
      <el-form :model="couponForm" label-width="120px">
        <el-form-item label="优惠券码" required>
          <el-input v-model="couponForm.code" />
        </el-form-item>
        <el-form-item label="优惠券名称" required>
          <el-input v-model="couponForm.name" />
        </el-form-item>
        <el-form-item label="描述" required>
          <el-input v-model="couponForm.description" type="textarea" :rows="3" />
        </el-form-item>
        <el-form-item label="优惠券类型" required>
          <el-select v-model="couponForm.coupon_type">
            <el-option label="充值折扣券" value="recharge_discount" />
            <el-option label="充值赠送券" value="recharge_bonus" />
            <el-option label="会员折扣券" value="membership_discount" />
            <el-option label="通用券" value="general" />
          </el-select>
        </el-form-item>
        <el-form-item label="折扣类型" required>
          <el-select v-model="couponForm.discount_type">
            <el-option label="百分比" value="percent" />
            <el-option label="固定金额" value="fixed" />
          </el-select>
        </el-form-item>
        <el-form-item label="折扣值" required>
          <el-input-number v-model="couponForm.discount_value" :min="0" />
        </el-form-item>
        <el-form-item label="最低消费金额" required>
          <el-input-number v-model="couponForm.min_amount" :min="0" />
        </el-form-item>
        <el-form-item label="最大折扣金额">
          <el-input-number v-model="couponForm.max_discount" :min="0" />
        </el-form-item>
        <el-form-item label="发行数量" required>
          <el-input-number v-model="couponForm.total_quantity" :min="1" />
        </el-form-item>
        <el-form-item label="每人限领数量">
          <el-input-number v-model="couponForm.per_user_limit" :min="1" />
        </el-form-item>
        <el-form-item label="开始时间" required>
          <el-date-picker
            v-model="couponForm.valid_from"
            type="datetime"
            placeholder="选择开始时间"
          />
        </el-form-item>
        <el-form-item label="结束时间" required>
          <el-date-picker
            v-model="couponForm.valid_until"
            type="datetime"
            placeholder="选择结束时间"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="saveCoupon">保存</el-button>
      </template>
    </el-dialog>

    <!-- 发放优惠券对话框 -->
    <el-dialog v-model="issueVisible" title="发放优惠券" width="480px">
      <el-form label-width="100px">
        <el-form-item label="优惠券">
          <span>{{ issueTarget?.code }}（{{ issueTarget?.name }}）</span>
        </el-form-item>
        <el-form-item label="用户ID" required>
          <el-input
            v-model="issueUserIds"
            type="textarea"
            :rows="4"
            placeholder="填写用户ID，多个用英文逗号分隔，如：1,2,3"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="issueVisible = false">取消</el-button>
        <el-button type="primary" @click="doIssue">确认发放</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import * as operationApi from '@/api/operation'

const coupons = ref<operationApi.Coupon[]>([])
const searchForm = reactive({
  coupon_type: '',
  is_active: undefined as boolean | undefined,
})

const pagination = reactive({
  page: 1,
  pageSize: 10,
  total: 0,
})

const dialogVisible = ref(false)
const dialogTitle = ref('创建优惠券')
const issueVisible = ref(false)
const issueTarget = ref<operationApi.Coupon | null>(null)
const issueUserIds = ref('')
const couponForm = reactive({
  id: 0,
  code: '',
  name: '',
  description: '',
  coupon_type: 'recharge_discount',
  discount_type: 'percent',
  discount_value: 0,
  min_amount: 0,
  max_discount: undefined as number | undefined,
  total_quantity: 100,
  per_user_limit: undefined as number | undefined,
  valid_from: '',
  valid_until: '',
})

const loadCoupons = async () => {
  try {
    const params = {
      skip: (pagination.page - 1) * pagination.pageSize,
      limit: pagination.pageSize,
      ...searchForm,
    }
    const response = await operationApi.getCoupons(params)
    coupons.value = response.data.items
    pagination.total = response.data.total
  } catch (error) {
    ElMessage.error('加载优惠券列表失败')
  }
}

const showCreateDialog = () => {
  dialogTitle.value = '创建优惠券'
  resetForm()
  dialogVisible.value = true
}

const viewCoupon = (coupon: operationApi.Coupon) => {
  ElMessageBox.alert(
    `<p><strong>优惠券码：</strong>${coupon.code}</p>
     <p><strong>优惠券名称：</strong>${coupon.name}</p>
     <p><strong>描述：</strong>${coupon.description}</p>
     <p><strong>折扣：</strong>${coupon.discount_type === 'fixed' ? coupon.discount_value + '元' : coupon.discount_value + '%'}</p>
     <p><strong>使用情况：</strong>${coupon.used_quantity} / ${coupon.total_quantity}</p>`,
    '优惠券详情',
    {
      dangerouslyUseHTMLString: true,
    }
  )
}

const showIssueDialog = (coupon: operationApi.Coupon) => {
  issueTarget.value = coupon
  issueUserIds.value = ''
  issueVisible.value = true
}

const doIssue = async () => {
  if (!issueTarget.value) return
  const ids = issueUserIds.value
    .split(',')
    .map((s) => parseInt(s.trim(), 10))
    .filter((n) => Number.isInteger(n) && n > 0)
  if (ids.length === 0) {
    ElMessage.warning('请填写有效的用户ID')
    return
  }
  try {
    const response = await operationApi.issueCoupon(issueTarget.value.id, ids)
    ElMessage.success(`已发放 ${response.data.issued} 张（重复领取自动跳过）`)
    issueVisible.value = false
    loadCoupons()
  } catch (error) {
    ElMessage.error('发放失败')
  }
}

const voidCouponAction = async (coupon: operationApi.Coupon) => {
  try {
    await ElMessageBox.confirm(
      '确定作废这张优惠券吗？用户未使用的券将全部失效。',
      '提示',
      { type: 'warning' }
    )
    await operationApi.voidCoupon(coupon.id)
    ElMessage.success('作废成功')
    loadCoupons()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('作废失败')
    }
  }
}

const editCoupon = (coupon: operationApi.Coupon) => {
  dialogTitle.value = '编辑优惠券'
  Object.assign(couponForm, coupon)
  dialogVisible.value = true
}

const deleteCoupon = async (coupon: operationApi.Coupon) => {
  try {
    await ElMessageBox.confirm('确定要删除这个优惠券吗？', '提示', {
      type: 'warning',
    })
    await operationApi.deleteCoupon(coupon.id)
    ElMessage.success('删除成功')
    loadCoupons()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('删除失败')
    }
  }
}

const saveCoupon = async () => {
  try {
    if (couponForm.id) {
      await operationApi.updateCoupon(couponForm.id, couponForm)
      ElMessage.success('更新成功')
    } else {
      await operationApi.createCoupon(couponForm)
      ElMessage.success('创建成功')
    }
    dialogVisible.value = false
    loadCoupons()
  } catch (error) {
    ElMessage.error('保存失败')
  }
}

const resetForm = () => {
  couponForm.id = 0
  couponForm.code = ''
  couponForm.name = ''
  couponForm.description = ''
  couponForm.coupon_type = 'recharge_discount'
  couponForm.discount_type = 'percent'
  couponForm.discount_value = 0
  couponForm.min_amount = 0
  couponForm.max_discount = undefined
  couponForm.total_quantity = 100
  couponForm.per_user_limit = undefined
  couponForm.valid_from = ''
  couponForm.valid_until = ''
}

onMounted(() => {
  loadCoupons()
})
</script>

<style scoped>
.coupon-management {
  padding: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.el-pagination {
  margin-top: 20px;
  justify-content: center;
}
</style>
