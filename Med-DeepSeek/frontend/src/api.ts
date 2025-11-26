import axios from 'axios';
import type { ConsultRequest, ConsultResponse } from './types';

const api = axios.create({
  baseURL: 'http://127.0.0.1:8000', // backend/main.py 跑在这里
});

export async function consult(req: ConsultRequest): Promise<ConsultResponse> {
  const res = await api.post<ConsultResponse>('/api/consult', req);
  return res.data;
}

export async function resetSession(user_id: string) {
  const res = await fetch("http://127.0.0.1:8000/api/reset_session", {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify({ user_id })
  });

  if (!res.ok) {
    throw new Error("reset_session failed");
  }

  return res.json();
}