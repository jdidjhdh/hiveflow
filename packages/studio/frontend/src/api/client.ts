/**
 * Unified HTTP client for HiveFlow Studio backend.
 */

function resolveApiBaseUrl(): string {
  const envUrl = import.meta.env.VITE_API_BASE_URL;
  if (typeof envUrl === 'string' && envUrl.length > 0) {
    return envUrl;
  }
  if (import.meta.env.DEV) {
    return '';
  }
  if (typeof window !== 'undefined' && window.location?.origin) {
    return window.location.origin;
  }
  return 'http://127.0.0.1:8000';
}

/** Base URL for API requests (empty string = same origin in dev). */
export const API_BASE_URL = resolveApiBaseUrl();

/** Public base URL for webhooks / copy-paste links shown in UI. */
export function getPublicApiBaseUrl(): string {
  const envUrl = import.meta.env.VITE_API_BASE_URL;
  if (typeof envUrl === 'string' && envUrl.length > 0) {
    return envUrl;
  }
  if (typeof window !== 'undefined' && window.location?.origin) {
    return window.location.origin;
  }
  return 'http://127.0.0.1:8000';
}

export class ApiError extends Error {
  public status: number;
  public details?: string;

  constructor(message: string, status: number, details?: string) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.details = details;
  }
}

export async function handleApiError(response: Response): Promise<never> {
  let message = '请求失败';
  let details;

  try {
    const data = await response.json();
    if (typeof data === 'object' && data !== null) {
      const body = data as Record<string, unknown>;
      if (typeof body.error === 'string') {
        message = body.error;
      } else if (typeof body.detail === 'string') {
        message = body.detail;
      } else if (Array.isArray(body.detail)) {
        message = body.detail
          .map((item) => (typeof item === 'object' && item && 'msg' in item ? String((item as { msg: unknown }).msg) : String(item)))
          .join('; ');
      } else if (typeof body.message === 'string') {
        message = body.message;
      }
      if (typeof body.details === 'string') {
        details = body.details;
      }
    }
  } catch {
    message = `HTTP ${response.status}: ${response.statusText}`;
  }

  throw new ApiError(message, response.status, details);
}

export async function apiFetch<T = any>(url: string, options?: RequestInit): Promise<T> {
  const fullUrl = url.startsWith('http') ? url : `${API_BASE_URL}${url}`;
  try {
    const response = await fetch(fullUrl, {
      headers: {
        'Content-Type': 'application/json',
        ...options?.headers,
      },
      ...options,
    });

    if (!response.ok) {
      await handleApiError(response);
    }

    const text = await response.text();
    if (!text.trim()) {
      return null as T;
    }
    try {
      return JSON.parse(text) as T;
    } catch {
      throw new ApiError('响应不是有效 JSON', response.status);
    }
  } catch (error) {
    if (error instanceof ApiError) {
      throw error;
    }
    throw new ApiError('网络连接失败', 0, String(error));
  }
}

export function getErrorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    switch (error.status) {
      case 400: return `请求参数错误: ${error.message}`;
      case 401: return '未授权，请重新登录';
      case 403: return '权限不足';
      case 404: return '请求的资源不存在';
      case 500: return '服务器内部错误，请稍后重试';
      case 503: return `Agent 服务不可用: ${error.message}`;
      case 0: return '网络连接失败，请检查网络';
      default: return `请求失败 (${error.status}): ${error.message}`;
    }
  }
  if (error instanceof Error) {
    return error.message;
  }
  return '发生了未知错误';
}
