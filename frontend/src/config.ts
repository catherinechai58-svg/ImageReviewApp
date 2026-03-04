// 平台配置 — Cognito 和 API 参数
export const config = {
  // API 基础 URL
  // 本地开发: 空字符串（Vite 代理转发到后端）
  // 生产环境: ALB DNS 地址（如 http://xxx.ap-northeast-1.elb.amazonaws.com）
  apiBaseUrl: import.meta.env.VITE_API_BASE_URL || '',

  // Cognito 配置
  cognito: {
    userPoolId: import.meta.env.VITE_COGNITO_USER_POOL_ID || '',
    clientId: import.meta.env.VITE_COGNITO_CLIENT_ID || '',
    region: import.meta.env.VITE_AWS_REGION || 'ap-northeast-1',
  },
};
