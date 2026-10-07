import React, { useRef, useEffect } from 'react';
import { MessageSquare, User, Bot, Volume2, Sparkles, Trash2 } from 'lucide-react';

export default function LiveConversation({ conversation, partialTranscript, sessionState, isVoiceActive, onClearConversation }) {
  const bottomRef = useRef(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [conversation, sessionState, partialTranscript]);

  const hasMessages = Boolean((conversation && conversation.length > 0) || (partialTranscript && partialTranscript.content));

  return (
    <div className="glass-panel" style={{ padding: '20px', display: 'flex', flexDirection: 'column', height: '100%', minHeight: '440px' }}>
      
      {/* Header */}
      <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        flexWrap: 'wrap',
        gap: '10px',
        marginBottom: '16px',
        borderBottom: '1px solid rgba(148, 163, 184, 0.1)',
        paddingBottom: '12px'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <MessageSquare size={18} color="#14B8A6" />
          <h2 style={{ fontSize: '15px', fontWeight: '600', color: '#F1F5F9' }}>
            Live Conversation Stream
          </h2>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '10px', flexWrap: 'wrap' }}>
          <button
            onClick={onClearConversation}
            id="clear-conversation-btn"
            title="Clear all conversation data, transcripts, and session buffers"
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '6px',
              background: hasMessages ? 'rgba(239, 68, 68, 0.16)' : 'rgba(239, 68, 68, 0.08)',
              border: hasMessages ? '1px solid rgba(239, 68, 68, 0.38)' : '1px solid rgba(239, 68, 68, 0.22)',
              color: '#FDA4AF',
              borderRadius: '8px',
              padding: '5px 11px',
              fontSize: '11px',
              fontWeight: '600',
              cursor: 'pointer',
              opacity: 1,
              transition: 'all 0.2s ease',
              outline: 'none'
            }}
          >
            <Trash2 size={13} color="#FDA4AF" />
            Clear Conversation
          </button>


          <span style={{ fontSize: '11px', color: '#64748B', fontWeight: '500' }}>
            STT & TTS Synchronized
          </span>
        </div>
      </div>

      {/* Messages Stream Container */}
      <div style={{
        flex: 1,
        overflowY: 'auto',
        display: 'flex',
        flexDirection: 'column',
        gap: '12px',
        paddingRight: '6px'
      }}>
        {(!conversation || conversation.length === 0) && (!partialTranscript || !partialTranscript.content) ? (
          <div style={{
            height: '100%',
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            color: '#64748B',
            textAlign: 'center',
            padding: '30px'
          }}>
            <Bot size={36} color="#334155" style={{ marginBottom: '10px' }} />
            <div style={{ fontSize: '14px', fontWeight: '500', color: '#94A3B8' }}>
              No active conversation yet
            </div>
            <p style={{ fontSize: '12px', color: '#64748B', marginTop: '4px', maxWidth: '280px' }}>
              Click <strong>Start Voice Conversation</strong> above to speak with the AI concierge, or use the interactive demo chips below.
            </p>
          </div>
        ) : (
          <>
            {conversation.filter((msg) => msg && msg.is_final !== false).map((msg, idx) => {
              const isUser = msg.role === 'user';

              return (
                <div key={msg.turn_id ? `turn-${msg.turn_id}-${idx}` : `msg-${idx}`} style={{
                  display: 'flex',
                  gap: '10px',
                  alignItems: 'flex-start',
                  flexDirection: isUser ? 'row-reverse' : 'row',
                  opacity: 1
                }}>
                  {/* Avatar Icon */}
                  <div style={{
                    width: '30px',
                    height: '30px',
                    borderRadius: '8px',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    background: isUser ? 'rgba(56, 189, 248, 0.15)' : 'rgba(20, 184, 166, 0.15)',
                    flexShrink: 0
                  }}>
                    {isUser ? <User size={15} color="#38BDF8" /> : <Bot size={15} color="#14B8A6" />}
                  </div>

                  {/* Message Bubble */}
                  <div style={{
                    maxWidth: '82%',
                    background: isUser ? 'rgba(30, 41, 59, 0.85)' : 'rgba(15, 23, 42, 0.85)',
                    border: isUser
                      ? '1px solid rgba(56, 189, 248, 0.25)'
                      : '1px solid rgba(20, 184, 166, 0.25)',
                    borderRadius: isUser ? '14px 14px 2px 14px' : '14px 14px 14px 2px',
                    padding: '10px 14px',
                    boxShadow: '0 4px 14px rgba(0, 0, 0, 0.25)'
                  }}>
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '8px', marginBottom: '4px' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                        <span style={{ fontSize: '11px', fontWeight: '600', color: isUser ? '#38BDF8' : '#2DD4BF' }}>
                          {isUser ? 'Caller / Guest' : 'Resort Concierge AI'}
                        </span>
                      </div>
                      {msg.mark_id && (
                        <span className="mono-font" style={{ fontSize: '9px', color: '#64748B' }}>
                          mark:{msg.mark_id}
                        </span>
                      )}
                    </div>
                    <div style={{
                      fontSize: '13px',
                      lineHeight: '1.5',
                      color: '#F1F5F9',
                      wordBreak: 'break-word',
                      fontStyle: 'normal'
                    }}>
                      {msg.content}
                    </div>
                  </div>
                </div>
              );
            })}

            {/* Live Interim / Partial Transcript Bubble (Replaces in place, NEVER committed) */}
            {partialTranscript && partialTranscript.content && (
              <div
                id="live-partial-transcript-bubble"
                style={{
                  display: 'flex',
                  gap: '10px',
                  alignItems: 'flex-start',
                  flexDirection: 'row-reverse',
                  opacity: 0.88,
                  transition: 'opacity 0.15s ease'
                }}
              >
                <div style={{
                  width: '30px',
                  height: '30px',
                  borderRadius: '8px',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  background: 'rgba(56, 189, 248, 0.22)',
                  flexShrink: 0,
                  border: '1px solid rgba(56, 189, 248, 0.4)'
                }}>
                  <User size={15} color="#38BDF8" />
                </div>

                <div style={{
                  maxWidth: '82%',
                  background: 'rgba(30, 41, 59, 0.92)',
                  border: '1px dashed #38BDF8',
                  borderRadius: '14px 14px 2px 14px',
                  padding: '10px 14px',
                  boxShadow: '0 4px 14px rgba(56, 189, 248, 0.15)'
                }}>
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '8px', marginBottom: '4px' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                      <span style={{ fontSize: '11px', fontWeight: '600', color: '#38BDF8' }}>
                        Caller / Guest
                      </span>
                      <span style={{
                        fontSize: '9px',
                        color: '#7DD3FC',
                        display: 'inline-flex',
                        alignItems: 'center',
                        gap: '4px',
                        background: 'rgba(56, 189, 248, 0.12)',
                        padding: '1px 6px',
                        borderRadius: '4px'
                      }}>
                        <span className="dot-pulse" style={{ display: 'inline-block', width: '5px', height: '5px', borderRadius: '50%', background: '#38BDF8' }} />
                        speaking live...
                      </span>
                    </div>
                  </div>
                  <div style={{
                    fontSize: '13px',
                    lineHeight: '1.5',
                    color: '#BAE6FD',
                    wordBreak: 'break-word',
                    fontStyle: 'italic'
                  }}>
                    {partialTranscript.content}
                  </div>
                </div>
              </div>
            )}
          </>
        )}

        {/* Live typing / thinking indicator */}
        {sessionState === 'THINKING' && (
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', padding: '8px 12px', background: 'rgba(168, 85, 247, 0.1)', border: '1px solid rgba(168, 85, 247, 0.25)', borderRadius: '10px', width: 'fit-content' }}>
            <Sparkles size={14} color="#A855F7" className="dot-pulse" />
            <span style={{ fontSize: '12px', color: '#C084FC', fontWeight: '500' }}>
              Gemini LLM reasoning with tools & RAG...
            </span>
          </div>
        )}

        {/* Live speaking indicator */}
        {sessionState === 'SPEAKING' && (
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', padding: '8px 12px', background: 'rgba(56, 189, 248, 0.1)', border: '1px solid rgba(56, 189, 248, 0.25)', borderRadius: '10px', width: 'fit-content' }}>
            <Volume2 size={14} color="#38BDF8" className="dot-pulse" />
            <span style={{ fontSize: '12px', color: '#38BDF8', fontWeight: '500' }}>
              Concierge speaking (TTS audio streaming)...
            </span>
          </div>
        )}

        <div ref={bottomRef} />
      </div>

    </div>
  );
}
