<template>
  <div class="login-container">
    <div class="background-decoration">
      <div class="gradient-blob blob-1"></div>
      <div class="gradient-blob blob-2"></div>
      <div class="gradient-blob blob-3"></div>
    </div>

    <div class="login-content">
      <div class="login-card">
        <div class="login-shell">
          <section class="brand-panel">
            <div class="brand-header">
              <img src="/logo-mark.svg" alt="有梦" class="brand-icon" />
              <h2>有梦</h2>
              <p class="brand-en">Have a Dream</p>
              <p class="brand-slogan">让每一个灵感，长成作品</p>
            </div>
            <div class="brand-body">
              <div class="brand-tags">
                <span class="tag">文案</span>
                <span class="tag">图片</span>
                <span class="tag">视频</span>
              </div>
              <ul class="brand-features">
                <li>
                  <span class="feature-icon">1</span>
                  <span>一站式完成写作、图片、视频创作流程</span>
                </li>
                <li>
                  <span class="feature-icon">2</span>
                  <span>模板、素材和工作流整合，开箱即可开始创作</span>
                </li>
                <li>
                  <span class="feature-icon">3</span>
                  <span>创作记录与草稿管理，保持内容生产连续性</span>
                </li>
              </ul>
              <div class="brand-note">
                <span class="note-dot"></span>
                聚焦效率与审美，让创作体验更顺滑
              </div>
            </div>
          </section>

          <section class="form-panel">
            <div class="form-header">
              <h3>欢迎回来</h3>
              <p>登录后继续你的创作</p>
            </div>

            <div class="form-container">
              <el-form
                ref="loginFormRef"
                :model="loginForm"
                :rules="loginRules"
                class="login-form"
                @submit.prevent="handleLogin"
              >
                <el-form-item prop="username">
                  <el-input
                    v-model="loginForm.username"
                    placeholder="用户名或邮箱"
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

                <div class="remember-forgot-row">
                  <div class="remember-checkbox">
                    <el-checkbox v-model="loginForm.remember">
                      <span>记住我</span>
                    </el-checkbox>
                  </div>
                  <el-link type="primary" :underline="false" class="forgot-password-link" @click="goToForgotPassword">
                    忘记密码？
                  </el-link>
                </div>

                <el-form-item>
                  <el-button
                    type="primary"
                    size="large"
                    :loading="loading"
                    class="login-button"
                    @click="handleLogin"
                  >
                    {{ loading ? '登录中...' : '立即登录' }}
                  </el-button>
                </el-form-item>

                <div class="register-section">
                  <span>还没有账号？</span>
                  <el-link type="primary" :underline="false" class="register-link" @click="goToRegister">
                    立即注册
                  </el-link>
                </div>
              </el-form>
            </div>

          </section>
        </div>
      </div>
    </div>

    <el-dialog v-model="showForgotDialog" title="重置密码" width="400px" :close-on-click-modal="false">
      <p style="margin-bottom: 16px; color: #666;">
        请输入您的邮箱地址，我们将发送重置密码链接到您的邮箱。
      </p>
      <el-input v-model="resetEmail" placeholder="请输入您的邮箱" clearable />
      <template #footer>
        <el-button @click="showForgotDialog = false">取消</el-button>
        <el-button type="primary" @click="handleReset" :loading="resetLoading">
          发送重置链接
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ElMessage, type FormInstance, type FormRules } from 'element-plus'
import { User, Lock } from '@element-plus/icons-vue'
import { useUserStore } from '@/store/user'
import { requestPasswordReset } from '@/api/auth'

const router = useRouter()
const route = useRoute()
const userStore = useUserStore()

const loginFormRef = ref<FormInstance>()
const loading = ref(false)
const showForgotDialog = ref(false)
const resetEmail = ref('')
const resetLoading = ref(false)

const loginForm = reactive({
  username: '',
  password: '',
  remember: false,
})

const loginRules: FormRules = {
  username: [{ required: true, message: '请输入用户名或邮箱', trigger: 'blur' }],
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
      await userStore.login(loginForm.username, loginForm.password)
      ElMessage.success('登录成功')
      const redirect = (route.query.redirect as string) || '/'
      router.push(redirect)
    } catch {
      // 错误已在 request.ts 拦截器中处理，这里不再重复提示
    } finally {
      loading.value = false
    }
  })
}

const goToRegister = () => {
  router.push('/register')
}

const goToForgotPassword = () => {
  showForgotDialog.value = true
  resetEmail.value = ''
}

const handleReset = async () => {
  if (!resetEmail.value) {
    ElMessage.warning('请输入您的邮箱地址')
    return
  }

  resetLoading.value = true
  try {
    await requestPasswordReset({ email: resetEmail.value })
    ElMessage.success('重置链接已发送到您的邮箱，请检查收件箱')
    showForgotDialog.value = false
    resetEmail.value = ''
  } catch (error: any) {
    ElMessage.error(error.message || '发送失败，请稍后重试')
  } finally {
    resetLoading.value = false
  }
}
</script>

<style scoped lang="scss">
$primary-color: #2563eb;
$secondary-color: #38bdf8;
$accent-color: #0ea5e9;
$text-primary: #0f172a;
$text-secondary: #5b6472;
$shadow-lg: 0 32px 60px rgba(15, 23, 42, 0.16);

.login-container {
  position: relative;
  min-height: 100dvh;
  overflow: hidden;
  color: $text-primary;
  background:
    radial-gradient(1200px circle at -10% -20%, rgba(56, 189, 248, 0.28) 0%, transparent 60%),
    radial-gradient(900px circle at 110% 0%, rgba(37, 99, 235, 0.24) 0%, transparent 55%),
    radial-gradient(800px circle at 50% 120%, rgba(14, 165, 233, 0.2) 0%, transparent 60%),
    linear-gradient(135deg, #f6f8ff 0%, #eef6ff 45%, #f3fbff 100%);

  &::before {
    content: '';
    position: absolute;
    inset: 0;
    background-image:
      linear-gradient(120deg, rgba(37, 99, 235, 0.08) 0%, transparent 40%),
      linear-gradient(to right, rgba(37, 99, 235, 0.05) 1px, transparent 1px),
      linear-gradient(to bottom, rgba(37, 99, 235, 0.05) 1px, transparent 1px);
    background-size: auto, 48px 48px, 48px 48px;
    opacity: 0.35;
    pointer-events: none;
  }
}

.background-decoration {
  position: absolute;
  inset: 0;
  pointer-events: none;
  z-index: 0;
}

.gradient-blob {
  position: absolute;
  border-radius: 50%;
  filter: blur(70px);
  opacity: 0.35;

  &.blob-1 {
    width: 340px;
    height: 340px;
    top: -120px;
    left: -120px;
    background: rgba(56, 189, 248, 0.35);
    animation: float 8s ease-in-out infinite;
  }

  &.blob-2 {
    width: 280px;
    height: 280px;
    right: -80px;
    bottom: -80px;
    background: rgba(37, 99, 235, 0.3);
    animation: float 10s ease-in-out infinite reverse;
  }

  &.blob-3 {
    width: 220px;
    height: 220px;
    top: 50%;
    right: 10%;
    background: rgba(14, 165, 233, 0.25);
    animation: float 12s ease-in-out infinite;
  }
}

.login-content {
  position: relative;
  z-index: 1;
  min-height: 100dvh;
  padding: 24px 32px;
  display: flex;
  align-items: stretch;
  justify-content: center;
}

.login-card {
  position: relative;
  width: min(800px, 100%);
  min-height: calc(100dvh - 48px);
  overflow: hidden;
  border-radius: 26px;
  border: 1px solid rgba(255, 255, 255, 0.6);
  background: rgba(255, 255, 255, 0.82);
  box-shadow: $shadow-lg;
  backdrop-filter: blur(18px) saturate(1.08);
  animation: fadeInUp 0.7s cubic-bezier(0.16, 1, 0.3, 1);

  &::before {
    content: '';
    position: absolute;
    inset: 0 0 auto 0;
    height: 3px;
    background: linear-gradient(90deg, rgba(37, 99, 235, 0.1), rgba(37, 99, 235, 0.85), rgba(56, 189, 248, 0.8));
  }
}

.login-shell {
  display: grid;
  grid-template-columns: minmax(0, 1.05fr) minmax(0, 0.95fr);
  min-height: inherit;
}

.brand-panel {
  position: relative;
  padding: 44px 40px;
  display: flex;
  flex-direction: column;
  gap: 24px;
  background:
    linear-gradient(145deg, rgba(37, 99, 235, 0.18), rgba(56, 189, 248, 0.12)),
    radial-gradient(180px circle at 20% 15%, rgba(37, 99, 235, 0.2), transparent 70%);

  &::after {
    content: '';
    position: absolute;
    inset: 24px;
    border-radius: 24px;
    border: 1px solid rgba(255, 255, 255, 0.34);
    pointer-events: none;
  }
}

.form-panel {
  padding: 44px 42px;
  display: flex;
  flex-direction: column;
  background: linear-gradient(135deg, rgba(255, 255, 255, 0.95), rgba(239, 246, 255, 0.92));
  border-left: 1px solid rgba(37, 99, 235, 0.12);
}

.brand-header {
  margin-bottom: 4px;

  .brand-icon {
    width: 60px;
    height: 60px;
    margin-bottom: 14px;
    display: block;
    border-radius: 16px;
    box-shadow: 0 12px 24px rgba(37, 99, 235, 0.18);
    object-fit: contain;
  }

  h2 {
    margin: 0 0 10px;
    font-size: 32px;
    font-weight: 700;
    line-height: 1.15;
    letter-spacing: -0.6px;
  }

  .brand-en {
    margin: 0 0 10px;
    font-size: 13px;
    font-weight: 600;
    letter-spacing: 0.24em;
    color: rgba(37, 99, 235, 0.72);
  }

  .brand-slogan {
    margin: 0;
    font-size: 15px;
    line-height: 1.6;
    color: $text-secondary;
  }
}

.brand-body {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.brand-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;

  .tag {
    padding: 6px 12px;
    border-radius: 999px;
    font-size: 12px;
    font-weight: 600;
    color: $primary-color;
    background: rgba(255, 255, 255, 0.75);
    border: 1px solid rgba(37, 99, 235, 0.18);
    box-shadow: 0 6px 12px rgba(37, 99, 235, 0.1);
  }
}

.brand-features {
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 14px;

  li {
    display: flex;
    align-items: flex-start;
    gap: 12px;
    font-size: 14px;
    line-height: 1.5;
  }
}

.feature-icon {
  width: 28px;
  height: 28px;
  flex-shrink: 0;
  border-radius: 10px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  font-weight: 700;
  background: rgba(255, 255, 255, 0.84);
  color: $primary-color;
  box-shadow: 0 6px 12px rgba(37, 99, 235, 0.12);
}

.brand-note {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 14px;
  border-radius: 12px;
  font-size: 13px;
  color: $text-secondary;
  background: rgba(255, 255, 255, 0.7);
  border: 1px solid rgba(37, 99, 235, 0.12);
}

.note-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: linear-gradient(135deg, $primary-color, $secondary-color);
  box-shadow: 0 0 0 4px rgba(37, 99, 235, 0.16);
}

.form-header {
  margin-bottom: 20px;

  h3 {
    margin: 0 0 6px;
    font-size: 22px;
    font-weight: 700;
  }

  p {
    margin: 0;
    font-size: 13.5px;
    color: $text-secondary;
  }
}

.form-container {
  margin-bottom: 20px;
}

.login-form {
  width: 100%;

  :deep(.el-form-item__content),
  :deep(.el-input) {
    width: 100%;
  }

  .el-form-item {
    margin-bottom: 18px;

    &:last-child {
      margin-bottom: 0;
    }

    :deep(.el-input__wrapper) {
      border-radius: 12px;
      background: rgba(255, 255, 255, 0.86);
      border: 1px solid rgba(37, 99, 235, 0.14);
      box-shadow: inset 0 0 0 1px rgba(255, 255, 255, 0.4), 0 8px 16px rgba(37, 99, 235, 0.08);
      transition: all 0.3s ease;

      &:hover {
        border-color: rgba(37, 99, 235, 0.4);
        background: #fff;
      }

      &.is-focus {
        border-color: rgba(37, 99, 235, 0.6);
        box-shadow: 0 0 0 4px rgba(56, 189, 248, 0.22);
        background: #fff;
      }
    }

    :deep(.el-input__inner) {
      font-weight: 500;
      color: $text-primary;
    }

    :deep(.el-input__inner::placeholder) {
      color: rgba(91, 100, 114, 0.75);
    }

    :deep(.el-input__prefix) {
      color: rgba(37, 99, 235, 0.75);
    }
  }

  .remember-forgot-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 12px;
    margin: 18px 0 8px;
  }

  .remember-checkbox {
    :deep(.el-checkbox__label) {
      font-size: 14px;
      color: $text-secondary;
    }
  }

  .forgot-password-link {
    font-size: 14px;
    white-space: nowrap;
  }

  .login-button {
    width: 100%;
    height: 46px;
    margin: 18px 0 16px;
    border: none;
    border-radius: 12px;
    font-size: 16px;
    font-weight: 600;
    color: #fff;
    background: linear-gradient(135deg, $primary-color 0%, $accent-color 45%, $secondary-color 100%);
    box-shadow: 0 16px 28px rgba(37, 99, 235, 0.2);
  }

  .register-section {
    text-align: center;
    font-size: 14px;
    color: $text-secondary;

    span {
      margin-right: 4px;
    }

    .register-link {
      font-weight: 600;
    }
  }
}

@keyframes fadeInUp {
  from {
    opacity: 0;
    transform: translateY(30px);
  }

  to {
    opacity: 1;
    transform: translateY(0);
  }
}

@keyframes float {
  0%,
  100% {
    transform: translate(0, 0);
  }

  33% {
    transform: translate(30px, -30px);
  }

  66% {
    transform: translate(-20px, 20px);
  }
}

@media (max-width: 900px) {
  .login-content {
    padding: 20px;
  }

  .login-card {
    min-height: auto;
  }

  .login-shell {
    grid-template-columns: 1fr;
  }

  .form-panel {
    order: 1;
    padding: 34px 32px 26px;
    border-left: none;
  }

  .brand-panel {
    order: 2;
    padding: 30px 32px 32px;
  }

  .brand-header {
    margin-bottom: 0;
    text-align: center;

    .brand-icon {
      margin: 0 auto 10px;
    }

    h2 {
      font-size: 24px;
      margin-bottom: 6px;
    }
  }

  .brand-body {
    margin-top: 18px;
  }

  .brand-tags {
    justify-content: center;
  }
}

@media (max-width: 600px) {
  .background-decoration {
    opacity: 0.55;
  }

  .gradient-blob {
    filter: blur(60px);

    &.blob-1 {
      width: 220px;
      height: 220px;
      top: -80px;
      left: -90px;
    }

    &.blob-2 {
      width: 180px;
      height: 180px;
      right: -50px;
      bottom: -40px;
    }

    &.blob-3 {
      display: none;
    }
  }

  .login-content {
    min-height: auto;
    padding: 12px;
    display: block;
  }

  .login-card {
    min-height: auto;
    border-radius: 18px;
  }

  .form-panel {
    padding: 22px 20px 18px;
  }

  .brand-panel {
    padding: 20px;
    background:
      linear-gradient(145deg, rgba(37, 99, 235, 0.14), rgba(56, 189, 248, 0.08)),
      radial-gradient(160px circle at 20% 10%, rgba(37, 99, 235, 0.14), transparent 70%);
  }

  .brand-header {
    text-align: left;
    display: flex;
    flex-direction: column;
    align-items: flex-start;
    gap: 4px;

    .brand-icon {
      width: 48px;
      height: 48px;
      margin: 0 0 6px;
    }

    h2 {
      font-size: 22px;
      line-height: 1.2;
    }

    .brand-slogan {
      font-size: 13px;
    }
  }

  .brand-body {
    gap: 14px;
    margin-top: 14px;
  }

  .brand-tags {
    gap: 8px;
    justify-content: flex-start;
  }

  .brand-features {
    gap: 10px;

    li {
      font-size: 13px;
    }
  }

  .feature-icon {
    width: 24px;
    height: 24px;
    border-radius: 8px;
    font-size: 11px;
  }

  .brand-note {
    padding: 8px 10px;
    font-size: 12px;
  }

  .form-header {
    margin-bottom: 16px;

    h3 {
      font-size: 20px;
    }
  }

  .form-container {
    margin-bottom: 16px;
  }

  .login-form {
    .el-form-item {
      margin-bottom: 14px;
    }

    .remember-forgot-row {
      margin-top: 12px;
    }

    .login-button {
      height: 44px;
      margin: 14px 0;
    }
  }

}

@media (max-width: 420px) {
  .login-content {
    padding: 10px;
  }

  .login-card {
    border-radius: 16px;
  }

  .brand-header h2 {
    font-size: 20px;
  }

  .form-header h3 {
    font-size: 18px;
  }

  .brand-body {
    gap: 12px;
  }

  .login-form {
    .remember-forgot-row {
      flex-direction: column;
      align-items: stretch;
    }

    .forgot-password-link {
      white-space: normal;
    }
  }
}

@media (prefers-color-scheme: dark) {
  .login-card {
    background: rgba(17, 24, 39, 0.85);
    color: #f8fafc;
  }

  .brand-panel {
    background:
      linear-gradient(145deg, rgba(37, 99, 235, 0.28), rgba(56, 189, 248, 0.18)),
      radial-gradient(180px circle at 20% 15%, rgba(56, 189, 248, 0.2), transparent 70%);
  }

  .form-panel {
    background: rgba(15, 23, 42, 0.8);
    border-left-color: rgba(255, 255, 255, 0.12);
  }

}

@media (prefers-reduced-motion: reduce) {
  .login-card,
  .gradient-blob {
    animation: none !important;
  }
}
</style>
