import type { TriageLevel } from './types';

export function triageLabel(level: TriageLevel): string {
  switch (level) {
    case 'emergency':
      return '紧急（急诊风险）';
    case 'urgent':
      return '较紧急（尽快就诊）';
    case 'non_urgent':
      return '一般（可择期就诊）';
    case 'self_care':
      return '自我管理为主';
    default:
      return '风险未知';
  }
}

export function triageColor(level: TriageLevel): string {
  switch (level) {
    case 'emergency':
      return 'bg-red-100 text-red-700 border-red-400';
    case 'urgent':
      return 'bg-orange-100 text-orange-700 border-orange-400';
    case 'non_urgent':
      return 'bg-green-100 text-green-700 border-green-400';
    case 'self_care':
      return 'bg-blue-100 text-blue-700 border-blue-400';
    default:
      return 'bg-gray-100 text-gray-700 border-gray-400';
  }
}
