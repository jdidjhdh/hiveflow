import { describe, it, expect } from 'vitest';
import { ApiError, getErrorMessage, handleApiError } from '@/api/client';

describe('api/client errors', () => {
  it('getErrorMessage maps ApiError status codes', () => {
    expect(getErrorMessage(new ApiError('bad', 400))).toContain('请求参数错误');
    expect(getErrorMessage(new ApiError('nope', 404))).toContain('不存在');
    expect(getErrorMessage(new ApiError('down', 503))).toContain('Agent 服务不可用');
    expect(getErrorMessage(new ApiError('offline', 0))).toContain('网络连接失败');
  });

  it('getErrorMessage handles generic Error', () => {
    expect(getErrorMessage(new Error('boom'))).toBe('boom');
    expect(getErrorMessage('x')).toContain('未知错误');
  });

  it('handleApiError parses JSON detail', async () => {
    const response = {
      ok: false,
      status: 422,
      statusText: 'Unprocessable',
      json: async () => ({ detail: 'invalid payload' }),
    } as Response;

    await expect(handleApiError(response)).rejects.toMatchObject({
      status: 422,
      message: 'invalid payload',
    });
  });

  it('handleApiError parses validation error array', async () => {
    const response = {
      ok: false,
      status: 422,
      statusText: 'Unprocessable',
      json: async () => ({ detail: [{ msg: 'field required' }] }),
    } as Response;

    await expect(handleApiError(response)).rejects.toMatchObject({
      message: 'field required',
    });
  });
});
