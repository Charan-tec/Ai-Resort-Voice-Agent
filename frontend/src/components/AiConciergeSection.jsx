import React, { useRef, useEffect } from 'react';
import {
  PhoneCall,
  PhoneOff,
  Mic,
  MicOff,
  Sparkles,
  RotateCcw,
  Volume2,
  Send,
  HelpCircle,
  Clock,
  Compass,
  Bed,
  Utensils
} from 'lucide-react';

const SUGGESTED_QUESTIONS = [
  { icon: Bed, text: "I need a room for two guests from November 21 to November 25." },
  { icon: Sparkles, text: "Which room is the cheapest?" },
  { icon: Compass, text: "Book the cheapest available room." },
  { icon: Utensils, text: "What dining options and restaurants do you offer?" },
  { icon: Clock, text: "What time is check-in and check-out?" },
  { icon: HelpCircle, text: "Can you share the price details for my booking?" }
];

export default function AiConciergeSection({
  isVoiceActive,
  isMuted,
  audioLevel = 0,
  sessionState = 'IDLE',
  conversation = [],
  partialTranscript = null,
  isThinking = false,
  voiceError = null,
  onStartVoice,
  onStopVoice,
  onToggleMute,
  onClearConversation,
  onSendTextTurn
}) {
  const scrollRef = useRef(null);

  // Auto-scroll conversation to bottom as new messages arrive
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [conversation, partialTranscript, isThinking]);

  const getStateBadge = () => {
    switch (sessionState) {
      case 'LISTENING':
        return { label: 'Listening to Guest...', color: '#38BDF8', bg: 'rgba(56, 189, 248, 0.15)', border: 'rgba(56, 189, 248, 0.35)' };
      case 'THINKING':
        return { label: 'Concierge Thinking...', color: '#FCE09B', bg: 'rgba(212, 175, 55, 0.15)', border: 'rgba(212, 175, 55, 0.35)' };
      case 'SPEAKING':
        return { label: 'Rachel is Speaking...', color: '#4ADE80', bg: 'rgba(74, 222, 128, 0.15)', border: 'rgba(74, 222, 128, 0.35)' };
      case 'BARGED_IN':
        return { label: 'Guest Speaking...', color: '#F43F5E', bg: 'rgba(244, 63, 94, 0.15)', border: 'rgba(244, 63, 94, 0.35)' };
      default:
        return { label: 'Ready to Assist', color: '#94A3B8', bg: 'rgba(255, 255, 255, 0.05)', border: 'rgba(255, 255, 255, 0.1)' };
    }
  };

  const statusBadge = getStateBadge();

  return (
    <section id="ai-concierge" style={{ padding: '80px 24px', maxWidth: '1440px', margin: '0 auto' }}>
      {/* Section Header */}
      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', textAlign: 'center', marginBottom: '40px' }}>
        <span className="section-tag">24/7 GUEST SERVICE</span>
        <h2 className="section-title">
          Azure <span className="gold-gradient-text">AI Concierge</span>
        </h2>
        <p className="section-desc">
          Your personal resort assistant. Ask Rachel about room reservations, live rates, dining, resort amenities, and Hawaiian excursions.
        </p>

        {/* Guest Guide Pill */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '12px',
            flexWrap: 'wrap',
            justifyContent: 'center',
            marginTop: '18px',
            padding: '10px 20px',
            borderRadius: '9999px',
            background: 'rgba(6, 21, 31, 0.7)',
            backdropFilter: 'blur(10px)',
            border: '1px solid rgba(212, 175, 55, 0.25)',
            fontSize: '12px',
            color: '#CBD5E1'
          }}
        >
          <span style={{ color: '#FCE09B', fontWeight: 600 }}>Ask about:</span>
          <span>Rooms</span>
          <span>•</span>
          <span>Availability</span>
          <span>•</span>
          <span>Pricing</span>
          <span>•</span>
          <span>Dining</span>
          <span>•</span>
          <span>Resort Activities</span>
          <span>•</span>
          <span>Amenities</span>
          <span>•</span>
          <span>Booking</span>
        </div>
      </div>

      {/* Main Concierge Interface Panel */}
      <div
        className="glass-panel ai-concierge-grid"
        style={{
          display: 'grid',
          gridTemplateColumns: 'minmax(300px, 380px) 1fr',
          gap: '24px',
          padding: '28px',
          borderRadius: '28px',
          background: 'rgba(8, 26, 38, 0.88)'
        }}
      >
        {/* Left Column: Voice Call Controls & Audio Status */}
        <div
          style={{
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            padding: '32px 24px',
            borderRadius: '22px',
            background: 'rgba(6, 21, 31, 0.7)',
            border: '1px solid rgba(255, 255, 255, 0.08)',
            textAlign: 'center',
            position: 'relative'
          }}
        >
          {/* Status Badge */}
          <div
            style={{
              padding: '6px 16px',
              borderRadius: '9999px',
              fontSize: '12px',
              fontWeight: 600,
              color: statusBadge.color,
              background: statusBadge.bg,
              border: `1px solid ${statusBadge.border}`,
              marginBottom: '28px',
              display: 'inline-flex',
              alignItems: 'center',
              gap: '6px'
            }}
          >
            <span
              style={{
                width: '7px',
                height: '7px',
                borderRadius: '50%',
                background: statusBadge.color,
                boxShadow: isVoiceActive ? `0 0 10px ${statusBadge.color}` : 'none'
              }}
            />
            <span>{statusBadge.label}</span>
          </div>

          {/* Animated Avatar / Audio Ring */}
          <div
            style={{
              position: 'relative',
              width: '150px',
              height: '150px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              marginBottom: '28px'
            }}
          >
            {/* Outer Pulsing Wave Ring */}
            {isVoiceActive && (
              <div
                style={{
                  position: 'absolute',
                  inset: 0,
                  borderRadius: '50%',
                  border: `2px solid ${statusBadge.color}`,
                  transform: `scale(${1 + Math.min(audioLevel * 0.4, 0.35)})`,
                  opacity: Math.max(0.3, audioLevel),
                  transition: 'transform 0.1s ease, opacity 0.1s ease',
                  boxShadow: `0 0 25px ${statusBadge.color}`
                }}
              />
            )}

            {/* Inner Concierge Crest */}
            <div
              style={{
                width: '120px',
                height: '120px',
                borderRadius: '50%',
                background: isVoiceActive
                  ? 'linear-gradient(135deg, rgba(2, 132, 199, 0.35) 0%, rgba(212, 175, 55, 0.35) 100%)'
                  : 'rgba(255, 255, 255, 0.05)',
                border: isVoiceActive
                  ? '2px solid rgba(212, 175, 55, 0.6)'
                  : '1px solid rgba(255, 255, 255, 0.15)',
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                justifyContent: 'center',
                color: '#FFFFFF',
                boxShadow: '0 10px 30px rgba(0, 0, 0, 0.5)'
              }}
            >
              <Sparkles size={32} style={{ color: '#FCE09B', marginBottom: '4px' }} />
              <span className="font-brand" style={{ fontSize: '14px', fontWeight: 600 }}>Rachel</span>
              <span style={{ fontSize: '10px', color: '#94A3B8' }}>Resort Host</span>
            </div>
          </div>

          {/* Error Message if Mic access failed */}
          {voiceError && (
            <div
              style={{
                color: '#FDA4AF',
                background: 'rgba(244, 63, 94, 0.15)',
                border: '1px solid rgba(244, 63, 94, 0.3)',
                padding: '8px 12px',
                borderRadius: '8px',
                fontSize: '12px',
                marginBottom: '18px'
              }}
            >
              {voiceError}
            </div>
          )}

          {/* Primary Action Button */}
          {!isVoiceActive ? (
            <button
              onClick={onStartVoice}
              className="btn-gold"
              style={{
                width: '100%',
                padding: '16px',
                fontSize: '15px',
                fontWeight: 600,
                boxShadow: '0 8px 30px rgba(212, 175, 55, 0.35)'
              }}
            >
              <PhoneCall size={18} />
              <span>Talk to AI Concierge</span>
            </button>
          ) : (
            <div style={{ display: 'flex', gap: '10px', width: '100%' }}>
              <button
                onClick={onToggleMute}
                style={{
                  flex: 1,
                  padding: '14px',
                  borderRadius: '9999px',
                  background: isMuted ? 'rgba(244, 63, 94, 0.2)' : 'rgba(255, 255, 255, 0.1)',
                  border: isMuted ? '1px solid rgba(244, 63, 94, 0.4)' : '1px solid rgba(255, 255, 255, 0.2)',
                  color: isMuted ? '#FDA4AF' : '#FFFFFF',
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: '6px',
                  fontSize: '13px',
                  fontWeight: 600
                }}
              >
                {isMuted ? <MicOff size={16} /> : <Mic size={16} />}
                <span>{isMuted ? 'Unmute' : 'Mute'}</span>
              </button>

              <button
                onClick={onStopVoice}
                style={{
                  flex: 1,
                  padding: '14px',
                  borderRadius: '9999px',
                  background: 'rgba(244, 63, 94, 0.25)',
                  border: '1px solid rgba(244, 63, 94, 0.5)',
                  color: '#FECDD3',
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: '6px',
                  fontSize: '13px',
                  fontWeight: 600
                }}
              >
                <PhoneOff size={16} />
                <span>End Call</span>
              </button>
            </div>
          )}

          {/* Reset Conversation Button */}
          <button
            onClick={onClearConversation}
            style={{
              background: 'transparent',
              border: 'none',
              color: '#94A3B8',
              fontSize: '12px',
              cursor: 'pointer',
              display: 'inline-flex',
              alignItems: 'center',
              gap: '6px',
              marginTop: '16px',
              padding: '6px 12px',
              borderRadius: '6px',
              transition: 'color 0.2s ease'
            }}
            onMouseEnter={(e) => (e.currentTarget.style.color = '#FCE09B')}
            onMouseLeave={(e) => (e.currentTarget.style.color = '#94A3B8')}
          >
            <RotateCcw size={12} />
            <span>Reset Conversation</span>
          </button>
        </div>

        {/* Right Column: Live Conversation Stream & Quick Prompts */}
        <div style={{ display: 'flex', flexDirection: 'column', height: '520px' }}>
          {/* Stream Header */}
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              paddingBottom: '16px',
              borderBottom: '1px solid rgba(255, 255, 255, 0.08)',
              marginBottom: '16px'
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <Volume2 size={16} style={{ color: '#38BDF8' }} />
              <span style={{ fontSize: '14px', fontWeight: 600, color: '#FFFFFF' }}>
                Live Concierge Conversation
              </span>
            </div>
            <span style={{ fontSize: '11px', color: '#64748B' }}>
              Live Voice & Guest Assistant
            </span>
          </div>

          {/* Chat Bubble Stream Body */}
          <div
            ref={scrollRef}
            style={{
              flex: 1,
              overflowY: 'auto',
              paddingRight: '8px',
              display: 'flex',
              flexDirection: 'column',
              gap: '14px'
            }}
          >
            {conversation.length === 0 && !partialTranscript && (
              <div
                style={{
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: 'center',
                  justifyContent: 'center',
                  height: '100%',
                  color: '#64748B',
                  textAlign: 'center',
                  padding: '30px'
                }}
              >
                <div
                  style={{
                    width: '48px',
                    height: '48px',
                    borderRadius: '50%',
                    background: 'rgba(255, 255, 255, 0.04)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    color: '#94A3B8',
                    marginBottom: '12px'
                  }}
                >
                  <Sparkles size={20} />
                </div>
                <p style={{ fontSize: '14px', color: '#CBD5E1', marginBottom: '6px' }}>
                  Rachel is ready to welcome you.
                </p>
                <p style={{ fontSize: '12px', maxWidth: '380px' }}>
                  Tap "Talk to AI Concierge" above or choose a suggested question below to start your conversation.
                </p>
              </div>
            )}

            {/* Conversation History Messages */}
            {conversation.map((msg, i) => {
              const isUser = msg.role === 'user';
              return (
                <div
                  key={msg.turn_id || i}
                  style={{
                    display: 'flex',
                    flexDirection: 'column',
                    alignItems: isUser ? 'flex-end' : 'flex-start'
                  }}
                >
                  <div
                    style={{
                      fontSize: '11px',
                      color: isUser ? '#38BDF8' : '#FCE09B',
                      fontWeight: 600,
                      marginBottom: '4px',
                      paddingLeft: '4px',
                      paddingRight: '4px'
                    }}
                  >
                    {isUser ? 'You (Guest)' : 'Rachel (Concierge)'}
                  </div>
                  <div
                    style={{
                      maxWidth: '82%',
                      padding: '12px 18px',
                      borderRadius: isUser ? '18px 18px 4px 18px' : '18px 18px 18px 4px',
                      background: isUser
                        ? 'linear-gradient(135deg, rgba(2, 132, 199, 0.4) 0%, rgba(14, 116, 144, 0.4) 100%)'
                        : 'rgba(255, 255, 255, 0.07)',
                      border: isUser
                        ? '1px solid rgba(56, 189, 248, 0.35)'
                        : '1px solid rgba(255, 255, 255, 0.1)',
                      color: '#FFFFFF',
                      fontSize: '14px',
                      lineHeight: 1.6,
                      boxShadow: '0 4px 15px rgba(0, 0, 0, 0.3)'
                    }}
                  >
                    {msg.content}
                  </div>
                </div>
              );
            })}

            {/* Live Partial Interim User Speech */}
            {partialTranscript && (
              <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end' }}>
                <div style={{ fontSize: '11px', color: '#38BDF8', fontWeight: 600, marginBottom: '4px' }}>
                  You (Speaking...)
                </div>
                <div
                  style={{
                    maxWidth: '82%',
                    padding: '12px 18px',
                    borderRadius: '18px 18px 4px 18px',
                    background: 'rgba(56, 189, 248, 0.15)',
                    border: '1px dashed rgba(56, 189, 248, 0.5)',
                    color: '#BAE6FD',
                    fontSize: '14px',
                    fontStyle: 'italic'
                  }}
                >
                  {partialTranscript.content}
                </div>
              </div>
            )}

            {/* Thinking / Synthesizing Indicator */}
            {isThinking && (
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', padding: '8px' }}>
                <div style={{ width: '8px', height: '8px', borderRadius: '50%', background: '#FCE09B', animation: 'pulse 1s infinite' }} />
                <span style={{ fontSize: '12px', color: '#FCE09B', fontStyle: 'italic' }}>
                  Rachel is preparing your response...
                </span>
              </div>
            )}
          </div>

          {/* Quick Suggested Inquiries Row */}
          <div
            style={{
              paddingTop: '16px',
              borderTop: '1px solid rgba(255, 255, 255, 0.08)',
              marginTop: '12px'
            }}
          >
            <div style={{ fontSize: '11px', color: '#94A3B8', marginBottom: '8px', fontWeight: 500 }}>
              Quick Guest Prompts:
            </div>
            <div
              style={{
                display: 'flex',
                gap: '8px',
                overflowX: 'auto',
                paddingBottom: '4px'
              }}
            >
              {SUGGESTED_QUESTIONS.map((q, idx) => {
                const IconComponent = q.icon;
                return (
                  <button
                    key={idx}
                    onClick={() => onSendTextTurn(q.text)}
                    style={{
                      background: 'rgba(255, 255, 255, 0.05)',
                      border: '1px solid rgba(255, 255, 255, 0.12)',
                      color: '#E2E8F0',
                      borderRadius: '9999px',
                      padding: '6px 14px',
                      fontSize: '12px',
                      cursor: 'pointer',
                      whiteSpace: 'nowrap',
                      display: 'flex',
                      alignItems: 'center',
                      gap: '6px',
                      transition: 'all 0.2s ease',
                      flexShrink: 0
                    }}
                    onMouseEnter={(e) => {
                      e.currentTarget.style.background = 'rgba(212, 175, 55, 0.15)';
                      e.currentTarget.style.borderColor = 'rgba(212, 175, 55, 0.4)';
                      e.currentTarget.style.color = '#FCE09B';
                    }}
                    onMouseLeave={(e) => {
                      e.currentTarget.style.background = 'rgba(255, 255, 255, 0.05)';
                      e.currentTarget.style.borderColor = 'rgba(255, 255, 255, 0.12)';
                      e.currentTarget.style.color = '#E2E8F0';
                    }}
                  >
                    <IconComponent size={12} style={{ color: '#D4AF37' }} />
                    <span>{q.text}</span>
                  </button>
                );
              })}
            </div>
          </div>
        </div>
      </div>

      <style>{`
        @media (max-width: 900px) {
          .ai-concierge-grid {
            grid-template-columns: 1fr !important;
          }
        }
      `}</style>
    </section>
  );
}
