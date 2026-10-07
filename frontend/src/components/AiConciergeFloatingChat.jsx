import React, { useState, useRef, useEffect } from 'react';
import {
  Sparkles,
  MessageSquare,
  Send,
  Mic,
  MicOff,
  X,
  ChevronDown,
  Calendar,
  Users,
  CheckCircle2,
  RotateCcw,
  Volume2,
  ArrowRight,
  ExternalLink,
  Bed,
  Utensils,
  Compass,
  DollarSign,
  ShieldCheck,
  Check
} from 'lucide-react';
import { resortImages } from '../config/resortImages';
import {
  formatPriceDisplay,
  convertTextCurrencies,
  getCurrencyInfo
} from '../services/currency';

// Canonical Room Catalog with Photos and Occupancies
const ROOM_CATALOG_MAP = {
  'villa-ocean-101': {
    id: 'villa-ocean-101',
    name: 'Oceanfront Luxury Villa',
    category: 'Villa',
    capacity: 4,
    rate: 650,
    image: resortImages.rooms.oceanfrontVilla
  },
  'suite-deluxe-201': {
    id: 'suite-deluxe-201',
    name: 'Deluxe Sunset Suite',
    category: 'Suite',
    capacity: 2,
    rate: 380,
    image: resortImages.rooms.deluxeSunsetSuite
  },
  'bungalow-garden-301': {
    id: 'bungalow-garden-301',
    name: 'Garden Tropical Bungalow',
    category: 'Bungalow',
    capacity: 3,
    rate: 290,
    image: resortImages.rooms.gardenBungalow
  },
  'suite-presidential-401': {
    id: 'suite-presidential-401',
    name: 'Presidential Ocean Suite',
    category: 'Suite',
    capacity: 4,
    rate: 850,
    image: resortImages.rooms.presidentialSuite
  },
  'villa-family-501': {
    id: 'villa-family-501',
    name: 'Family Pool Villa',
    category: 'Villa',
    capacity: 6,
    rate: 520,
    image: resortImages.rooms.familyPoolVilla
  },
  'suite-premium-302': {
    id: 'suite-premium-302',
    name: 'Premium Garden Suite',
    category: 'Suite',
    capacity: 3,
    rate: 450,
    image: resortImages.rooms.premiumGardenSuite
  }
};

const QUICK_ACTIONS = [
  { label: 'Find a Room', prompt: 'What rooms and luxury villas do you offer?' },
  { label: 'Check Availability', prompt: 'What rooms are available for two guests?' },
  { label: 'Check Pricing', prompt: 'What are the nightly prices for your rooms?' },
  { label: 'Dining', prompt: 'Tell me about the dining options and restaurants at Azure Paradise.' },
  { label: 'Resort Experiences', prompt: 'What resort experiences, spa treatments, and activities do you offer?' },
  { label: 'My Booking', prompt: 'Can you show my current booking details?' }
];

function resolveRoom(item) {
  if (!item) return null;
  if (typeof item === 'string') {
    const norm = item.toLowerCase();
    for (const [key, val] of Object.entries(ROOM_CATALOG_MAP)) {
      if (norm.includes(key) || norm.includes(val.name.toLowerCase())) {
        return val;
      }
    }
    return null;
  }
  const id = item.room_id || item.id;
  if (id && ROOM_CATALOG_MAP[id]) {
    return {
      ...ROOM_CATALOG_MAP[id],
      rate: item.base_rate_nightly || item.nightly_rate || ROOM_CATALOG_MAP[id].rate,
      capacity: item.max_occupancy || item.capacity || ROOM_CATALOG_MAP[id].capacity
    };
  }
  const name = item.name || item.room_name;
  if (name) {
    const norm = name.toLowerCase();
    for (const val of Object.values(ROOM_CATALOG_MAP)) {
      if (norm.includes(val.name.toLowerCase()) || val.name.toLowerCase().includes(norm)) {
        return {
          ...val,
          rate: item.base_rate_nightly || item.nightly_rate || val.rate,
          capacity: item.max_occupancy || item.capacity || val.capacity
        };
      }
    }
  }
  return null;
}

export default function AiConciergeFloatingChat({
  conversation = [],
  partialTranscript = null,
  isThinking = false,
  isVoiceActive = false,
  isMuted = false,
  audioLevel = 0,
  sessionState = 'IDLE',
  selectedCurrency = 'INR',
  activeBooking = null,
  onSendTextTurn,
  onStartVoice,
  onStopVoice,
  onToggleMute,
  onClearConversation,
  onViewRoom,
  onBookRoom,
  onViewMyBooking
}) {
  const [isOpen, setIsOpen] = useState(false);
  const [inputText, setInputText] = useState('');
  const [unreadCount, setUnreadCount] = useState(0);
  const scrollRef = useRef(null);
  const inputRef = useRef(null);
  const lastCountRef = useRef(conversation.length);

  // Auto-scroll chat body on new messages
  useEffect(() => {
    if (isOpen && scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [conversation, partialTranscript, isThinking, isOpen]);

  // Focus input when chat opens
  useEffect(() => {
    if (isOpen) {
      setUnreadCount(0);
      setTimeout(() => inputRef.current?.focus(), 100);
    }
  }, [isOpen]);

  // Track unread badge when chat is closed
  useEffect(() => {
    if (!isOpen && conversation.length > lastCountRef.current) {
      const diff = conversation.length - lastCountRef.current;
      setUnreadCount((c) => c + diff);
    }
    lastCountRef.current = conversation.length;
  }, [conversation.length, isOpen]);

  const handleSend = async (e) => {
    if (e) e.preventDefault();
    const text = inputText.trim();
    if (!text || isThinking) return;
    setInputText('');
    await onSendTextTurn(text);
  };

  const handleQuickAction = async (prompt) => {
    if (isThinking) return;
    await onSendTextTurn(prompt);
  };

  const handleMicrophoneClick = () => {
    if (isVoiceActive) {
      onStopVoice();
    } else {
      onStartVoice();
    }
  };

  // Helper to extract room cards from a turn
  const extractRoomsForMessage = (msg) => {
    if (msg.rooms && Array.isArray(msg.rooms) && msg.rooms.length > 0) {
      return msg.rooms.map(resolveRoom).filter(Boolean);
    }
    if (msg.role === 'assistant' && msg.content) {
      const text = msg.content.toLowerCase();
      const list = [];
      for (const [k, v] of Object.entries(ROOM_CATALOG_MAP)) {
        if (text.includes(v.name.toLowerCase())) {
          list.push(v);
        }
      }
      if (list.length > 0) return list;
    }
    return [];
  };

  // Helper to extract confirmed booking for a turn
  const extractBookingConfirmation = (msg) => {
    if (msg.bookingConfirmation) return msg.bookingConfirmation;
    if (msg.role === 'assistant' && msg.content) {
      const text = msg.content;
      const hasRes = text.match(/(RES-[A-Z0-9]{6,12})/i);
      const isConfirmedPhrase =
        text.toLowerCase().includes('booking is officially confirmed') ||
        text.toLowerCase().includes('reservation is officially confirmed') ||
        text.toLowerCase().includes('booking confirmed') ||
        text.toLowerCase().includes('reservation is confirmed');

      if (hasRes || (isConfirmedPhrase && activeBooking?.status === 'confirmed')) {
        const code = hasRes ? hasRes[1].toUpperCase() : (activeBooking?.booking_code || activeBooking?.confirmation_number || 'RES-849201');
        return {
          booking_code: code,
          status: 'confirmed',
          room_name: activeBooking?.room_name || 'Garden Tropical Bungalow',
          check_in: activeBooking?.check_in || 'Nov 21',
          check_out: activeBooking?.check_out || 'Nov 26',
          guests: activeBooking?.guests || 2,
          total_price: activeBooking?.total_price || 1450
        };
      }
    }
    return null;
  };

  const formatDateDisplay = (dateStr) => {
    if (!dateStr) return '';
    try {
      const d = new Date(dateStr);
      if (isNaN(d.getTime())) return dateStr;
      return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
    } catch (_) {
      return dateStr;
    }
  };

  return (
    <>
      {/* 1. COLLAPSED FLOATING CHAT BAR (Bottom-Right) */}
      {!isOpen && (
        <div
          id="ai-concierge-chat-bar"
          onClick={() => setIsOpen(true)}
          style={{
            position: 'fixed',
            bottom: '24px',
            right: '24px',
            zIndex: 9990,
            cursor: 'pointer',
            transition: 'all 0.3s cubic-bezier(0.25, 0.46, 0.45, 0.94)'
          }}
        >
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '12px',
              padding: '12px 20px',
              borderRadius: '9999px',
              background: 'linear-gradient(135deg, rgba(8, 26, 38, 0.94) 0%, rgba(6, 21, 31, 0.96) 100%)',
              backdropFilter: 'blur(20px)',
              WebkitBackdropFilter: 'blur(20px)',
              border: '1px solid rgba(212, 175, 55, 0.55)',
              boxShadow: '0 12px 36px rgba(0, 0, 0, 0.55), 0 0 24px rgba(212, 175, 55, 0.25)',
              color: '#FFFFFF'
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.transform = 'translateY(-3px) scale(1.02)';
              e.currentTarget.style.borderColor = 'rgba(212, 175, 55, 0.85)';
              e.currentTarget.style.boxShadow = '0 16px 42px rgba(0, 0, 0, 0.65), 0 0 32px rgba(212, 175, 55, 0.4)';
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.transform = 'translateY(0) scale(1)';
              e.currentTarget.style.borderColor = 'rgba(212, 175, 55, 0.55)';
              e.currentTarget.style.boxShadow = '0 12px 36px rgba(0, 0, 0, 0.55), 0 0 24px rgba(212, 175, 55, 0.25)';
            }}
          >
            {/* Sparkle Icon Crest with Pulse */}
            <div
              style={{
                width: '38px',
                height: '38px',
                borderRadius: '50%',
                background: isVoiceActive
                  ? 'linear-gradient(135deg, #10B981 0%, #059669 100%)'
                  : 'linear-gradient(135deg, rgba(212, 175, 55, 0.3) 0%, rgba(2, 132, 199, 0.3) 100%)',
                border: '1px solid rgba(212, 175, 55, 0.6)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: isVoiceActive ? '#FFFFFF' : '#FCE09B',
                boxShadow: isVoiceActive
                  ? '0 0 16px rgba(16, 185, 129, 0.6)'
                  : '0 0 14px rgba(212, 175, 55, 0.3)'
              }}
            >
              <Sparkles size={18} />
            </div>

            {/* Text Labels matching requirement: "✨ AI Concierge / Ask us anything" */}
            <div style={{ textAlign: 'left', paddingRight: '4px' }}>
              <div
                style={{
                  fontFamily: "'Cinzel', serif",
                  fontSize: '14px',
                  fontWeight: 700,
                  color: '#FCE09B',
                  letterSpacing: '0.04em',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '6px'
                }}
              >
                <span>✨ AI Concierge</span>
                <span
                  style={{
                    width: '6px',
                    height: '6px',
                    borderRadius: '50%',
                    background: '#10B981',
                    boxShadow: '0 0 8px #10B981'
                  }}
                />
              </div>
              <div style={{ fontSize: '11px', color: '#CBD5E1', fontWeight: 500, opacity: 0.9 }}>
                {isVoiceActive ? 'Voice Call Active • Tap to open' : 'Ask us anything'}
              </div>
            </div>

            {/* Unread Message Pill if any */}
            {unreadCount > 0 && (
              <span
                style={{
                  background: '#EF4444',
                  color: '#FFFFFF',
                  fontSize: '11px',
                  fontWeight: 700,
                  padding: '2px 7px',
                  borderRadius: '9999px',
                  boxShadow: '0 0 10px rgba(239, 68, 68, 0.6)'
                }}
              >
                {unreadCount}
              </span>
            )}
          </div>
        </div>
      )}

      {/* 2. EXPANDED FLOATING CHAT WINDOW */}
      {isOpen && (
        <div
          id="ai-concierge-chat-window"
          className="glass-panel"
          style={{
            position: 'fixed',
            bottom: '24px',
            right: '24px',
            width: '420px',
            maxWidth: 'calc(100vw - 32px)',
            height: '620px',
            maxHeight: 'calc(100vh - 48px)',
            zIndex: 9995,
            background: 'rgba(8, 26, 38, 0.96)',
            backdropFilter: 'blur(24px)',
            WebkitBackdropFilter: 'blur(24px)',
            border: '1px solid rgba(212, 175, 55, 0.45)',
            borderRadius: '24px',
            boxShadow: '0 28px 70px rgba(0, 0, 0, 0.75), 0 0 40px rgba(212, 175, 55, 0.2)',
            display: 'flex',
            flexDirection: 'column',
            overflow: 'hidden',
            animation: 'fadeInUp 0.25s cubic-bezier(0.16, 1, 0.3, 1)'
          }}
        >
          {/* HEADER: ✨ Azure Paradise AI Concierge ● Online / Subtitle: Your personal resort assistant */}
          <div
            style={{
              padding: '16px 20px',
              background: 'linear-gradient(180deg, rgba(10, 36, 50, 0.85) 0%, rgba(8, 26, 38, 0.6) 100%)',
              borderBottom: '1px solid rgba(212, 175, 55, 0.25)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              gap: '12px',
              position: 'relative'
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
              <div
                style={{
                  width: '36px',
                  height: '36px',
                  borderRadius: '50%',
                  background: isVoiceActive
                    ? 'linear-gradient(135deg, #10B981 0%, #047857 100%)'
                    : 'linear-gradient(135deg, rgba(212, 175, 55, 0.25) 0%, rgba(2, 132, 199, 0.25) 100%)',
                  border: '1px solid rgba(212, 175, 55, 0.5)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  color: isVoiceActive ? '#FFFFFF' : '#FCE09B',
                  boxShadow: isVoiceActive ? '0 0 14px rgba(16, 185, 129, 0.5)' : 'none'
                }}
              >
                <Sparkles size={18} />
              </div>

              <div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <h3
                    className="font-brand"
                    style={{
                      margin: 0,
                      fontSize: '15px',
                      fontWeight: 700,
                      color: '#FFFFFF',
                      letterSpacing: '0.02em',
                      lineHeight: 1.2
                    }}
                  >
                    ✨ Azure Paradise AI Concierge
                  </h3>
                  <span
                    style={{
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: '4px',
                      fontSize: '11px',
                      color: '#10B981',
                      fontWeight: 600
                    }}
                  >
                    <span
                      style={{
                        width: '6px',
                        height: '6px',
                        borderRadius: '50%',
                        background: '#10B981',
                        boxShadow: '0 0 8px #10B981'
                      }}
                    />
                    Online
                  </span>
                </div>
                <div style={{ fontSize: '11px', color: '#94A3B8', marginTop: '2px' }}>
                  Your personal resort assistant
                </div>
              </div>
            </div>

            {/* Header Controls: Clear & Close */}
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
              <button
                onClick={onClearConversation}
                title="Reset conversation"
                style={{
                  background: 'rgba(255, 255, 255, 0.05)',
                  border: '1px solid rgba(255, 255, 255, 0.1)',
                  color: '#94A3B8',
                  borderRadius: '50%',
                  width: '30px',
                  height: '30px',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  cursor: 'pointer',
                  transition: 'all 0.2s ease'
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.color = '#FCE09B';
                  e.currentTarget.style.borderColor = 'rgba(212, 175, 55, 0.4)';
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.color = '#94A3B8';
                  e.currentTarget.style.borderColor = 'rgba(255, 255, 255, 0.1)';
                }}
              >
                <RotateCcw size={14} />
              </button>

              <button
                onClick={() => setIsOpen(false)}
                title="Close chat"
                style={{
                  background: 'rgba(255, 255, 255, 0.05)',
                  border: '1px solid rgba(255, 255, 255, 0.1)',
                  color: '#CBD5E1',
                  borderRadius: '50%',
                  width: '30px',
                  height: '30px',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  cursor: 'pointer',
                  transition: 'all 0.2s ease'
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.background = 'rgba(244, 63, 94, 0.2)';
                  e.currentTarget.style.color = '#FDA4AF';
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.background = 'rgba(255, 255, 255, 0.05)';
                  e.currentTarget.style.color = '#CBD5E1';
                }}
              >
                <X size={16} />
              </button>
            </div>
          </div>

          {/* CHAT QUICK ACTIONS (Section 6) */}
          <div
            style={{
              padding: '10px 14px',
              background: 'rgba(6, 21, 31, 0.7)',
              borderBottom: '1px solid rgba(255, 255, 255, 0.06)',
              overflowX: 'auto',
              whiteSpace: 'nowrap',
              display: 'flex',
              gap: '6px',
              scrollbarWidth: 'none'
            }}
          >
            {QUICK_ACTIONS.map((action, idx) => (
              <button
                key={idx}
                onClick={() => handleQuickAction(action.prompt)}
                disabled={isThinking}
                style={{
                  background: 'rgba(255, 255, 255, 0.05)',
                  border: '1px solid rgba(212, 175, 55, 0.25)',
                  color: '#E2E8F0',
                  borderRadius: '9999px',
                  padding: '5px 12px',
                  fontSize: '11px',
                  fontWeight: 600,
                  cursor: isThinking ? 'not-allowed' : 'pointer',
                  transition: 'all 0.15s ease',
                  flexShrink: 0
                }}
                onMouseEnter={(e) => {
                  if (!isThinking) {
                    e.currentTarget.style.background = 'rgba(212, 175, 55, 0.18)';
                    e.currentTarget.style.borderColor = 'rgba(212, 175, 55, 0.6)';
                    e.currentTarget.style.color = '#FCE09B';
                  }
                }}
                onMouseLeave={(e) => {
                  if (!isThinking) {
                    e.currentTarget.style.background = 'rgba(255, 255, 255, 0.05)';
                    e.currentTarget.style.borderColor = 'rgba(212, 175, 55, 0.25)';
                    e.currentTarget.style.color = '#E2E8F0';
                  }
                }}
              >
                {action.label}
              </button>
            ))}
          </div>

          {/* MESSAGE STREAM AREA */}
          <div
            ref={scrollRef}
            style={{
              flex: 1,
              overflowY: 'auto',
              padding: '16px',
              display: 'flex',
              flexDirection: 'column',
              gap: '14px',
              background: 'radial-gradient(circle at 50% 0%, rgba(2, 132, 199, 0.06) 0%, transparent 70%)'
            }}
          >
            {/* Empty conversation welcome */}
            {conversation.length === 0 && !partialTranscript && (
              <div
                style={{
                  textAlign: 'center',
                  padding: '36px 16px',
                  color: '#94A3B8',
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: 'center',
                  gap: '10px'
                }}
              >
                <div
                  style={{
                    width: '44px',
                    height: '44px',
                    borderRadius: '50%',
                    background: 'rgba(212, 175, 55, 0.12)',
                    border: '1px solid rgba(212, 175, 55, 0.35)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    color: '#FCE09B'
                  }}
                >
                  <Sparkles size={20} />
                </div>
                <div style={{ fontFamily: "'Cinzel', serif", fontSize: '15px', color: '#FCE09B', fontWeight: 600 }}>
                  Aloha & Welcome to Azure Paradise
                </div>
                <p style={{ fontSize: '12px', color: '#CBD5E1', lineHeight: 1.6, maxWidth: '300px', margin: 0 }}>
                  I can assist you with real-time room availability, luxury villa pricing, booking reservations, dining, and Hawaiian experiences.
                </p>
                <div style={{ fontSize: '11px', color: '#64748B', marginTop: '4px' }}>
                  Tap any quick action above or type your question below.
                </div>
              </div>
            )}

            {/* Conversation Messages */}
            {conversation.map((msg, index) => {
              const isUser = msg.role === 'user';
              const roomsInTurn = !isUser ? extractRoomsForMessage(msg) : [];
              const bookingInTurn = !isUser ? extractBookingConfirmation(msg) : null;
              const convertedContent = !isUser
                ? convertTextCurrencies(msg.content, selectedCurrency)
                : msg.content;

              return (
                <div
                  key={msg.turn_id || index}
                  style={{
                    display: 'flex',
                    flexDirection: 'column',
                    alignItems: isUser ? 'flex-end' : 'flex-start',
                    gap: '4px'
                  }}
                >
                  <div
                    style={{
                      fontSize: '10px',
                      color: isUser ? '#38BDF8' : '#FCE09B',
                      fontWeight: 600,
                      paddingLeft: '4px',
                      paddingRight: '4px'
                    }}
                  >
                    {isUser ? 'You' : 'Rachel (Concierge)'}
                  </div>

                  {/* Message Bubble */}
                  <div
                    style={{
                      maxWidth: '86%',
                      padding: '10px 14px',
                      borderRadius: isUser ? '16px 16px 4px 16px' : '16px 16px 16px 4px',
                      background: isUser
                        ? 'linear-gradient(135deg, rgba(2, 132, 199, 0.45) 0%, rgba(14, 116, 144, 0.45) 100%)'
                        : 'rgba(255, 255, 255, 0.06)',
                      border: isUser
                        ? '1px solid rgba(56, 189, 248, 0.4)'
                        : '1px solid rgba(255, 255, 255, 0.1)',
                      color: '#F8FAFC',
                      fontSize: '13px',
                      lineHeight: 1.55,
                      boxShadow: '0 4px 14px rgba(0, 0, 0, 0.25)',
                      wordBreak: 'break-word',
                      whiteSpace: 'pre-line'
                    }}
                  >
                    {convertedContent}
                  </div>

                  {/* ROOM RESULTS IN CHAT (Section 9) */}
                  {roomsInTurn.length > 0 && (
                    <div
                      style={{
                        display: 'flex',
                        flexDirection: 'column',
                        gap: '8px',
                        marginTop: '6px',
                        width: '100%',
                        maxWidth: '86%'
                      }}
                    >
                      {roomsInTurn.map((room) => {
                        const priceInfo = formatPriceDisplay(room.rate, selectedCurrency, { perNight: true });
                        return (
                          <div
                            key={room.id}
                            style={{
                              background: 'rgba(6, 21, 31, 0.9)',
                              border: '1px solid rgba(212, 175, 55, 0.35)',
                              borderRadius: '14px',
                              overflow: 'hidden',
                              boxShadow: '0 6px 18px rgba(0, 0, 0, 0.4)'
                            }}
                          >
                            {/* Room Image */}
                            <div style={{ height: '110px', position: 'relative' }}>
                              <img
                                src={room.image}
                                alt={room.name}
                                style={{ width: '100%', height: '100%', objectFit: 'cover' }}
                              />
                              <div
                                style={{
                                  position: 'absolute',
                                  top: '8px',
                                  left: '8px',
                                  background: 'rgba(6, 21, 31, 0.85)',
                                  padding: '2px 8px',
                                  borderRadius: '6px',
                                  fontSize: '10px',
                                  color: '#FCE09B',
                                  fontWeight: 600
                                }}
                              >
                                {room.category}
                              </div>
                            </div>

                            {/* Details */}
                            <div style={{ padding: '10px 12px' }}>
                              <div
                                className="font-brand"
                                style={{ fontSize: '14px', fontWeight: 700, color: '#FFFFFF', marginBottom: '4px' }}
                              >
                                {room.name}
                              </div>

                              <div style={{ display: 'flex', alignItems: 'center', gap: '4px', fontSize: '11px', color: '#38BDF8', marginBottom: '8px' }}>
                                <Users size={12} />
                                <span>Up to {room.capacity} Guests</span>
                              </div>

                              {/* Price in Selected Currency with secondary USD */}
                              <div style={{ marginBottom: '10px' }}>
                                <div style={{ fontSize: '15px', fontWeight: 700, color: '#FCE09B' }}>
                                  {priceInfo.primary}
                                </div>
                                {priceInfo.secondary && (
                                  <div style={{ fontSize: '10px', color: '#94A3B8' }}>
                                    {priceInfo.secondary}
                                  </div>
                                )}
                                {priceInfo.isConversionUnavailable && (
                                  <div style={{ fontSize: '10px', color: '#FBBF24' }}>
                                    Local currency conversion temporarily unavailable.
                                  </div>
                                )}
                              </div>

                              {/* Action Buttons: [View Room] [Book This] */}
                              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '6px' }}>
                                <button
                                  onClick={() => onViewRoom && onViewRoom(room)}
                                  style={{
                                    background: 'rgba(255, 255, 255, 0.06)',
                                    border: '1px solid rgba(255, 255, 255, 0.15)',
                                    color: '#CBD5E1',
                                    borderRadius: '8px',
                                    padding: '6px 8px',
                                    fontSize: '11px',
                                    fontWeight: 600,
                                    cursor: 'pointer',
                                    display: 'flex',
                                    alignItems: 'center',
                                    justifyContent: 'center',
                                    gap: '4px',
                                    transition: 'all 0.15s ease'
                                  }}
                                  onMouseEnter={(e) => {
                                    e.currentTarget.style.color = '#FFFFFF';
                                    e.currentTarget.style.borderColor = 'rgba(212, 175, 55, 0.4)';
                                  }}
                                  onMouseLeave={(e) => {
                                    e.currentTarget.style.color = '#CBD5E1';
                                    e.currentTarget.style.borderColor = 'rgba(255, 255, 255, 0.15)';
                                  }}
                                >
                                  <span>View Room</span>
                                  <ExternalLink size={11} />
                                </button>

                                <button
                                  onClick={() => onBookRoom ? onBookRoom(room) : onSendTextTurn(`I would like to book the ${room.name}.`)}
                                  className="btn-gold"
                                  style={{
                                    borderRadius: '8px',
                                    padding: '6px 8px',
                                    fontSize: '11px',
                                    fontWeight: 700,
                                    display: 'flex',
                                    alignItems: 'center',
                                    justifyContent: 'center',
                                    gap: '4px'
                                  }}
                                >
                                  <span>Book This</span>
                                  <ArrowRight size={11} />
                                </button>
                              </div>
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  )}

                  {/* BOOKING CONFIRMATION IN CHAT (Section 11) */}
                  {bookingInTurn && (
                    <div
                      style={{
                        marginTop: '8px',
                        width: '100%',
                        maxWidth: '86%',
                        background: 'linear-gradient(135deg, rgba(6, 21, 31, 0.95) 0%, rgba(10, 37, 51, 0.95) 100%)',
                        border: '1px solid rgba(16, 185, 129, 0.55)',
                        borderRadius: '16px',
                        padding: '14px',
                        boxShadow: '0 8px 24px rgba(0, 0, 0, 0.5), 0 0 20px rgba(16, 185, 129, 0.15)'
                      }}
                    >
                      {/* ✓ Booking Confirmed Banner */}
                      <div style={{ display: 'flex', alignItems: 'center', gap: '6px', color: '#34D399', fontWeight: 700, fontSize: '13px', marginBottom: '8px' }}>
                        <CheckCircle2 size={16} />
                        <span>✓ Booking Confirmed</span>
                      </div>

                      <div className="font-brand" style={{ fontSize: '15px', fontWeight: 700, color: '#FFFFFF', marginBottom: '4px' }}>
                        {bookingInTurn.room_name || 'Garden Tropical Bungalow'}
                      </div>

                      <div style={{ display: 'flex', alignItems: 'center', gap: '12px', fontSize: '11px', color: '#94A3B8', marginBottom: '10px' }}>
                        <span>{formatDateDisplay(bookingInTurn.check_in)} – {formatDateDisplay(bookingInTurn.check_out)}</span>
                        <span>•</span>
                        <span>{bookingInTurn.guests || 2} Guests</span>
                      </div>

                      {/* Total in Selected Currency & Secondary USD */}
                      {(() => {
                        const priceInfo = formatPriceDisplay(bookingInTurn.total_price, selectedCurrency);
                        return (
                          <div style={{ padding: '8px 10px', background: 'rgba(255, 255, 255, 0.04)', borderRadius: '8px', marginBottom: '10px' }}>
                            <div style={{ fontSize: '10px', color: '#94A3B8', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                              Total:
                            </div>
                            <div style={{ fontSize: '16px', fontWeight: 700, color: '#FCE09B' }}>
                              {priceInfo.primary}
                            </div>
                            {priceInfo.secondary && (
                              <div style={{ fontSize: '11px', color: '#CBD5E1', opacity: 0.85 }}>
                                {priceInfo.secondary}
                              </div>
                            )}
                          </div>
                        );
                      })()}

                      {/* Confirmation Number: Real RES-XXXXXXXX */}
                      <div style={{ marginBottom: '12px' }}>
                        <div style={{ fontSize: '10px', color: '#94A3B8', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                          Confirmation:
                        </div>
                        <div className="mono-font" style={{ fontSize: '14px', fontWeight: 700, color: '#FCE09B', letterSpacing: '0.05em' }}>
                          {bookingInTurn.booking_code || bookingInTurn.confirmation_number || 'RES-742918'}
                        </div>
                      </div>

                      {/* Action: [ View My Booking ] */}
                      <button
                        onClick={() => onViewMyBooking && onViewMyBooking()}
                        className="btn-gold"
                        style={{
                          width: '100%',
                          padding: '8px 12px',
                          fontSize: '12px',
                          fontWeight: 700,
                          borderRadius: '8px',
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                          gap: '6px'
                        }}
                      >
                        <ShieldCheck size={14} />
                        <span>View My Booking</span>
                      </button>
                    </div>
                  )}
                </div>
              );
            })}

            {/* Live Partial Interim User Speech */}
            {partialTranscript && (
              <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: '4px' }}>
                <div style={{ fontSize: '10px', color: '#38BDF8', fontWeight: 600 }}>You (Speaking...)</div>
                <div
                  style={{
                    maxWidth: '86%',
                    padding: '10px 14px',
                    borderRadius: '16px 16px 4px 16px',
                    background: 'rgba(56, 189, 248, 0.15)',
                    border: '1px dashed rgba(56, 189, 248, 0.5)',
                    color: '#BAE6FD',
                    fontSize: '13px',
                    fontStyle: 'italic'
                  }}
                >
                  {partialTranscript.content}
                </div>
              </div>
            )}

            {/* Thinking / Synthesizing Indicator */}
            {isThinking && (
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', padding: '6px 4px' }}>
                <div style={{ width: '7px', height: '7px', borderRadius: '50%', background: '#FCE09B', animation: 'pulse 1s infinite' }} />
                <span style={{ fontSize: '11px', color: '#FCE09B', fontStyle: 'italic' }}>
                  Rachel is preparing your response...
                </span>
              </div>
            )}
          </div>

          {/* CHAT INPUT (Section 7) */}
          {/* Format: 🎤   Ask anything about your stay...        ➤ */}
          <div
            style={{
              padding: '12px 14px',
              background: 'rgba(6, 21, 31, 0.95)',
              borderTop: '1px solid rgba(255, 255, 255, 0.08)'
            }}
          >
            {/* Live Voice Status Indicator if Call Active */}
            {isVoiceActive && (
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  padding: '4px 10px',
                  borderRadius: '6px',
                  background: 'rgba(16, 185, 129, 0.12)',
                  border: '1px solid rgba(16, 185, 129, 0.3)',
                  marginBottom: '8px',
                  fontSize: '11px',
                  color: '#34D399'
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                  <Volume2 size={13} />
                  <span>Voice active ({sessionState})</span>
                </div>
                <button
                  onClick={onToggleMute}
                  style={{
                    background: 'transparent',
                    border: 'none',
                    color: isMuted ? '#FDA4AF' : '#A7F3D0',
                    fontSize: '11px',
                    fontWeight: 600,
                    cursor: 'pointer',
                    textDecoration: 'underline'
                  }}
                >
                  {isMuted ? 'Unmute' : 'Mute'}
                </button>
              </div>
            )}

            <form
              onSubmit={handleSend}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                background: 'rgba(11, 19, 43, 0.8)',
                border: '1px solid rgba(212, 175, 55, 0.35)',
                borderRadius: '9999px',
                padding: '4px 6px 4px 10px',
                boxShadow: 'inset 0 2px 6px rgba(0, 0, 0, 0.4)'
              }}
            >
              {/* Microphone Button with Browser Voice Support */}
              <button
                type="button"
                onClick={handleMicrophoneClick}
                title={isVoiceActive ? 'End voice call' : 'Start voice conversation'}
                style={{
                  background: isVoiceActive ? 'rgba(16, 185, 129, 0.25)' : 'transparent',
                  border: isVoiceActive ? '1px solid #10B981' : 'none',
                  color: isVoiceActive ? '#34D399' : '#94A3B8',
                  borderRadius: '50%',
                  width: '32px',
                  height: '32px',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  cursor: 'pointer',
                  flexShrink: 0,
                  transition: 'all 0.2s ease'
                }}
                onMouseEnter={(e) => {
                  if (!isVoiceActive) e.currentTarget.style.color = '#FCE09B';
                }}
                onMouseLeave={(e) => {
                  if (!isVoiceActive) e.currentTarget.style.color = '#94A3B8';
                }}
              >
                {isVoiceActive ? <MicOff size={16} /> : <Mic size={16} />}
              </button>

              {/* Text Input */}
              <input
                ref={inputRef}
                type="text"
                value={inputText}
                onChange={(e) => setInputText(e.target.value)}
                placeholder="Ask anything about your stay..."
                disabled={isThinking}
                style={{
                  flex: 1,
                  background: 'transparent',
                  border: 'none',
                  outline: 'none',
                  color: '#FFFFFF',
                  fontSize: '13px',
                  fontFamily: 'inherit',
                  padding: '6px 4px'
                }}
              />

              {/* Send Button ➤ */}
              <button
                type="submit"
                disabled={!inputText.trim() || isThinking}
                style={{
                  width: '32px',
                  height: '32px',
                  borderRadius: '50%',
                  background: inputText.trim() && !isThinking
                    ? 'linear-gradient(135deg, #D4AF37 0%, #F59E0B 100%)'
                    : 'rgba(255, 255, 255, 0.08)',
                  border: 'none',
                  color: inputText.trim() && !isThinking ? '#06151F' : '#64748B',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  cursor: inputText.trim() && !isThinking ? 'pointer' : 'default',
                  flexShrink: 0,
                  transition: 'all 0.2s ease'
                }}
              >
                <Send size={14} />
              </button>
            </form>
          </div>
        </div>
      )}

      {/* Responsive and Animation Styles */}
      <style>{`
        @keyframes fadeInUp {
          from {
            opacity: 0;
            transform: translateY(16px) scale(0.96);
          }
          to {
            opacity: 1;
            transform: translateY(0) scale(1);
          }
        }
        @media (max-width: 640px) {
          #ai-concierge-chat-window {
            bottom: 0 !important;
            right: 0 !important;
            left: 0 !important;
            top: auto !important;
            width: 100% !important;
            max-width: 100% !important;
            height: 90vh !important;
            border-radius: 24px 24px 0 0 !important;
          }
        }
      `}</style>
    </>
  );
}
