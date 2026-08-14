<template>
  <div class="activity-management">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>活动管理</span>
          <el-button type="primary" @click="showCreateDialog">创建活动</el-button>
        </div>
      </template>

      <el-form :inline="true" :model="searchForm">
        <el-form-item label="活动类型" style="width: 20%">
          <el-select v-model="searchForm.activity_type" placeholder="全部" clearable>
            <el-option label="积分赠送" value="credit_gift" />
            <el-option label="优惠券活动" value="coupon" />
          </el-select>
        </el-form-item>
        <el-form-item label="状态" style="width: 20%">
          <el-select v-model="searchForm.status" placeholder="全部" clearable>
            <el-option label="草稿" value="draft" />
            <el-option label="进行中" value="active" />
            <el-option label="暂停" value="paused" />
            <el-option label="已结束" value="ended" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="loadActivities">查询</el-button>
        </el-form-item>
      </el-form>

      <el-table :data="activities" style="width: 100%">
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="title" label="活动标题" />
        <el-table-column prop="activity_type" label="活动类型">
          <template #default="{ row }">
            <el-tag v-if="row.activity_type === 'credit_gift'">积分赠送</el-tag>
            <el-tag v-else-if="row.activity_type === 'coupon'" type="warning">优惠券活动</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="奖励金额" width="100">
          <template #default="{ row }">
            {{ row.reward_amount ?? 0 }}
          </template>
        </el-table-column>
        <el-table-column label="参与人数" width="120">
          <template #default="{ row }">
            <span>{{ row.current_participants ?? 0 }}</span>
            <span v-if="row.max_participants" style="color: #909399"> / {{ row.max_participants }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态">
          <template #default="{ row }">
            <el-tag v-if="row.status === 'draft'" type="info">草稿</el-tag>
            <el-tag v-else-if="row.status === 'active'" type="success">进行中</el-tag>
            <el-tag v-else-if="row.status === 'paused'" type="warning">暂停</el-tag>
            <el-tag v-else type="danger">已结束</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="360">
          <template #default="{ row }">
            <el-button size="small" @click="viewActivity(row)">查看</el-button>
            <el-button size="small" type="primary" @click="editActivity(row)">编辑</el-button>
            <el-button size="small" type="danger" @click="deleteActivity(row)">删除</el-button>
            <el-button
              v-if="row.status === 'draft' || row.status === 'paused'"
              size="small"
              type="success"
              @click="changeStatus(row, 'active')"
            >发布</el-button>
            <el-button
              v-if="row.status === 'active'"
              size="small"
              type="warning"
              @click="changeStatus(row, 'paused')"
            >暂停</el-button>
            <el-button
              v-if="row.status === 'draft' || row.status === 'active' || row.status === 'paused'"
              size="small"
              type="danger"
              @click="changeStatus(row, 'ended')"
            >结束</el-button>
          </template>
        </el-table-column>
      </el-table>

      <el-pagination
        v-model:current-page="pagination.page"
        v-model:page-size="pagination.pageSize"
        :total="pagination.total"
        layout="total, prev, pager, next"
        @current-change="loadActivities"
      />
    </el-card>

    <!-- 创建/编辑活动对话框 -->
    <el-dialog
      v-model="dialogVisible"
      :title="dialogTitle"
      width="600px"
    >
      <el-form :model="activityForm" label-width="100px">
        <el-form-item label="活动标题" required>
          <el-input v-model="activityForm.title" />
        </el-form-item>
        <el-form-item label="活动描述" required>
          <el-input v-model="activityForm.description" type="textarea" :rows="3" />
        </el-form-item>
        <el-form-item label="活动类型" required>
          <el-select v-model="activityForm.activity_type">
            <el-option label="积分赠送" value="credit_gift" />
            <el-option label="优惠券活动" value="coupon" />
          </el-select>
        </el-form-item>
        <el-form-item label="奖励类型" required>
          <el-select v-model="activityForm.reward_type">
            <el-option label="积分" value="credit" />
            <el-option label="优惠券" value="coupon" />
          </el-select>
        </el-form-item>
        <el-form-item label="奖励金额" required>
          <el-input-number v-model="activityForm.reward_amount" :min="0" />
        </el-form-item>
        <el-form-item v-if="activityForm.activity_type === 'coupon'" label="关联优惠券" required>
          <el-select v-model="activityForm.couponId" placeholder="选择要发放的优惠券" style="width: 100%">
            <el-option
              v-for="c in couponOptions"
              :key="c.id"
              :label="`${c.name}（${c.code}）`"
              :value="c.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="开始时间" required>
          <el-date-picker
            v-model="activityForm.start_time"
            type="datetime"
            placeholder="选择开始时间"
          />
        </el-form-item>
        <el-form-item label="结束时间" required>
          <el-date-picker
            v-model="activityForm.end_time"
            type="datetime"
            placeholder="选择结束时间"
          />
        </el-form-item>
        <el-form-item label="参与人数限制">
          <el-input-number v-model="activityForm.max_participants" :min="0" />
        </el-form-item>
        <el-form-item label="活动预算">
          <el-input-number v-model="activityForm.budget" :min="0" :precision="2" :step="0.01" />
        </el-form-item>
        <el-form-item label="目标用户">
          <el-input
            v-model="activityForm.target_users"
            type="textarea"
            :rows="3"
            placeholder='JSON，如 {"level":"vip"}，留空表示全部用户'
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="saveActivity">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import * as operationApi from '@/api/operation'

const activities = ref<operationApi.Activity[]>([])
const searchForm = reactive({
  activity_type: '',
  status: '',
})

const pagination = reactive({
  page: 1,
  pageSize: 10,
  total: 0,
})

const dialogVisible = ref(false)
const dialogTitle = ref('创建活动')
const activityForm = reactive({
  id: 0,
  title: '',
  description: '',
  activity_type: 'credit_gift',
  reward_type: 'credit',
  reward_amount: 0,
  couponId: undefined as number | undefined,
  start_time: '' as string | Date,
  end_time: '' as string | Date,
  max_participants: undefined as number | undefined,
  budget: undefined as number | undefined,
  target_users: '',
})

const couponOptions = ref<operationApi.Coupon[]>([])

const loadCouponOptions = async () => {
  try {
    const res: any = await operationApi.getCoupons({ skip: 0, limit: 100 })
    const items: operationApi.Coupon[] = res.data?.items || res.data || []
    couponOptions.value = items.filter((c) => c.is_active !== false)
  } catch (e) {
    console.error('加载优惠券选项失败:', e)
  }
}

const loadActivities = async () => {
  try {
    const params = {
      skip: (pagination.page - 1) * pagination.pageSize,
      limit: pagination.pageSize,
      ...searchForm,
    }
    const response = await operationApi.getActivities(params)
    activities.value = response.data.items
    pagination.total = response.data.total
  } catch (error) {
    ElMessage.error('加载活动列表失败')
  }
}

const showCreateDialog = () => {
  dialogTitle.value = '创建活动'
  resetForm()
  dialogVisible.value = true
}

const viewActivity = (activity: operationApi.Activity) => {
  const max = activity.max_participants
  const cur = activity.current_participants ?? 0
  const participantsLine = max
    ? `<p><strong>参与人数：</strong>${cur} / ${max}</p>`
    : `<p><strong>参与人数：</strong>${cur}（不限）</p>`
  ElMessageBox.alert(
    `<p><strong>活动标题：</strong>${activity.title}</p>
     <p><strong>活动描述：</strong>${activity.description ?? '（无）'}</p>
     <p><strong>奖励金额：</strong>${activity.reward_amount ?? 0}</p>
     ${participantsLine}`,
    '活动详情',
    {
      dangerouslyUseHTMLString: true,
    }
  )
}

const editActivity = (activity: operationApi.Activity) => {
  dialogTitle.value = '编辑活动'
  Object.assign(activityForm, activity, {
    budget: activity.budget != null ? Number(activity.budget) : undefined,
    target_users: activity.target_users
      ? JSON.stringify(activity.target_users, null, 2)
      : '',
    couponId: (activity.rules as any)?.coupon_id ?? undefined,
  })
  dialogVisible.value = true
}

const deleteActivity = async (activity: operationApi.Activity) => {
  try {
    await ElMessageBox.confirm('确定要删除这个活动吗？', '提示', {
      type: 'warning',
    })
    await operationApi.deleteActivity(activity.id)
    ElMessage.success('删除成功')
    loadActivities()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('删除失败')
    }
  }
}

const changeStatus = async (activity: operationApi.Activity, status: string) => {
  try {
    await operationApi.updateActivity(activity.id, { status })
    ElMessage.success('状态更新成功')
    loadActivities()
  } catch (error) {
    ElMessage.error('状态更新失败')
  }
}

const saveActivity = async () => {
  try {
    if (!activityForm.start_time || !activityForm.end_time) {
      ElMessage.error('请选择活动开始和结束时间')
      return
    }
    if (new Date(activityForm.end_time).getTime() <= new Date(activityForm.start_time).getTime()) {
      ElMessage.error('结束时间必须晚于开始时间')
      return
    }
    let target_users: unknown
    if (activityForm.target_users && activityForm.target_users.trim()) {
      try {
        target_users = JSON.parse(activityForm.target_users)
      } catch (e) {
        ElMessage.error('目标用户必须是合法 JSON')
        return
      }
    }
    const payload: any = {
      ...activityForm,
      budget: activityForm.budget ?? undefined,
      target_users,
    }
    if (activityForm.activity_type === 'coupon') {
      const coupon = couponOptions.value.find((c) => c.id === activityForm.couponId)
      if (!coupon) {
        ElMessage.error('请选择要发放的优惠券')
        return
      }
      payload.rules = {
        ...(payload.rules || {}),
        reward_type: 'coupon',
        coupon_id: coupon.id,
        coupon_code: coupon.code,
      }
    }
    if (activityForm.id) {
      await operationApi.updateActivity(activityForm.id, payload)
      ElMessage.success('更新成功')
    } else {
      await operationApi.createActivity(payload)
      ElMessage.success('创建成功')
    }
    dialogVisible.value = false
    loadActivities()
  } catch (error) {
    ElMessage.error('保存失败')
  }
}

const resetForm = () => {
  activityForm.id = 0
  activityForm.title = ''
  activityForm.description = ''
  activityForm.activity_type = 'credit_gift'
  activityForm.reward_type = 'credit'
  activityForm.reward_amount = 0
  activityForm.couponId = undefined
  activityForm.start_time = new Date()
  activityForm.end_time = new Date(Date.now() + 7 * 24 * 60 * 60 * 1000)
  activityForm.max_participants = undefined
  activityForm.budget = undefined
  activityForm.target_users = ''
}

onMounted(() => {
  loadActivities()
  loadCouponOptions()
})
</script>

<style scoped>
.activity-management {
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
