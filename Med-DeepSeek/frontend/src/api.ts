import axios from 'axios';
import type { ConsultRequest, ConsultResponse } from './types';

const api = axios.create({
  baseURL: 'http://127.0.0.1:8000', // backend/main.py 跑在这里
});

export async function consult(req: ConsultRequest): Promise<ConsultResponse> {
  const res = await api.post<ConsultResponse>('/api/consult', req);
  return res.data;
}
