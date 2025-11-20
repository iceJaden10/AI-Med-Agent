// src/App.tsx
import { useState, useEffect } from 'react';
import { v4 as uuidv4 } from 'uuid';

import { consult, resetSession } from './api';
import type { ChatMessage, ConsultResponse } from './types';
import { triageLabel, triageColor } from './triage';

const DEFAULT_USER_ID = 'jaden-memory';
const GREETING_TEXT =
  '你好，我是你的智能医疗问诊助手。我会根据你描述的症状，给出初步的风险评估和就医建议，但不能替代医院面诊和正规医疗服务。请用中文详细描述你的不适、持续时间和伴随症状。';

// 继续问诊默认问题（用户视角）
const DEFAULT_FOLLOW_UP_QUESTIONS = [
  '如果我去医院的话，应该挂哪个科室？',
  '目前这种情况有没有比较合适的药物或处理方式？',
  '有哪些情况说明病情在加重，需要立刻去医院或急诊？',
  '在家休息期间，我需要特别注意些什么？',
];

function App() {
  const [userId] = useState(DEFAULT_USER_ID);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);

  // 最近一条带 meta 的助手消息，用于右侧展示
  const lastAssistantMessage = [...messages].reverse().find(m => m.role === 'assistant' && !!m.meta);
  const lastMeta: ConsultResponse | undefined = lastAssistantMessage?.meta;

  // 页面首次加载时插入问候语
  useEffect(() => {
    const greetingMsg: ChatMessage = {
      id: uuidv4(),
      role: 'assistant',
      content: GREETING_TEXT,
      ts: new Date().toISOString(),
    };
    setMessages([greetingMsg]);
  }, [userId]);

  // 新开聊天：重置前端 & 后端会话
  async function handleNewChat() {
    const greetingMsg: ChatMessage = {
      id: uuidv4(),
      role: 'assistant',
      content: GREETING_TEXT,
      ts: new Date().toISOString(),
    };
    setMessages([greetingMsg]);
    setInput('');
    setLoading(false);

    try {
      await resetSession(userId);
      console.log('Session reset for user:', userId);
    } catch (err) {
      console.error('Failed to reset session', err);
    }
  }

  // 发送消息
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
    // 用户快速提问
    handleSend(question);
  }

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col items-center">
      {/* 顶部导航：整体宽度保持不变 */}
      <header className="w-full max-w-6xl px-4 pt-4 pb-2 flex items-center justify-between">
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

      {/* 主体区域：整体宽度保持不变 */}
      <main className="w-full max-w-6xl px-4 pb-4 flex flex-col gap-3 flex-1">
        {/* 当前风险等级 & 摘要 */}
        <RiskPanel meta={lastMeta} />

        {/* 聊天区域 + 诊断&红旗 */}
        <div className="grid grid-cols-1 md:grid-cols-12 gap-3 md:gap-4 flex-1 items-stretch">
          {/* 左侧：聊天记录 —— 固定高度 + 内部滚动 */}
          <section
            className="
              md:col-span-9 bg-white rounded-xl shadow-sm border border-slate-200
              flex flex-col md:h-[600px] h-[700px] min-h-0
            "
          >
            {/* 上方提示文案 */}
            <div className="px-4 py-3 border-b border-slate-100 text-sm text-slate-500">
              请尽量详细描述你的症状、持续时间、伴随情况等。系统不会记录身份证号等敏感信息。
            </div>

            {/* 消息列表（内部滚动） */}
            <div className="flex-1 min-h-0 overflow-y-auto px-4 py-3 space-y-3">
              {messages.map(msg => (
                <ChatBubble key={msg.id} msg={msg} />
              ))}
            </div>

            {/* 底部输入区 —— 左输入框 / 右按钮上下排列 */}
            <div className="border-t border-slate-100 px-3 py-3">
              <div className="flex items-stretch gap-3">
                {/* 左侧：输入框 */}
                <textarea
                  className="flex-1 resize-none rounded-lg border border-slate-200 px-4 py-3 text-sm
                             focus:outline-none focus:ring-2 focus:ring-emerald-400 focus:border-emerald-400
                             bg-white h-[80px]"
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

                {/* 右侧：按钮上下排列 */}
                <div className="flex flex-col justify-between gap-2">
                  <button
                    onClick={handleNewChat}
                    className="text-xs px-3 py-2 rounded-lg border border-slate-300
                               text-slate-700 bg-white hover:bg-slate-100 whitespace-nowrap"
                  >
                    新开聊天
                  </button>

                  <button
                    className="px-4 py-2.5 rounded-lg text-sm font-medium bg-emerald-500 text-white
                               hover:bg-emerald-600 disabled:bg-slate-300 disabled:cursor-not-allowed
                               whitespace-nowrap"
                    onClick={() => handleSend()}
                    disabled={loading || !input.trim()}
                  >
                    {loading ? '问诊中…' : '发送'}
                  </button>
                </div>
              </div>
            </div>
          </section>

          {/* 右侧：诊断卡片 + 红旗 + 继续问诊 —— 占比变小 */}
          <section className="md:col-span-3 flex flex-col gap-3">
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
  const followUps = !isUser ? msg.meta?.follow_up_questions ?? [] : [];

  return (
    <div className={`flex flex-col ${isUser ? 'items-end' : 'items-start'}`}>
      <div
        className={`max-w-[80%] rounded-2xl px-3 py-2 text-sm leading-relaxed shadow-sm ${
          isUser
            ? 'bg-emerald-500 text-white rounded-br-sm'
            : 'bg-white border border-slate-200 text-slate-800 rounded-bl-sm'
        }`}
      >
        {msg.content}
      </div>

      {/* 助手侧：后端返回的继续问诊问题，作为灰色小字展示在下方 */}
      {!isUser && followUps.length > 0 && (
        <div className="mt-1 max-w-[80%] text-[11px] text-slate-400 leading-snug">
          <span className="font-medium">医生想进一步了解：</span>
          {followUps.join('；')}
        </div>
      )}
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
  // 需要先有一次问诊结果再展示“继续问诊”
  if (!meta) return null;

  return (
    <div className="bg-white border border-slate-200 rounded-xl px-3 py-2 shadow-sm">
      <div className="flex items-center justify-between mb-1.5">
        <div className="text-sm font-medium text-slate-800">继续问诊</div>
        <span className="text-[11px] text-slate-400">点击下方问题快速提问</span>
      </div>
      <div className="flex flex-wrap gap-1">
        {DEFAULT_FOLLOW_UP_QUESTIONS.map((q, i) => (
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
