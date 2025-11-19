// src/App.tsx
import { useState } from 'react';
import { v4 as uuidv4 } from 'uuid';

import { consult } from './api';
import type { ChatMessage, ConsultResponse } from './types';
import { triageLabel, triageColor } from './triage';

const DEFAULT_USER_ID = 'jaden-memory';

function App() {
  const [userId] = useState(DEFAULT_USER_ID);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);

  const lastAssistantMessage = [...messages].reverse().find(m => m.role === 'assistant');
  const lastMeta: ConsultResponse | undefined = lastAssistantMessage?.meta;

  async function handleSend(customText?: string) {
    const text = (customText ?? input).trim();
    if (!text || loading) return;

    const ts = new Date().toISOString();

    const userMsg: ChatMessage = {
      id: uuidv4(),
      role: 'user',
      content: text,
      ts,
    };

    setMessages(prev => [...prev, userMsg]);
    setInput('');
    setLoading(true);

    try {
      const res = await consult({
        user_id: userId,
        query: text,
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
        content: '抱歉，系统开小差了，请稍后再试一次或检查网络连接。',
        ts: new Date().toISOString(),
      };
      setMessages(prev => [...prev, errMsg]);
    } finally {
      setLoading(false);
    }
  }

  function handleFollowUpClick(question: string) {
    handleSend(question);
  }

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col items-center">
      {/* 顶部导航 */}
      <header className="w-full max-w-4xl px-4 pt-4 pb-2 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-full bg-emerald-500 flex items-center justify-center text-white font-bold">
            医
          </div>
          <div>
            <div className="text-base font-semibold">智能医疗问诊助手</div>
            <div className="text-xs text-slate-500">不能替代医院，仅供健康信息参考</div>
          </div>
        </div>
      </header>

      <main className="w-full max-w-4xl px-4 pb-4 flex flex-col gap-3 flex-1">
        {/* 当前风险等级 & 摘要 */}
        <RiskPanel meta={lastMeta} />

        {/* 聊天区域 + 诊断&红旗 */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3 md:gap-4 flex-1">
          {/* 左侧：聊天记录 */}
          <section className="md:col-span-2 bg-white rounded-xl shadow-sm border border-slate-200 flex flex-col">
            <div className="px-4 py-3 border-b border-slate-100 text-sm text-slate-500">
              请用中文描述你的症状、持续时间、伴随情况。系统不会记录身份证号等敏感信息。
            </div>
            <div className="flex-1 overflow-y-auto px-4 py-3 space-y-3">
              {messages.length === 0 && (
                <div className="text-xs text-slate-400 text-center mt-6">
                  例如可以输入：「这两天一直咳嗽，还有点低烧」「孩子今天早上开始拉肚子」等。
                </div>
              )}

              {messages.map(msg => (
                <ChatBubble key={msg.id} msg={msg} />
              ))}
            </div>
            <div className="border-t border-slate-100 px-3 py-2">
              <div className="flex items-end gap-2">
                <textarea
                  className="flex-1 resize-none rounded-lg border border-slate-200 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-400 focus:border-emerald-400 bg-slate-50"
                  rows={2}
                  placeholder="请描述你的症状，例如：这两天一直咳嗽，还有点低烧……"
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
                <button
                  className="inline-flex items-center justify-center px-4 py-2 rounded-lg text-sm font-medium bg-emerald-500 text-white hover:bg-emerald-600 disabled:bg-slate-300 disabled:cursor-not-allowed"
                  onClick={() => handleSend()}
                  disabled={loading || !input.trim()}
                >
                  {loading ? '问诊中...' : '发送'}
                </button>
              </div>
            </div>
          </section>

          {/* 右侧：诊断卡片 + 红旗 + 继续问诊 */}
          <section className="flex flex-col gap-3">
            <DiagnosisPanel meta={lastMeta} />
            <RedFlagsPanel meta={lastMeta} />
            <FollowUpPanel meta={lastMeta} onFollowUpClick={handleFollowUpClick} />
          </section>
        </div>
      </main>
    </div>
  );
}

export default App;

// ====== 子组件们 ======

function ChatBubble({ msg }: { msg: ChatMessage }) {
  const isUser = msg.role === 'user';
  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'}`}>
      <div
        className={`max-w-[80%] rounded-2xl px-3 py-2 text-sm leading-relaxed shadow-sm ${
          isUser
            ? 'bg-emerald-500 text-white rounded-br-sm'
            : 'bg-white border border-slate-200 text-slate-800 rounded-bl-sm'
        }`}
      >
        {msg.content}
      </div>
    </div>
  );
}

function RiskPanel({ meta }: { meta?: ConsultResponse }) {
  if (!meta) {
    return (
      <div className="w-full bg-slate-100 border border-dashed border-slate-300 rounded-xl px-4 py-3 text-xs text-slate-500">
        当前暂无风险评估。发送一条症状描述后，这里会显示系统给出的就诊紧急程度。
      </div>
    );
  }

  const triageCls = triageColor(meta.triage_level);
  const label = triageLabel(meta.triage_level);

  return (
    <div className="w-full flex flex-col md:flex-row md:items-center gap-2 bg-white border border-slate-200 rounded-xl px-4 py-3 shadow-sm">
      <div className={`inline-flex items-center gap-2 px-3 py-1 rounded-full text-xs font-medium border ${triageCls}`}>
        <span>当前风险等级：</span>
        <span>{label}</span>
      </div>
      {meta.context_summary && (
        <div className="text-xs text-slate-600 md:ml-3">
          <span className="font-medium text-slate-700">系统摘要：</span>
          {meta.context_summary}
        </div>
      )}
    </div>
  );
}

function DiagnosisPanel({ meta }: { meta?: ConsultResponse }) {
  if (!meta || !meta.possible_diagnoses?.length) {
    return (
      <div className="bg-slate-100 border border-dashed border-slate-300 rounded-xl px-3 py-2 text-xs text-slate-500">
        这里会展示「可能诊断」及对应的概率，仅供参考，不能替代医生面诊。
      </div>
    );
  }

  return (
    <div className="bg-white border border-slate-200 rounded-xl px-3 py-2 shadow-sm">
      <div className="flex items-center justify-between mb-1.5">
        <div className="text-sm font-medium text-slate-800">可能诊断（仅供参考）：</div>
      </div>
      <div className="space-y-1.5">
        {meta.possible_diagnoses.map((d, idx) => {
          const pct = Math.round(d.probability * 100);
          return (
            <div
              key={idx}
              className="border border-slate-200 rounded-lg px-2 py-1.5 text-xs flex flex-col gap-1"
            >
              <div className="flex justify-between items-center">
                <span className="font-medium text-slate-800">{d.name}</span>
                <span className="text-slate-500">{pct}%</span>
              </div>
              <div className="w-full h-1.5 bg-slate-100 rounded-full overflow-hidden">
                <div
                  className="h-full bg-emerald-400"
                  style={{ width: `${Math.min(100, Math.max(0, pct))}%` }}
                />
              </div>
            </div>
          );
        })}
      </div>
      {meta.suggestions?.length > 0 && (
        <div className="mt-2 pt-1 border-t border-slate-100">
          <div className="text-xs font-medium text-slate-700 mb-1">系统建议：</div>
          <ul className="list-disc list-inside space-y-0.5 text-xs text-slate-600">
            {meta.suggestions.map((s, i) => (
              <li key={i}>{s}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

function RedFlagsPanel({ meta }: { meta?: ConsultResponse }) {
  if (!meta || !meta.red_flags?.length) return null;

  return (
    <div className="bg-red-50 border border-red-300 rounded-xl px-3 py-2 shadow-sm">
      <div className="text-xs font-semibold text-red-700 mb-1 flex items-center gap-1.5">
        <span>⚠️ 强提醒（红旗信号）</span>
      </div>
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
  onFollowUpClick,
}: {
  meta?: ConsultResponse;
  onFollowUpClick: (q: string) => void;
}) {
  if (!meta || !meta.follow_up_questions?.length) return null;

  return (
    <div className="bg-white border border-slate-200 rounded-xl px-3 py-2 shadow-sm">
      <div className="flex items-center justify-between mb-1.5">
        <div className="text-sm font-medium text-slate-800">继续问诊</div>
        <span className="text-[11px] text-slate-400">点击下方问题继续回答</span>
      </div>
      <div className="flex flex-wrap gap-1">
        {meta.follow_up_questions.map((q, i) => (
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
