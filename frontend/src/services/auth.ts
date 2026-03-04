import {
  CognitoUserPool,
  CognitoUser,
  AuthenticationDetails,
  CognitoUserSession,
} from 'amazon-cognito-identity-js';
import { config } from '../config';

// Cognito 用户池实例（配置无效时为 null）
let userPool: CognitoUserPool | null = null;
try {
  if (config.cognito.userPoolId && config.cognito.clientId
      && !config.cognito.userPoolId.includes('XXXXX')) {
    userPool = new CognitoUserPool({
      UserPoolId: config.cognito.userPoolId,
      ClientId: config.cognito.clientId,
    });
  }
} catch {
  // 配置无效，userPool 保持 null
}

// token 存储 key
const TOKEN_KEY = 'auth_tokens';

export interface AuthTokens {
  idToken: string;
  accessToken: string;
  refreshToken: string;
}

// 保存 token 到 localStorage
function saveTokens(session: CognitoUserSession): AuthTokens {
  const tokens: AuthTokens = {
    idToken: session.getIdToken().getJwtToken(),
    accessToken: session.getAccessToken().getJwtToken(),
    refreshToken: session.getRefreshToken().getToken(),
  };
  localStorage.setItem(TOKEN_KEY, JSON.stringify(tokens));
  return tokens;
}

// 获取已存储的 token
export function getStoredTokens(): AuthTokens | null {
  const raw = localStorage.getItem(TOKEN_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as AuthTokens;
  } catch {
    return null;
  }
}

// 清除 token
export function clearTokens(): void {
  localStorage.removeItem(TOKEN_KEY);
}

// 登录
export function login(username: string, password: string): Promise<AuthTokens> {
  return new Promise((resolve, reject) => {
    if (!userPool) {
      reject(new Error('Cognito 未配置，请检查环境变量'));
      return;
    }
    const user = new CognitoUser({ Username: username, Pool: userPool });
    const authDetails = new AuthenticationDetails({ Username: username, Password: password });

    user.authenticateUser(authDetails, {
      onSuccess: (session) => {
        resolve(saveTokens(session));
      },
      onFailure: (err) => {
        reject(new Error(err.message || '登录失败'));
      },
      // 首次登录需要修改密码的场景
      newPasswordRequired: () => {
        reject(new Error('NEW_PASSWORD_REQUIRED'));
      },
    });
  });
}

// 刷新 token
export function refreshSession(): Promise<AuthTokens | null> {
  return new Promise((resolve) => {
    if (!userPool) {
      resolve(null);
      return;
    }
    const currentUser = userPool.getCurrentUser();
    if (!currentUser) {
      resolve(null);
      return;
    }
    currentUser.getSession((err: Error | null, session: CognitoUserSession | null) => {
      if (err || !session || !session.isValid()) {
        clearTokens();
        resolve(null);
        return;
      }
      resolve(saveTokens(session));
    });
  });
}

// 检查当前是否已认证（token 有效）
export function isAuthenticated(): boolean {
  const tokens = getStoredTokens();
  if (!tokens) return false;
  // 简单检查 token 是否过期（解析 JWT payload）
  try {
    const payload = JSON.parse(atob(tokens.idToken.split('.')[1]));
    return payload.exp * 1000 > Date.now();
  } catch {
    return false;
  }
}

// 登出
export function logout(): void {
  if (userPool) {
    const currentUser = userPool.getCurrentUser();
    if (currentUser) {
      currentUser.signOut();
    }
  }
  clearTokens();
}
