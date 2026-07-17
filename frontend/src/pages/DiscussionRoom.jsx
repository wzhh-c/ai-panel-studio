import { useState, useRef, useEffect, useCallback, useReducer } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { getDiscussion, endDiscussion, askQuestion } from '../api/client';
import useSSE from '../hooks/useSSE';

// ── reducer ─────────────────────────────────────────────────────

const initialState = {
  discussion: null,
  transcripts: [],
  experts: [],
  consensusList: [],
  divergenceList: [],
  summary: '',
  ended: false,
};

function roomReducer(state, action) {
  switch (action.type) {
    case 'INIT':
      return { ...state, discussion: action.discussion, experts: action.experts };

    case 'SPEECH': {
      const exists = state.transcripts.find((t) => t.id === action.speech.id);
      if (exists) return state;
      return {
        ...state,
        transcripts: [...state.transcripts, action.speech].sort(
          (a, b) => (a.sequence ?? 0) - (b.sequence ?? 0),
        ),
      };
    }

    case 'STATUS_UPDATE':
      return {
        ...state,
        experts: state.experts.map((e) =>
          e.id === action.data.expert_id
            ? { ...e, status: action.data.expert_status }
            : e,
        ),
      };

    case 'CONSENSUS':
      return {
        ...state,
        consensusList: upsertById(state.consensusList, action.data),
      };

    case 'DIVERGENCE':
      return {
        ...state,
        divergenceList: upsertById(state.divergenceList, action.data),
      };

    case 'SUMMARY':
      return { ...state, summary: action.data.summary, ended: true };

    default:
      return state;
  }
}

function upsertById(list, item) {
  const idx = list.findIndex((x) => x.id === item.id);
  if (idx >= 0) {
    const copy = [...list];
    copy[idx] = item;
    return copy;
  }
  return [...list, item];
}

// ── helpers ─────────────────────────────────────────────────────

const STATUS_DOT = {
  idle:     'bg-gray-300',
  typing:   'bg-yellow-400 animate-pulse',
  speaking: 'bg-green-500',
};

const STATUS_LABEL = {
  idle:     '空闲',
  typing:   '输入中',
  speaking: '发言中',
};

function formatTime(iso) {
  if (!iso) return '';
  const d = new Date(iso);
  return d.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
}

// ═══════════════════════════════════════════════════════════════════

export default function DiscussionRoom() {
  const { id } = useParams();
  const navigate = useNavigate();

  const [state, dispatch] = useReducer(roomReducer, initialState);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState('');
  const [mobileTab, setMobileTab] = useState('transcript');
  const [ending, setEnding] = useState(false);
  const [question, setQuestion] = useState('');
  const [asking, setAsking] = useState(false);

  const transcriptEndRef = useRef(null);

  // ── SSE handler ─────────────────────────────────────────────
  const handleSSEEvent = useCallback((eventType, data) => {
    switch (eventType) {
      case 'speech':
        dispatch({ type: 'SPEECH', speech: data });
        break;
      case 'status_update':
        dispatch({ type: 'STATUS_UPDATE', data });
        break;
      case 'consensus_update':
        dispatch({ type: 'CONSENSUS', data });
        break;
      case 'divergence_update':
        dispatch({ type: 'DIVERGENCE', data });
        break;
      case 'summary':
        dispatch({ type: 'SUMMARY', data });
        break;
    }
  }, []);

  useSSE(id, handleSSEEvent);

  // ── initial load ────────────────────────────────────────────
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await getDiscussion(id);
        if (cancelled) return;
        const d = res.data;
        const experts = (d.experts || []).map((e) => ({ ...e, status: 'idle' }));
        // Load existing transcripts.
        const transcripts = (d.transcripts || []).sort(
          (a, b) => (a.sequence ?? 0) - (b.sequence ?? 0),
        );
        dispatch({ type: 'INIT', discussion: d, experts });
        transcripts.forEach((t) => dispatch({ type: 'SPEECH', speech: t }));
        // Existing consensus/divergence.
        (d.consensus_list || []).forEach((c) =>
          dispatch({ type: 'CONSENSUS', data: c }),
        );
        (d.divergence_list || []).forEach((dv) =>
          dispatch({ type: 'DIVERGENCE', data: dv }),
        );
      } catch (err) {
        if (!cancelled) setLoadError(err.response?.data?.detail || '加载失败');
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [id]);

  // ── auto-scroll ─────────────────────────────────────────────
  useEffect(() => {
    transcriptEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [state.transcripts.length]);

  // ── auto-navigate after summary ─────────────────────────────
  useEffect(() => {
    if (state.ended) {
      const timer = setTimeout(() => navigate('/'), 3000);
      return () => clearTimeout(timer);
    }
  }, [state.ended, navigate]);

  // ── end discussion ──────────────────────────────────────────
  const handleEnd = async () => {
    setEnding(true);
    try {
      await endDiscussion(id);
    } catch (err) {
      // summary event may arrive before the HTTP response in SSE;
      // ignore errors here.
    } finally {
      setEnding(false);
    }
  };

  // ── ask question ────────────────────────────────────────────
  const handleAsk = async () => {
    const q = question.trim();
    if (!q || asking) return;
    setAsking(true);
    try {
      await askQuestion(id, q);
      setQuestion('');
    } catch (err) {
      console.error('提问失败:', err);
      alert('提问失败，请稍后重试');
    } finally {
      setAsking(false);
    }
  };

  const handleAskKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleAsk();
    }
  };

  // ── loading / error ─────────────────────────────────────────
  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-900">
        <div className="text-center">
          <div className="animate-spin rounded-full h-10 w-10 border-4
                          border-indigo-200 border-t-indigo-600 mx-auto mb-3" />
          <p className="text-gray-400">进入讨论室...</p>
        </div>
      </div>
    );
  }

  if (loadError) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-900">
        <div className="text-center max-w-md mx-4">
          <p className="text-red-400 text-lg mb-4">{loadError}</p>
          <button onClick={() => navigate('/')}
                  className="px-5 py-2.5 bg-indigo-600 text-white rounded-lg
                             hover:bg-indigo-700 transition-colors text-sm">
            返回首页
          </button>
        </div>
      </div>
    );
  }

  const { discussion, transcripts, experts, consensusList, divergenceList, summary, ended } = state;
  const topic = discussion?.topic || '';

  return (
    <div className="h-screen flex flex-col bg-gray-900 text-gray-100">
      {/* top bar */}
      <header className="h-12 bg-gray-800 border-b border-gray-700 flex items-center
                          px-3 sm:px-4 flex-shrink-0 gap-3">
        <button onClick={() => navigate('/')}
                className="p-1 text-gray-400 hover:text-gray-200 rounded">
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
          </svg>
        </button>
        <h1 className="text-sm font-medium text-gray-200 truncate flex-1">{topic}</h1>
        {!ended && (
          <button
            onClick={handleEnd}
            disabled={ending}
            className="px-3 py-1 text-xs font-medium bg-red-600 hover:bg-red-700
                       text-white rounded-lg transition-colors disabled:opacity-50"
          >
            {ending ? '结束中...' : '结束讨论'}
          </button>
        )}
      </header>

      {/* main area — three columns on desktop, tabbed on mobile */}
      <div className="flex-1 flex overflow-hidden">
        {/* ── LEFT: experts ─────────────────────────────────── */}
        <SidePanel
          title="专家"
          show={mobileTab === 'experts'}
          className="hidden lg:flex lg:w-1/5 xl:w-1/5"
        >
          <div className="flex flex-col gap-2 p-3">
            {experts.map((e) => {
              const isSpeaking = e.status === 'speaking';
              return (
                <div key={e.id}
                     className={`flex items-center gap-2.5 bg-gray-800 rounded-lg px-3 py-2
                                 transition-all duration-500
                                 ${isSpeaking
                                   ? 'ring-2 ring-green-500/60 shadow-lg shadow-green-500/20 bg-gray-800/80'
                                   : 'ring-2 ring-transparent shadow-none'}`}>
                  <span className="w-2.5 h-2.5 rounded-full flex-shrink-0"
                        style={{ backgroundColor: e.color }} />
                  <span className="text-sm text-gray-200 truncate flex-1">{e.name}</span>
                  <span className={`w-2 h-2 rounded-full flex-shrink-0 ${STATUS_DOT[e.status] || STATUS_DOT.idle}`}
                        title={STATUS_LABEL[e.status] || '空闲'} />
                </div>
              );
            })}
          </div>
        </SidePanel>

        {/* ── CENTER: transcript ────────────────────────────── */}
        <div className="flex-1 flex flex-col overflow-hidden border-x border-gray-700">
          <div className="flex-1 overflow-y-auto px-4 py-4 space-y-4">
            {transcripts.map((t) => {
              const speaker = experts.find((e) => e.id === t.speaker_id);
              // 查找被回复人姓名
              let replyToName = null;
              if (t.reply_to_id) {
                const replyExpert = experts.find((e) => e.id === t.reply_to_id);
                if (replyExpert) {
                  replyToName = replyExpert.name;
                } else {
                  const replyTranscript = transcripts.find((tr) => tr.speaker_id === t.reply_to_id);
                  replyToName = replyTranscript?.speaker_name || null;
                }
              }
              return (
                <div key={t.id} className="flex gap-3">
                  <div
                    className="w-8 h-8 rounded-full flex-shrink-0 flex items-center
                               justify-center text-white text-xs font-bold"
                    style={{ backgroundColor: speaker?.color || t.speaker_color || '#6B7280' }}
                  >
                    {(speaker?.name || t.speaker_name || '?')[0]}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1">
                      <span className="text-sm font-semibold"
                            style={{ color: speaker?.color || t.speaker_color || '#9CA3AF' }}>
                        {speaker?.name || t.speaker_name || '未知'}
                      </span>
                      {replyToName && (
                        <span className="text-xs text-blue-300">
                          回复 @{replyToName}
                        </span>
                      )}
                      {t.is_user_question && (
                        <span className="text-[10px] bg-blue-500/20 text-blue-300
                                         px-1.5 py-0.5 rounded-full">
                          💬 用户提问
                        </span>
                      )}
                      <span className="text-xs text-gray-500">{formatTime(t.created_at)}</span>
                    </div>
                    <p className="text-sm text-gray-200 leading-relaxed whitespace-pre-wrap">
                      {t.content}
                    </p>
                  </div>
                </div>
              );
            })}

            {/* summary banner */}
            {summary && (
              <div className="bg-indigo-900/30 border border-indigo-500/50 rounded-xl p-4 mt-4">
                <p className="text-xs font-semibold text-indigo-300 mb-2">📋 主持人总结</p>
                <p className="text-sm text-gray-200 leading-relaxed whitespace-pre-wrap">{summary}</p>
              </div>
            )}

            <div ref={transcriptEndRef} />
          </div>

          {/* question input bar */}
          {!ended && (
            <div className="flex-shrink-0 px-4 py-3 bg-gray-800 border-t border-gray-700">
              <div className="flex gap-2">
                <input
                  type="text"
                  value={question}
                  onChange={(e) => setQuestion(e.target.value)}
                  onKeyDown={handleAskKeyDown}
                  placeholder="向专家提问...（按回车发送）"
                  disabled={asking}
                  className="flex-1 bg-gray-700 text-sm text-gray-100
                             placeholder-gray-500 rounded-lg px-3 py-2
                             border border-gray-600 focus:border-blue-500
                             focus:outline-none transition-colors
                             disabled:opacity-50 disabled:cursor-not-allowed"
                />
                <button
                  onClick={handleAsk}
                  disabled={asking || !question.trim()}
                  className="px-4 py-2 text-sm font-medium bg-blue-600
                             hover:bg-blue-700 text-white rounded-lg
                             transition-colors disabled:opacity-50
                             disabled:cursor-not-allowed flex-shrink-0"
                >
                  {asking ? '发送中...' : '提问'}
                </button>
              </div>
            </div>
          )}
        </div>

        {/* ── RIGHT: consensus & divergence ─────────────────── */}
        <SidePanel
          title="共识·分歧"
          show={mobileTab === 'analysis'}
          className="hidden lg:flex lg:w-1/5 xl:w-1/5"
        >
          <div className="flex flex-col h-full">
            {/* consensus */}
            <div className="flex-1 overflow-y-auto p-3 border-b border-gray-700">
              <h3 className="text-xs font-semibold text-green-400 uppercase tracking-wide mb-2">
                ✅ 共识
              </h3>
              {consensusList.length === 0 && (
                <p className="text-xs text-gray-500">等待共识识别...</p>
              )}
              {consensusList.map((c) => (
                <div key={c.id} className="bg-gray-800 rounded-lg p-2.5 mb-2">
                  <p className="text-xs text-gray-200 leading-relaxed">{c.content}</p>
                  <p className="text-[10px] text-gray-500 mt-1">
                    {c.action === 'created' ? '新共识' : '已更新'} · {formatTime(c.updated_at)}
                  </p>
                </div>
              ))}
            </div>

            {/* divergence */}
            <div className="flex-1 overflow-y-auto p-3">
              <h3 className="text-xs font-semibold text-orange-400 uppercase tracking-wide mb-2">
                ⚡ 分歧
              </h3>
              {divergenceList.length === 0 && (
                <p className="text-xs text-gray-500">等待分歧识别...</p>
              )}
              {divergenceList.map((d) => (
                <div key={d.id} className="bg-gray-800 rounded-lg p-2.5 mb-2">
                  <p className="text-xs text-gray-200 leading-relaxed">{d.content}</p>
                  {d.sides && (
                    <div className="mt-1.5 flex flex-wrap gap-1">
                      {(Array.isArray(d.sides) ? d.sides : []).map((s, i) => (
                        <span key={i}
                              className="text-[10px] bg-gray-700 text-gray-300 px-1.5 py-0.5 rounded">
                          {s.stance_label || s.summary}
                        </span>
                      ))}
                    </div>
                  )}
                  <p className="text-[10px] text-gray-500 mt-1">
                    {d.action === 'created' ? '新分歧' : '已更新'} · {formatTime(d.updated_at)}
                  </p>
                </div>
              ))}
            </div>
          </div>
        </SidePanel>
      </div>

      {/* mobile tab bar */}
      <nav className="lg:hidden h-11 bg-gray-800 border-t border-gray-700 flex flex-shrink-0">
        {[
          { key: 'experts',    label: '专家',  icon: '👥' },
          { key: 'transcript', label: '发言',  icon: '💬' },
          { key: 'analysis',   label: '分析',  icon: '📊' },
        ].map((tab) => (
          <button
            key={tab.key}
            onClick={() => setMobileTab(tab.key)}
            className={`flex-1 flex items-center justify-center gap-1 text-xs
                        ${mobileTab === tab.key
                          ? 'text-indigo-400 border-t-2 border-indigo-400'
                          : 'text-gray-500 border-t-2 border-transparent'}`}
          >
            <span>{tab.icon}</span>
            {tab.label}
          </button>
        ))}
      </nav>
    </div>
  );
}

/** Collapsible side panel (hidden on mobile unless active tab). */
function SidePanel({ title, children, show, className = '' }) {
  return (
    <aside className={`${className} flex-col bg-gray-850 overflow-hidden
                       ${show === false ? 'hidden' : 'flex lg:flex'}`}>
      <div className="h-8 bg-gray-800 flex items-center px-3 border-b border-gray-700 flex-shrink-0">
        <span className="text-[11px] font-semibold text-gray-400 uppercase tracking-wide">
          {title}
        </span>
      </div>
      <div className="flex-1 overflow-y-auto">
        {children}
      </div>
    </aside>
  );
}