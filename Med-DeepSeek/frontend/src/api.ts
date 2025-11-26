// src/api.ts
import axios from 'axios';
import type { ConsultRequest, ConsultResponse } from './types';

const api = axios.create({
  baseURL: 'http://127.0.0.1:8000', // backend/main.py 跑在这里
});

/**
 * 调用后端问诊接口：
 * - 自动补上 provider，默认使用 Qwen3-max（"qwen"）
 */
export async function consult(req: ConsultRequest): Promise<ConsultResponse> {
  const payload: ConsultRequest = {
    ...req,
    // 如果调用方没传 provider，这里强制补成 "qwen"
    provider: req.provider ?? 'qwen',
  };

  const res = await api.post<ConsultResponse>('/api/consult', payload);
  return res.data;
}

export async function resetSession(user_id: string) {
  const res = await fetch('http://127.0.0.1:8000/api/reset_session', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ user_id }),
  });

  if (!res.ok) {
    throw new Error('reset_session failed');
  }

  return res.json();
}
