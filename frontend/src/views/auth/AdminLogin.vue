<template>
  <div class="admin-login-container">
    <div class="admin-login-card">
      <div class="admin-brand">
        <div class="brand-icon">AI</div>
        <h2>管理员登录</h2>
        <p>仅限白名单 IP / VPN 内网访问</p>
      </div>

      <el-form
        ref="loginFormRef"
        :model="loginForm"
        :rules="loginRules"
        class="admin-login-form"
        @submit.prevent="handleLogin"
      >
        <el-form-item prop="username">
          <el-input
            v-model="loginForm.username"
            placeholder="管理员账号"
            size="large"
            :prefix-icon="User"
            clearable
            @keyup.enter="handleLogin"
          />
        </el-form-item>

        <el-form-item prop="password">
          <el-input
            v-model="loginForm.password"
            type="password"
            placeholder="密码"
            size="large"
            :prefix-icon="Lock"
            show-password
            clearable
            @keyup.enter="handleLogin"
          />
        </el-form-item>

        <el-button
          type="primary"
          size="large"
          :loading="loading"
          class="admin-login-button"
          @click="handleLogin"
        >
          {{ loading ? '登录中...' : '登录管理端' }}
        </el-button>
      </el-form>

      <div class="admin-login-footer">
        <el-link type="primary" :underline="false" @click="router.push('/login')">
          返回用户登录
        </el-link>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, type FormInstance, type FormRules } from 'element-plus'
import { User, Lock } from '@element-plus/icons-vue'
import { useUserStore } from '@/store/user'

const router = useRouter()
const userStore = useUserStore()

const loginFormRef = ref<FormInstance>()
const loading = ref(false)

const loginForm = reactive({
  username: '',
  password: '',
})

const loginRules: FormRules = {
  username: [{ required: true, message: '请输入管理员账号', trigger: 'blur' }],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 6, message: '密码长度不能少于6位', trigger: 'blur' },
  ],
}

const handleLogin = async () => {
  if (!loginFormRef.value) return

  await loginFormRef.value.validate(async (valid) => {
    if (!valid) return

    loading.value = true
    try {
      await userStore.adminLogin(loginForm.username, loginForm.password)
      ElMessage.success('管理员登录成功')
      router.push('/')
    } catch {
      // 错误已在 request.ts 拦截器中提示
    } finally {
      loading.value = false
    }
  })
}
</script>

<style scoped lang="scss">
.admin-login-container {
  min-height: 100dvh;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
  background:
    radial-gradient(900px circle at 10% -10%, rgba(37, 99, 235, 0.25) 0%, transparent 55%),
    radial-gradient(700px circle at 110% 110%, rgba(14, 165, 233, 0.2) 0%, transparent 55%),
    linear-gradient(135deg, #f6f8ff 0%, #eef6ff 50%, #f3fbff 100%);
}

.admin-login-card {
  width: min(420px, 100%);
  padding: 40px 36px 28px;
  border-radius: 20px;
  border: 1px solid rgba(37, 99, 235, 0.12);
  background: rgba(255, 255, 255, 0.92);
  box-shadow: 0 24px 56px rgba(15, 23, 42, 0.12);
  backdrop-filter: blur(14px);
}

.admin-brand {
  margin-bottom: 26px;
  text-align: center;

  .brand-icon {
    width: 52px;
    height: 52px;
    margin: 0 auto 14px;
    display: flex;
    align-items: center;
    justify-content: center;
    border-radius: 16px;
    font-size: 16px;
    font-weight: 700;
    letter-spacing: 0.08em;
    color: #fff;
    background: linear-gradient(135deg, #2563eb, #0ea5e9);
  }

  h2 {
    margin: 0 0 8px;
    font-size: 24px;
    color: #0f172a;
  }

  p {
    margin: 0;
    font-size: 13px;
    color: #64748b;
  }
}

.admin-login-form {
  :deep(.el-input__wrapper) {
    border-radius: 10px;
  }

  .admin-login-button {
    width: 100%;
    height: 44px;
    margin-top: 8px;
    border-radius: 10px;
    font-size: 15px;
    font-weight: 600;
  }
}

.admin-login-footer {
  margin-top: 22px;
  text-align: center;
}
</style>
