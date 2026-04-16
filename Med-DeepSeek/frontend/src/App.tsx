import { useEffect, useRef, useState } from 'react';
import type { ChangeEvent } from 'react';
import { v4 as uuidv4 } from 'uuid';

import { consult, getProfile, resetSession, saveProfile } from './api';
import type { ChatMessage, ConsultResponse, PatientProfile } from './types';
import { triageColor } from './triage';
import { I18N, type Lang } from './i18n';

function safeGetLang(): Lang {
  try {
    const saved = localStorage.getItem('lang');
    return saved === 'en' || saved === 'zh' ? saved : 'zh';
  } catch {
    return 'zh';
  }
}

function safeSetLang(lang: Lang) {
  try {
    localStorage.setItem('lang', lang);
  } catch {
    // ignore
  }
}

function safeGetUserId(): string {
  try {
    const saved = localStorage.getItem('med_user_id');
    if (saved) return saved;
    const id = uuidv4();
    localStorage.setItem('med_user_id', id);
    return id;
  } catch {
    return uuidv4();
  }
}

function splitToList(input: string): string[] {
  return input
    .split(/[，,、；;]/)
    .map(s => s.trim())
    .filter(Boolean);
}

function joinList(list?: string[]): string {
  return (list ?? []).join(', ');
}

const PROFILE_MODAL_CLOSE_MS = 200;

export default function App() {
  const [userId] = useState(() => safeGetUserId());

  const [lang, setLang] = useState<Lang>(() => safeGetLang());
  const t = I18N[lang];

  useEffect(() => {
    safeSetLang(lang);
  }, [lang]);

  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);

  const [pendingImage, setPendingImage] = useState<{ file: File; dataUrl: string } | null>(null);
  const [uploadError, setUploadError] = useState('');
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const profileCloseTimerRef = useRef<number | null>(null);

  const [profileOpen, setProfileOpen] = useState(false);
  const [profileClosing, setProfileClosing] = useState(false);
  const [profileLoading, setProfileLoading] = useState(false);
  const [profileSaving, setProfileSaving] = useState(false);
  const [patientProfile, setPatientProfile] = useState<PatientProfile>({});
  const [profileForm, setProfileForm] = useState({
    age: '',
    gender: '',
    height_cm: '',
    weight_kg: '',
    chronic_diseases: '',
    allergies: '',
  });

  const MAX_IMAGE_SIZE = 8 * 1024 * 1024;

  const lastAssistantMessage = [...messages].reverse().find(m => m.role === 'assistant' && !!m.meta);
  const lastMeta: ConsultResponse | undefined = lastAssistantMessage?.meta;

  function triageLabelLocalized(level: any) {
    const key = String(level ?? '');
    return t.triage?.[key] ?? key;
  }

  function syncFormFromProfile(profile: PatientProfile | null) {
    const p = profile ?? {};
    setPatientProfile(p);
    setProfileForm({
      age: p.age != null ? String(p.age) : '',
      gender: p.gender ?? '',
      height_cm: p.height_cm != null ? String(p.height_cm) : '',
      weight_kg: p.weight_kg != null ? String(p.weight_kg) : '',
      chronic_diseases: joinList(p.chronic_diseases),
      allergies: joinList(p.allergies),
    });
  }

  useEffect(() => {
    const greetingMsg: ChatMessage = {
      id: uuidv4(),
      role: 'assistant',
      content: t.greeting,
      ts: new Date().toISOString(),
    };
    setMessages([greetingMsg]);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [userId]);

  useEffect(() => {
    setMessages(prev => {
      if (!prev.length) return prev;
      if (prev[0].role !== 'assistant') return prev;
      return [{ ...prev[0], content: t.greeting }, ...prev.slice(1)];
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [lang]);

  useEffect(() => {
    let cancelled = false;

    async function loadProfile() {
      setProfileLoading(true);
      try {
        const profile = await getProfile(userId);
        if (!cancelled) syncFormFromProfile(profile);
      } catch (err) {
        console.error(err);
        if (!cancelled) syncFormFromProfile(null);
      } finally {
        if (!cancelled) setProfileLoading(false);
      }
    }

    loadProfile();
    return () => {
      cancelled = true;
    };
  }, [userId]);

  useEffect(() => {
    return () => {
      if (profileCloseTimerRef.current != null) {
        window.clearTimeout(profileCloseTimerRef.current);
      }
    };
  }, []);

  function openProfileModal() {
    if (profileCloseTimerRef.current != null) {
      window.clearTimeout(profileCloseTimerRef.current);
      profileCloseTimerRef.current = null;
    }
    setProfileClosing(false);
    setProfileOpen(true);
  }

  function closeProfileModal() {
    if (!profileOpen) return;
    if (profileCloseTimerRef.current != null) {
      window.clearTimeout(profileCloseTimerRef.current);
    }

    setProfileClosing(true);
    profileCloseTimerRef.current = window.setTimeout(() => {
      setProfileOpen(false);
      setProfileClosing(false);
      profileCloseTimerRef.current = null;
    }, PROFILE_MODAL_CLOSE_MS);
  }

  async function handleNewChat() {
    const greetingMsg: ChatMessage = {
      id: uuidv4(),
      role: 'assistant',
      content: t.greeting,
      ts: new Date().toISOString(),
    };
    setMessages([greetingMsg]);
    setInput('');
    setLoading(false);
    setPendingImage(null);
    setUploadError('');

    try {
      await resetSession(userId);
    } catch (err) {
      console.error(err);
    }
  }

  async function handleSend(customText?: string) {
    const text = (customText ?? input).trim();
    if ((!text && !pendingImage) || loading) return;

    const ts = new Date().toISOString();

    const base64Image = pendingImage ? pendingImage.dataUrl.split(',')[1] : undefined;
    const mime = pendingImage?.file.type;
    const name = pendingImage?.file.name;

    const queryText = text || t.imageOnlyQuery;

    const userMsg: ChatMessage = {
      id: uuidv4(),
      role: 'user',
      content: queryText,
      ts,
      image: pendingImage ? { previewUrl: pendingImage.dataUrl, name } : undefined,
    };

    setMessages(prev => [...prev, userMsg]);
    setInput('');
    setPendingImage(null);
    setUploadError('');
    setLoading(true);

    try {
      const res = await consult({
        user_id: userId,
        query: queryText,
        provider: 'qwen',
        lang,
        patient_profile: patientProfile,
        image_base64: base64Image,
        image_mime_type: mime,
        image_name: name,
      });

      const assistantMsg: ChatMessage = {
        id: uuidv4(),
        role: 'assistant',
        content: res.answer,
        ts: new Date().toISOString(),
        meta: res,
      };

      setMessages(prev => [...prev, assistantMsg]);
    } catch (err) {
      console.error(err);
      const errMsg: ChatMessage = {
        id: uuidv4(),
        role: 'assistant',
        content: t.systemBusy,
        ts: new Date().toISOString(),
      };
      setMessages(prev => [...prev, errMsg]);
    } finally {
      setLoading(false);
    }
  }

  async function handleSaveProfile() {
    const payload: PatientProfile = {
      age: profileForm.age.trim() ? Number(profileForm.age) : undefined,
      gender: profileForm.gender.trim() || undefined,
      height_cm: profileForm.height_cm.trim() ? Number(profileForm.height_cm) : undefined,
      weight_kg: profileForm.weight_kg.trim() ? Number(profileForm.weight_kg) : undefined,
      chronic_diseases: splitToList(profileForm.chronic_diseases),
      allergies: splitToList(profileForm.allergies),
    };

    if (
      payload.age != null &&
      (!Number.isInteger(payload.age) || payload.age <= 0)
    ) {
      alert(t.profileSaveFailed);
      return;
    }

    if (payload.height_cm != null && Number.isNaN(payload.height_cm)) {
      alert(t.profileSaveFailed);
      return;
    }

    if (payload.weight_kg != null && Number.isNaN(payload.weight_kg)) {
      alert(t.profileSaveFailed);
      return;
    }

    setProfileSaving(true);
    try {
      const saved = await saveProfile(userId, payload);
      setPatientProfile(saved);
      syncFormFromProfile(saved);
      closeProfileModal();
    } catch (err) {
      console.error(err);
      alert(t.profileSaveFailed);
    } finally {
      setProfileSaving(false);
    }
  }

  async function handleImageChange(e: ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    e.target.value = '';
    setUploadError('');

    if (!file.type.startsWith('image/')) {
      setUploadError(t.uploadOnlyImage);
      return;
    }
    if (file.size > MAX_IMAGE_SIZE) {
      setUploadError(t.uploadTooLarge);
      return;
    }

    const reader = new FileReader();
    reader.onloadend = () => {
      const result = reader.result;
      if (typeof result === 'string') setPendingImage({ file, dataUrl: result });
      else setUploadError(t.uploadReadFail);
    };
    reader.onerror = () => setUploadError(t.uploadReadFail);
    reader.readAsDataURL(file);
  }

  function clearPendingImage() {
    setPendingImage(null);
    setUploadError('');
  }

  const hasContent = input.trim().length > 0 || !!pendingImage;

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col items-center">
      <header className="w-full max-w-6xl px-4 pt-4 pb-2 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-full bg-emerald-500 flex items-center justify-center text-white font-bold">
            医
          </div>
          <div>
            <div className="text-base font-semibold">{t.appTitle}</div>
            <div className="text-xs text-slate-500">{t.appSubtitle}</div>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={openProfileModal}
            className="text-xs px-3 py-2 rounded-lg border border-slate-300 text-slate-700 bg-white hover:bg-slate-100"
          >
            {t.myInfo}
          </button>

          <button
            type="button"
            onClick={() => setLang(prev => (prev === 'zh' ? 'en' : 'zh'))}
            className="text-xs px-3 py-2 rounded-lg border border-slate-300 text-slate-700 bg-white hover:bg-slate-100"
          >
            {lang === 'zh' ? 'EN' : '中文'}
          </button>
        </div>
      </header>

      <main className="w-full max-w-6xl px-4 pb-4 flex flex-col gap-3 flex-1">
        <RiskPanel meta={lastMeta} t={t} triageLabelLocalized={triageLabelLocalized} />

        <div className="grid grid-cols-1 md:grid-cols-12 gap-3 md:gap-4 flex-1 items-stretch">
          <section className="md:col-span-9 bg-white rounded-xl shadow-sm border border-slate-200 flex flex-col flex-1 min-h-0">
            <div className="px-4 py-3 border-b border-slate-100 text-sm text-slate-500">{t.chatHint}</div>

            <div className="flex-1 min-h-0 overflow-y-auto px-4 pt-3 space-y-3">
              {messages.map(msg => (
                <ChatBubble key={msg.id} msg={msg} doctorWantsMore={t.doctorWantsMore} />
              ))}
            </div>

            <div className="border-t border-slate-100 px-3 py-3">
              <div className="flex flex-col gap-2">
                <div
                  className="
                    relative w-full rounded-2xl border border-slate-200 bg-white
                    px-4 pt-3 pb-14
                    focus-within:ring-2 focus-within:ring-emerald-400 focus-within:border-emerald-400
                  "
                >
                  {pendingImage && (
                    <div className="mb-3">
                      <div className="relative inline-block">
                        <img
                          src={pendingImage.dataUrl}
                          alt="preview"
                          className="w-20 h-20 rounded-xl object-cover border border-slate-200"
                        />
                        <div className="absolute top-2 right-2 flex gap-2">
                          <button
                            type="button"
                            onClick={() => fileInputRef.current?.click()}
                            className="w-8 h-8 rounded-full bg-black/80 text-white flex items-center justify-center hover:bg-black"
                            disabled={loading}
                            title={t.replace}
                          >
                            ✎
                          </button>
                          <button
                            type="button"
                            onClick={clearPendingImage}
                            className="w-8 h-8 rounded-full bg-black/80 text-white flex items-center justify-center hover:bg-black"
                            disabled={loading}
                            title={t.remove}
                          >
                            ×
                          </button>
                        </div>

                        <div className="mt-2 text-[11px] text-slate-500 max-w-[160px] truncate">
                          {pendingImage.file.name}
                        </div>
                      </div>
                    </div>
                  )}

                  <textarea
                    className="w-full resize-none bg-transparent outline-none text-sm leading-relaxed min-h-[72px]"
                    placeholder={t.placeholder}
                    value={input}
                    onChange={e => setInput(e.target.value)}
                    onKeyDown={e => {
                      if (e.key === 'Enter' && !e.shiftKey) {
                        e.preventDefault();
                        handleSend();
                      }
                    }}
                    disabled={loading}
                  />

                  <input
                    ref={fileInputRef}
                    type="file"
                    accept="image/*"
                    className="hidden"
                    onChange={handleImageChange}
                    disabled={loading}
                  />

                  <div className="absolute bottom-2 left-2 flex items-center gap-2">
                    <button
                      type="button"
                      onClick={() => fileInputRef.current?.click()}
                      className="w-10 h-10 rounded-full border border-slate-300 text-slate-700 bg-white flex items-center justify-center text-xl hover:bg-slate-100 disabled:opacity-50"
                      disabled={loading}
                      title={t.upload}
                    >
                      +
                    </button>

                    <button
                      onClick={handleNewChat}
                      className="text-xs px-3 py-2 rounded-lg border border-slate-300 text-slate-700 bg-white hover:bg-slate-100 whitespace-nowrap"
                      disabled={loading}
                    >
                      {t.newChat}
                    </button>
                  </div>

                  <button
                    className={`absolute bottom-2 right-2 w-11 h-11 rounded-full flex items-center justify-center text-lg font-bold
                      ${loading || !hasContent ? 'bg-slate-300 text-white cursor-not-allowed' : 'bg-black text-white hover:bg-slate-900'}`}
                    onClick={() => handleSend()}
                    disabled={loading || !hasContent}
                    title={t.send}
                  >
                    ↑
                  </button>
                </div>

                {uploadError && !pendingImage && (
                  <div className="text-[11px] text-red-500 px-1">{uploadError}</div>
                )}
              </div>
            </div>
          </section>

          <section className="md:col-span-3 flex flex-col gap-3">
            <DiagnosisPanel meta={lastMeta} t={t} />
            <RedFlagsPanel meta={lastMeta} t={t} />
            <FollowUpPanel meta={lastMeta} t={t} onFollowUpClick={q => handleSend(q)} />
          </section>
        </div>
      </main>

      {profileOpen && (
        <ProfileModal
          closing={profileClosing}
          t={t}
          loading={profileLoading}
          saving={profileSaving}
          form={profileForm}
          onClose={closeProfileModal}
          onSave={handleSaveProfile}
          onChange={patch => setProfileForm(prev => ({ ...prev, ...patch }))}
        />
      )}
    </div>
  );
}

function ProfileModal({
  closing,
  t,
  loading,
  saving,
  form,
  onClose,
  onSave,
  onChange,
}: {
  closing: boolean;
  t: any;
  loading: boolean;
  saving: boolean;
  form: {
    age: string;
    gender: string;
    height_cm: string;
    weight_kg: string;
    chronic_diseases: string;
    allergies: string;
  };
  onClose: () => void;
  onSave: () => void;
  onChange: (patch: Partial<{
    age: string;
    gender: string;
    height_cm: string;
    weight_kg: string;
    chronic_diseases: string;
    allergies: string;
  }>) => void;
}) {
  return (
    <div
      className={`fixed inset-0 z-50 flex items-center justify-center px-4 transition-opacity duration-200 ${
        closing ? 'bg-black/0 opacity-0' : 'bg-black/35 opacity-100'
      }`}
    >
      <div
        className={`w-full max-w-lg overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-xl transition-all duration-200 ${
          closing ? 'translate-y-2 scale-95 opacity-0' : 'translate-y-0 scale-100 opacity-100'
        }`}
      >
        <div className="px-5 py-4 border-b border-slate-100 flex items-center justify-between">
          <div>
            <div className="text-base font-semibold text-slate-800">{t.profileTitle}</div>
            <div className="text-xs text-slate-500 mt-1">{t.profileHint}</div>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="text-slate-400 hover:text-slate-700 text-xl leading-none"
          >
            ×
          </button>
        </div>

        <div className="px-5 py-4 space-y-4">
          {loading ? (
            <div className="text-sm text-slate-500">{t.loadingProfile}</div>
          ) : (
            <>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-1">{t.age}</label>
                  <input
                    type="number"
                    min="1"
                    step="1"
                    value={form.age}
                    onChange={e => onChange({ age: e.target.value })}
                    placeholder={t.agePlaceholder}
                    className="w-full rounded-xl border border-slate-300 px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-emerald-400 focus:border-emerald-400"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-1">{t.gender}</label>
                  <input
                    type="text"
                    value={form.gender}
                    onChange={e => onChange({ gender: e.target.value })}
                    placeholder={t.genderPlaceholder}
                    className="w-full rounded-xl border border-slate-300 px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-emerald-400 focus:border-emerald-400"
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-1">{t.height}</label>
                  <input
                    type="number"
                    value={form.height_cm}
                    onChange={e => onChange({ height_cm: e.target.value })}
                    className="w-full rounded-xl border border-slate-300 px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-emerald-400 focus:border-emerald-400"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-1">{t.weight}</label>
                  <input
                    type="number"
                    value={form.weight_kg}
                    onChange={e => onChange({ weight_kg: e.target.value })}
                    className="w-full rounded-xl border border-slate-300 px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-emerald-400 focus:border-emerald-400"
                  />
                </div>
              </div>

              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">{t.chronicDiseases}</label>
                <textarea
                  value={form.chronic_diseases}
                  onChange={e => onChange({ chronic_diseases: e.target.value })}
                  placeholder={t.chronicDiseasesPlaceholder}
                  className="w-full min-h-[88px] rounded-xl border border-slate-300 px-3 py-2 text-sm outline-none resize-none focus:ring-2 focus:ring-emerald-400 focus:border-emerald-400"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">{t.allergies}</label>
                <textarea
                  value={form.allergies}
                  onChange={e => onChange({ allergies: e.target.value })}
                  placeholder={t.allergiesPlaceholder}
                  className="w-full min-h-[88px] rounded-xl border border-slate-300 px-3 py-2 text-sm outline-none resize-none focus:ring-2 focus:ring-emerald-400 focus:border-emerald-400"
                />
              </div>
            </>
          )}
        </div>

        <div className="px-5 py-4 border-t border-slate-100 flex justify-end gap-2">
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-2 text-sm rounded-xl border border-slate-300 bg-white text-slate-700 hover:bg-slate-50"
            disabled={saving}
          >
            {t.cancel}
          </button>

          <button
            type="button"
            onClick={onSave}
            className="px-4 py-2 text-sm rounded-xl bg-emerald-500 text-white hover:bg-emerald-600 disabled:opacity-50"
            disabled={loading || saving}
          >
            {saving ? '...' : t.save}
          </button>
        </div>
      </div>
    </div>
  );
}

function ChatBubble({ msg, doctorWantsMore }: { msg: ChatMessage; doctorWantsMore: string }) {
  const isUser = msg.role === 'user';
  const followUps = !isUser ? msg.meta?.follow_up_questions ?? [] : [];

  return (
    <div className={`flex flex-col ${isUser ? 'items-end' : 'items-start'}`}>
      <div className="max-w-[80%] flex flex-col gap-2">
        <div
          className={`rounded-2xl px-3 py-2 text-sm leading-relaxed shadow-sm ${
            isUser ? 'bg-emerald-500 text-white rounded-br-sm' : 'bg-white border border-slate-200 text-slate-800 rounded-bl-sm'
          }`}
        >
          {msg.content}
        </div>

        {msg.image && (
          <div className="rounded-xl overflow-hidden border border-slate-200 bg-white shadow-sm">
            <img src={msg.image.previewUrl} alt={msg.image.name || 'uploaded'} className="max-h-60 w-full object-contain bg-slate-50" />
            {msg.image.name && (
              <div className="px-2 py-1 text-[11px] text-slate-500 border-t border-slate-100">
                {msg.image.name}
              </div>
            )}
          </div>
        )}
      </div>

      {!isUser && followUps.length > 0 && (
        <div className="mt-1 max-w-[80%] text-[11px] text-slate-400 leading-snug">
          <span className="font-medium">{doctorWantsMore}</span>
          {followUps.join('；')}
        </div>
      )}
    </div>
  );
}

function RiskPanel({
  meta,
  t,
  triageLabelLocalized,
}: {
  meta?: ConsultResponse;
  t: any;
  triageLabelLocalized: (l: any) => string;
}) {
  if (!meta) {
    return (
      <div className="w-full bg-slate-100 border border-dashed border-slate-300 rounded-xl px-4 py-3 text-xs text-slate-500">
        {t.riskEmpty}
      </div>
    );
  }

  const triageCls = triageColor(meta.triage_level);
  const label = triageLabelLocalized(meta.triage_level);

  return (
    <div className="w-full flex flex-col md:flex-row md:items-center gap-2 bg-white border border-slate-200 rounded-xl px-4 py-3 shadow-sm">
      <div className={`inline-flex items-center gap-2 px-3 py-1 rounded-full text-xs font-medium border ${triageCls}`}>
        <span>{t.riskLevel}</span>
        <span>{label}</span>
      </div>
      {meta.context_summary && (
        <div className="text-xs text-slate-600 md:ml-3">
          <span className="font-medium text-slate-700">{t.summary}</span>
          {meta.context_summary}
        </div>
      )}
    </div>
  );
}

function DiagnosisPanel({ meta, t }: { meta?: ConsultResponse; t: any }) {
  if (!meta || !meta.possible_diagnoses?.length) {
    return (
      <div className="bg-slate-100 border border-dashed border-slate-300 rounded-xl px-3 py-2 text-xs text-slate-500">
        {t.diagnosisEmpty}
      </div>
    );
  }

  return (
    <div className="bg-white border border-slate-200 rounded-xl px-3 py-2 shadow-sm">
      <div className="text-sm font-medium text-slate-800 mb-1.5">{t.diagnosisTitle}</div>
      <div className="space-y-1.5">
        {meta.possible_diagnoses.map((d, idx) => {
          const pct = Math.round(d.probability * 100);
          return (
            <div key={idx} className="border border-slate-200 rounded-lg px-2 py-1.5 text-xs flex justify-between">
              <span className="font-medium text-slate-800">{d.name}</span>
              <span className="text-slate-500">{pct}%</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function RedFlagsPanel({ meta, t }: { meta?: ConsultResponse; t: any }) {
  if (!meta || !meta.red_flags?.length) return null;
  return (
    <div className="bg-red-50 border border-red-300 rounded-xl px-3 py-2 shadow-sm">
      <div className="text-xs font-semibold text-red-700 mb-1">{t.redFlagTitle}</div>
      <ul className="list-disc list-inside text-xs text-red-700 space-y-0.5">
        {meta.red_flags.map((r, i) => (
          <li key={i}>{r}</li>
        ))}
      </ul>
    </div>
  );
}

function FollowUpPanel({
  meta,
  t,
  onFollowUpClick,
}: {
  meta?: ConsultResponse;
  t: any;
  onFollowUpClick: (q: string) => void;
}) {
  if (!meta) return null;
  return (
    <div className="bg-white border border-slate-200 rounded-xl px-3 py-2 shadow-sm">
      <div className="flex items-center justify-between mb-1.5">
        <div className="text-sm font-medium text-slate-800">{t.followUpTitle}</div>
        <span className="text-[11px] text-slate-400">{t.followUpHint}</span>
      </div>

      <div className="flex flex-wrap gap-1">
        {t.followUps.map((q: string, i: number) => (
          <button
            key={i}
            type="button"
            className="text-xs px-2 py-1 rounded-full border border-emerald-200 text-emerald-700 bg-emerald-50 hover:bg-emerald-100"
            onClick={() => onFollowUpClick(q)}
          >
            {q}
          </button>
        ))}
      </div>
    </div>
  );
}
