/* eslint-env node */
/**
 * ESLint 配置（Vue3 + TypeScript 项目）
 * 与 package.json 中声明的依赖配套：
 * - eslint 8.x（legacy 配置格式）
 * - eslint-plugin-vue 9.x（vue3-essential）
 * - @vue/eslint-config-typescript 12.x（推荐规则集）
 */
module.exports = {
  root: true,
  env: {
    browser: true,
    es2022: true,
    node: true,
  },
  extends: [
    'eslint:recommended',
    'plugin:vue/vue3-essential',
    '@vue/eslint-config-typescript/recommended',
  ],
  parserOptions: {
    ecmaVersion: 'latest',
    sourceType: 'module',
  },
  ignorePatterns: ['dist', 'node_modules', 'coverage', 'pptist', 'tmp'],
  rules: {
    // 存量代码大量使用 any，先不阻断，后续可逐步收紧
    '@typescript-eslint/no-explicit-any': 'off',
    '@typescript-eslint/ban-types': 'off',
    '@typescript-eslint/ban-ts-comment': 'off',
    // 未使用变量 / let→const 等风格问题降为警告
    '@typescript-eslint/no-unused-vars': 'warn',
    'prefer-const': 'warn',
    // 存量单字组件名（Home/Login 等）与历史转义字符，暂不阻断
    'vue/multi-word-component-names': 'off',
    'no-useless-escape': 'off',
    'no-prototype-builtins': 'warn',
    'no-case-declarations': 'warn',
  },
}
