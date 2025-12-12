// src/i18n.ts

export type Lang = 'zh' | 'en';

export const I18N = {
  zh: {
    appTitle: '智能医疗问诊助手',
    appSubtitle: '不能替代医院，仅供健康信息参考',

    riskEmpty: '当前暂无风险评估。发送一条症状描述后，这里会显示系统给出的就诊紧急程度。',
    riskLevel: '当前风险等级：',
    summary: '系统摘要：',

    chatHint:
      '请尽量详细描述你的症状、持续时间、伴随情况等。系统不会记录身份证号等敏感信息。',

    greeting:
      '你好，我是你的智能医疗问诊助手。我会根据你描述的症状，给出初步的风险评估和就医建议，但不能替代医院面诊和正规医疗服务。请用中文详细描述你的不适、持续时间和伴随症状。',

    placeholder: '请描述你的症状，例如：这两天一直咳嗽，还有点低烧……',

    upload: '上传图片',
    newChat: '新开聊天',
    send: '发送',
    replace: '替换',
    remove: '移除',

    uploadOnlyImage: '仅支持上传图片文件',
    uploadTooLarge: '图片过大，请压缩到 8MB 以内',
    uploadReadFail: '读取图片失败，请重试',

    systemBusy: '抱歉，系统开小差了，请稍后再试一次或检查网络连接。',

    diagnosisEmpty: '这里会展示「可能诊断」及对应的概率，仅供参考，不能替代医生面诊。',
    diagnosisTitle: '可能诊断（仅供参考）：',
    suggestionsTitle: '系统建议：',

    redFlagTitle: '⚠️ 强提醒（红旗信号）',

    followUpTitle: '继续问诊',
    followUpHint: '点击下方问题快速提问',

    doctorWantsMore: '医生想进一步了解：',

    imageOnlyQuery: '请结合我上传的图片进行分析，并给出安全的问诊建议。',

    followUps: [
      '如果我去医院的话，应该挂哪个科室？',
      '目前这种情况有没有比较合适的药物或处理方式？',
      '有哪些情况说明病情在加重，需要立刻去医院或急诊？',
      '在家休息期间，我需要特别注意些什么？',
    ],

    triage: {
      self_care: '可居家观察',
      non_urgent: '需要门诊就诊',
      urgent: '尽快就医',
      emergency: '紧急（建议急诊）',
    } as Record<string, string>,
  },

  en: {
    appTitle: 'AI Medical Triage Assistant',
    appSubtitle: 'Not a substitute for medical care. For health information only.',

    riskEmpty:
      'No triage result yet. Send a symptom description and the urgency level will appear here.',
    riskLevel: 'Triage level:',
    summary: 'Summary:',

    chatHint:
      'Please describe your symptoms, duration, and associated signs in detail. We do not store sensitive ID information.',

    greeting:
      "Hi, I’m your AI medical triage assistant. Based on your symptoms, I can provide a preliminary risk assessment and care suggestions, but this does not replace in-person medical evaluation. Please describe what you feel, how long it has lasted, and any accompanying symptoms.",

    placeholder: 'Describe your symptoms, e.g., cough for 2 days with mild fever…',

    upload: 'Upload image',
    newChat: 'New chat',
    send: 'Send',
    replace: 'Replace',
    remove: 'Remove',

    uploadOnlyImage: 'Only image files are supported',
    uploadTooLarge: 'Image too large. Please compress to under 8MB',
    uploadReadFail: 'Failed to read image. Please try again',

    systemBusy: 'Sorry—something went wrong. Please try again later or check your network.',

    diagnosisEmpty:
      'Possible diagnoses and probabilities will be shown here for reference only. Not a medical diagnosis.',
    diagnosisTitle: 'Possible diagnoses (for reference):',
    suggestionsTitle: 'Suggestions:',

    redFlagTitle: '⚠️ Red flags',

    followUpTitle: 'Follow-up',
    followUpHint: 'Click a question to ask quickly',

    doctorWantsMore: 'To clarify, I want to know:',

    imageOnlyQuery:
      'Please analyze my uploaded image and provide safe triage-oriented suggestions.',

    followUps: [
      'Which department should I visit if I go to a hospital?',
      'Are there any suitable medications or home care steps for now?',
      'What signs indicate worsening and require urgent care or ER?',
      'What should I pay attention to while resting at home?',
    ],

    triage: {
      self_care: 'Self-care / monitor',
      non_urgent: 'Clinic visit needed',
      urgent: 'See a doctor soon',
      emergency: 'Emergency (go to ER)',
    } as Record<string, string>,
  },
} as const;
