/**
 * DocumentChat - "chat with this document" panel.
 *
 * Sends the user's question to POST /api/documents/{id}/chat and renders
 * the answer. The conversation lives in component state only - nothing is
 * persisted server-side (the backend is stateless per request).
 *
 * The provider label from the response is shown honestly: answers produced
 * by Mock AI are labelled as simulated, never as Gemini output.
 */
import { useEffect, useRef, useState } from 'react';
import { motion } from 'framer-motion';
import { MessageSquareText, Send, Sparkles } from 'lucide-react';
import { askDocument } from '../../services/chat';
import { getErrorMessage } from '../../services/api';

const SUGGESTED_QUESTIONS = [
  'Summarize this document',
  'What are the key deadlines?',
  'Who should take action?',
];

// Honest labels per provider (kept in sync with AiResults.jsx).
const PROVIDER_LABELS = {
  mock: 'Mock AI (simulated)',
  gemini: 'Google Gemini',
  openrouter: 'OpenRouter',
  ollama: 'Ollama (local)',
};

export default function DocumentChat({ documentId, compact = false }) {
  const [messages, setMessages] = useState([]);
  const [question, setQuestion] = useState('');
  const [sending, setSending] = useState(false);
  const bottomRef = useRef(null);

  // A fresh conversation whenever a different document is opened.
  useEffect(() => {
    setMessages([]);
    setQuestion('');
  }, [documentId]);

  // Keep the newest message visible.
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' });
  }, [messages, sending]);

  async function sendQuestion(text) {
    const trimmed = (text ?? question).trim();
    if (!trimmed || sending) return;

    const userMessage = { role: 'user', text: trimmed };
    setMessages((current) => [...current, userMessage]);
    setQuestion('');
    setSending(true);

    try {
      const response = await askDocument(documentId, trimmed);
      setMessages((current) => [
        ...current,
        {
          role: 'assistant',
          text: response.answer,
          provider: response.provider,
          notice: response.provider_notice || null,
          sources: response.sources || [],
        },
      ]);
    } catch (error) {
      setMessages((current) => [
        ...current,
        { role: 'assistant', text: `Error: ${getErrorMessage(error)}`, provider: 'error' },
      ]);
    } finally {
      setSending(false);
    }
  }

  function handleSubmit(event) {
    event.preventDefault();
    sendQuestion();
  }

  return (
    <section className="flex flex-col rounded-xl border border-slate-200 bg-white">
      {/* Header */}
      <div className="flex items-center gap-2 border-b border-slate-100 px-4 py-3">
        <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-indigo-50 text-indigo-600">
          <MessageSquareText className="h-4 w-4" />
        </span>
        <div className="min-w-0">
          <h3 className="text-sm font-semibold text-slate-900">Chat with this document</h3>
          <p className="text-xs text-slate-400">
            Answers use only this document's text{compact ? '' : ' - nothing leaves your account'}
          </p>
        </div>
      </div>

      {/* Messages */}
      <div className={`${compact ? 'h-56' : 'h-72'} space-y-3 overflow-y-auto px-4 py-3`}>
        {messages.length === 0 && (
          <div className="flex h-full flex-col items-center justify-center text-center">
            <Sparkles className="h-6 w-6 text-indigo-300" />
            <p className="mt-2 text-sm font-medium text-slate-700">Ask anything about this document</p>
            <p className="mt-1 max-w-xs text-xs text-slate-400">
              e.g. deadlines, people, amounts, action items - the AI answers from the stored text only.
            </p>
            <div className="mt-3 flex flex-wrap justify-center gap-2">
              {SUGGESTED_QUESTIONS.map((suggestion) => (
                <button
                  key={suggestion}
                  type="button"
                  onClick={() => sendQuestion(suggestion)}
                  disabled={sending}
                  className="rounded-full border border-slate-200 bg-slate-50 px-3 py-1.5 text-xs text-slate-600 transition hover:border-indigo-200 hover:bg-indigo-50 hover:text-indigo-700 disabled:opacity-50"
                >
                  {suggestion}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((message, index) => (
          <motion.div
            key={index}
            initial={{ opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
            className={`flex ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}
          >
            <div
              className={`max-w-[85%] rounded-2xl px-3.5 py-2.5 text-sm leading-relaxed ${
                message.role === 'user'
                  ? 'bg-indigo-600 text-white'
                  : message.provider === 'error'
                    ? 'border border-rose-200 bg-rose-50 text-rose-700'
                    : 'bg-slate-100 text-slate-800'
              }`}
            >
              <p className="whitespace-pre-wrap">{message.text}</p>

              {/* Honest provider indicator - never claim Gemini when
                  another provider (or the mock engine) answered. */}
              {message.provider && message.provider !== 'error' && (
                <p className="mt-1.5 text-[10px] font-medium uppercase tracking-wide text-slate-400">
                  {PROVIDER_LABELS[message.provider] || message.provider}
                </p>
              )}

              {/* Fallback notice - only set when a provider failed over. */}
              {message.notice && (
                <p className="mt-2 rounded-lg border border-amber-200 bg-amber-50 px-2.5 py-1.5 text-[11px] leading-relaxed text-amber-800">
                  ⚠️ {message.notice}
                </p>
              )}

              {/* Retrieved chunk citations - only what was actually used. */}
              {message.sources?.length > 0 && (
                <div className="mt-2 border-t border-slate-200 pt-2">
                  <p className="mb-1.5 text-[10px] font-semibold uppercase tracking-wide text-slate-400">
                    Sources ({message.sources.length})
                  </p>
                  <div className="flex flex-wrap gap-1.5">
                    {message.sources.map((source) => (
                      <span
                        key={source.chunk_index}
                        title={source.excerpt}
                        className="cursor-help rounded-full border border-slate-200 bg-white px-2 py-0.5 text-[10px] font-medium text-slate-600"
                      >
                        chunk {source.chunk_index + 1} · {Math.round(source.score * 100)}%
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </motion.div>
        ))}

        {sending && (
          <div className="flex justify-start">
            <div className="flex items-center gap-1.5 rounded-2xl bg-slate-100 px-4 py-3">
              {[0, 1, 2].map((dot) => (
                <motion.span
                  key={dot}
                  className="h-1.5 w-1.5 rounded-full bg-slate-400"
                  animate={{ opacity: [0.3, 1, 0.3] }}
                  transition={{ duration: 1, repeat: Infinity, delay: dot * 0.2 }}
                />
              ))}
            </div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <form onSubmit={handleSubmit} className="flex items-center gap-2 border-t border-slate-100 p-3">
        <input
          className="input !py-2"
          placeholder="Ask a question about this document…"
          value={question}
          onChange={(event) => setQuestion(event.target.value)}
          maxLength={2000}
          disabled={sending}
        />
        <button
          type="submit"
          className="btn-primary !px-3 !py-2"
          disabled={sending || !question.trim()}
          aria-label="Send question"
        >
          <Send className="h-4 w-4" />
        </button>
      </form>
    </section>
  );
}
