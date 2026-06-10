/**
 * API 请求工具
 */

// 统一后端 baseURL，可通过环境变量覆盖
export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000';

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
    message = data.detail || data.message || message;
    details = data.details;
  } catch {
    message = `HTTP ${response.status}: ${response.statusText}`;
  }

  throw new ApiError(message, response.status, details);
}

/**
 * 统一的 API 请求方法，自动添加 baseURL 和 Content-Type
 */
export async function apiFetch(url: string, options?: RequestInit) {
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

    return await response.json();
  } catch (error) {
    if (error instanceof ApiError) {
      throw error;
    }
    // 网络错误
    throw new ApiError('网络连接失败', 0, String(error));
  }
}

// 友好的错误消息映射
export function getErrorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    switch (error.status) {
      case 400: return `请求参数错误: ${error.message}`;
      case 401: return '未授权，请重新登录';
      case 403: return '权限不足';
      case 404: return '请求的资源不存在';
      case 500: return '服务器内部错误，请稍后重试';
      case 0: return '网络连接失败，请检查网络';
      default: return `请求失败 (${error.status}): ${error.message}`;
    }
  }
  if (error instanceof Error) {
    return error.message;
  }
  return '发生了未知错误';
}
