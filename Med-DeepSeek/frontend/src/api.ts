import axios from 'axios';
import type { ConsultRequest, ConsultResponse, PatientProfile } from './types';

const api = axios.create({
  baseURL: '/api',
});

export async function consult(req: ConsultRequest): Promise<ConsultResponse> {
  const payload: ConsultRequest = {
    ...req,
    provider: req.provider ?? 'qwen',
  };

  const res = await api.post<ConsultResponse>('/consult', payload);
  return res.data;
}

export async function resetSession(user_id: string) {
  const res = await fetch('/api/reset_session', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ user_id }),
  });

  if (!res.ok) throw new Error('reset_session failed');
  return res.json();
}

export async function getProfile(user_id: string): Promise<PatientProfile | null> {
  const res = await api.get<{ user_id: string; profile: PatientProfile | null }>('/profile', {
    params: { user_id },
  });
  return res.data.profile ?? null;
}

export async function saveProfile(user_id: string, profile: PatientProfile): Promise<PatientProfile> {
  const res = await api.post<{ status: string; user_id: string; profile: PatientProfile }>('/profile', {
    user_id,
    profile,
  });
  return res.data.profile;
}