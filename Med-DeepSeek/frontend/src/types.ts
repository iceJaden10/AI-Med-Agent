export type TriageLevel = 'emergency' | 'urgent' | 'non_urgent' | 'self_care' | 'unknown';

export interface PossibleDiagnosis {
  name: string;
  probability: number;
}

export interface ConsultResponse {
  answer: string;
  triage_level: TriageLevel;
  possible_diagnoses: PossibleDiagnosis[];
  suggestions: string[];
  red_flags: string[];
  follow_up_questions: string[];
  context_summary?: string;
  disclaimer: string;
}

export interface ConsultRequest {
  user_id: string;
  query: string;
  patient_profile?: {
    age?: number;
    gender?: string;
    chronic_diseases?: string[];
    allergies?: string[];
    medications?: string[];
    extra?: Record<string, any>;
  };
}

export type ChatRole = 'user' | 'assistant';

export interface ChatMessage {
  id: string;
  role: ChatRole;
  content: string;
  ts: string;
  meta?: ConsultResponse; // 只有 assistant 消息会带
}
