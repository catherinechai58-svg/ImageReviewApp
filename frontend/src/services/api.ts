import axios from 'axios';
import { config } from '../config';
import { getStoredTokens, refreshSession, clearTokens } from './auth';

// 创建 axios 实例
const api = axios.create({
  baseURL: config.apiBaseUrl,
  timeout: 30000,
  headers: { 'Content-Type': 'application/json' },
});

// 请求拦截器 — 自动附加 Authorization header
api.interceptors.request.use(async (reqConfig) => {
  let tokens = getStoredTokens();

  // 尝试检查 token 是否快过期（5 分钟内），提前刷新
  if (tokens) {
    try {
      const payload = JSON.parse(atob(tokens.idToken.split('.')[1]));
      const expiresIn = payload.exp * 1000 - Date.now();
      if (expiresIn < 5 * 60 * 1000) {
        const refreshed = await refreshSession();
        if (refreshed) tokens = refreshed;
      }
    } catch {
      // 解析失败，继续使用现有 token
    }
  }

  if (tokens) {
    reqConfig.headers.Authorization = `Bearer ${tokens.idToken}`;
  }
  return reqConfig;
});

// 响应拦截器 — 401 时清除 token 并跳转登录页
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      clearTokens();
      // 跳转到登录页（避免在登录页循环）
      if (window.location.pathname !== '/login') {
        window.location.href = '/login';
      }
    }
    return Promise.reject(error);
  },
);

export default api;
