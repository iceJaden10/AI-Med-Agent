export type TriageLevel = 'emergency' | 'urgent' | 'non_urgent' | 'self_care' | 'unknown';

export type Provider = 'qwen' | 'azure';

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

export interface PatientProfile {
  age?: number;
  gender?: string;
  height_cm?: number;
  weight_kg?: number;
  chronic_diseases?: string[];
  allergies?: string[];
  medications?: string[];
  extra?: Record<string, any>;
}

export interface ConsultRequest {
  user_id: string;
  query: string;
  provider?: Provider;
  patient_profile?: PatientProfile;
  image_base64?: string;
  image_mime_type?: string;
  image_name?: string;
  lang?: 'zh' | 'en';
}

export type ChatRole = 'user' | 'assistant';

export interface ImageAttachment {
  previewUrl: string;
  name?: string;
}

export interface ChatMessage {
  id: string;
  role: ChatRole;
  content: string;
  ts: string;
  meta?: ConsultResponse;
  image?: ImageAttachment;
}