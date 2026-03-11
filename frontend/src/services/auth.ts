import axios from 'axios';
import { config } from '../config';

const authApi = axios.create({
  baseURL: config.apiBaseUrl,
  timeout: 30000,
  headers: { 'Content-Type': 'application/json' },
});

const TOKEN_KEY = 'auth_tokens';

export interface AuthTokens {
  idToken: string;
  accessToken: string;
  refreshToken: string;
}

export interface ChallengeResult {
  challenge: string;
  session: string;
  username: string;
}

function saveTokens(data: any): AuthTokens {
  const tokens: AuthTokens = {
    idToken: data.id_token,
    accessToken: data.access_token,
    refreshToken: data.refresh_token,
  };
  localStorage.setItem(TOKEN_KEY, JSON.stringify(tokens));
  return tokens;
}

export function getStoredTokens(): AuthTokens | null {
  const raw = localStorage.getItem(TOKEN_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as AuthTokens;
  } catch {
    return null;
  }
}

export function clearTokens(): void {
  localStorage.removeItem(TOKEN_KEY);
}

/**
 * 登录 — 返回 tokens 或 challenge 信息
 */
export async function login(username: string, password: string): Promise<AuthTokens | ChallengeResult> {
  const res = await authApi.post('/auth/login', { username, password });
  const data = res.data.data;

  if (data.challenge === 'NEW_PASSWORD_REQUIRED') {
    return { challenge: data.challenge, session: data.session, username: data.username };
  }

  return saveTokens(data);
}

/**
 * 首次登录强制修改密码
 */
export async function forceChangePassword(username: string, newPassword: string, session: string): Promise<AuthTokens> {
  const res = await authApi.post('/auth/force-change-password', {
    username,
    new_password: newPassword,
    session,
  });
  return saveTokens(res.data.data);
}

export function isAuthenticated(): boolean {
  const tokens = getStoredTokens();
  if (!tokens) return false;
  try {
    const payload = JSON.parse(atob(tokens.idToken.split('.')[1]));
    return payload.exp * 1000 > Date.now();
  } catch {
    return false;
  }
}

export function getCurrentUsername(): string {
  const tokens = getStoredTokens();
  if (!tokens) return '';
  try {
    const payload = JSON.parse(atob(tokens.idToken.split('.')[1]));
    return payload['cognito:username'] || payload['username'] || '';
  } catch {
    return '';
  }
}

export function logout(): void {
  clearTokens();
}

// Stub for compatibility — refresh not implemented via backend yet
export async function refreshSession(): Promise<AuthTokens | null> {
  const tokens = getStoredTokens();
  if (!tokens) return null;
  if (isAuthenticated()) return tokens;
  clearTokens();
  return null;
}
