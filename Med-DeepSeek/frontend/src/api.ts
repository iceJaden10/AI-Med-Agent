// src/api.ts
import axios from 'axios';
import type { ConsultRequest, ConsultResponse } from './types';

const api = axios.create({
  baseURL: '/api', // ✅ 生产环境走 nginx 反代
});

/**
 * 调用后端问诊接口
 */
export async function consult(req: ConsultRequest): Promise<ConsultResponse> {
  const payload: ConsultRequest = {
    ...req,
    provider: req.provider ?? 'qwen',
  };

  const res = await api.post<ConsultResponse>('/consult', payload); // ✅ /api/consult
  return res.data;
}

export async function resetSession(user_id: string) {
  const res = await fetch('/api/reset_session', {  // ✅ /api/reset_session
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ user_id }),
  });

  if (!res.ok) throw new Error('reset_session failed');
  return res.json();
}
