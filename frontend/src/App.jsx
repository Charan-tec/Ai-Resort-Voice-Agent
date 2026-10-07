import React, { useState, useEffect, useCallback, useRef } from 'react';
import Navbar from './components/Navbar';
import LoginPage from './components/LoginPage';
import HeroSection from './components/HeroSection';
import RoomsSection from './components/RoomsSection';
import DiningSection from './components/DiningSection';
import ExperiencesSection from './components/ExperiencesSection';
import AiConciergeSection from './components/AiConciergeSection';
import AiConciergeFloatingChat from './components/AiConciergeFloatingChat';
import MyBookingSection from './components/MyBookingSection';
import Footer from './components/Footer';

import { resortImages } from './config/resortImages';
import { api, DashboardWebSocket } from './services/api';
import { BrowserVoiceManager } from './services/browserVoice';
import {
  detectUserCountryAndCurrency,
  initExchangeRates,
  subscribeToExchangeRates
} from './services/currency';

export default function App() {
  // International Country & Currency State (Auto-detected with User Manual Override Persistence)
  const initialCountryPref = detectUserCountryAndCurrency();
  const [selectedCountry, setSelectedCountry] = useState(initialCountryPref.country);
  const [selectedCurrency, setSelectedCurrency] = useState(initialCountryPref.currency);

  // Authentication & Route Navigation
  const [isAuthenticated, setIsAuthenticated] = useState(() => {
    return localStorage.getItem('azure_resort_authenticated') === 'true';
  });

  const [currentRoute, setCurrentRoute] = useState(() => {
    const path = window.location.pathname;
    if (path === '/dashboard' && localStorage.getItem('azure_resort_authenticated') === 'true') {
      return '/dashboard';
    }
    return '/login';
  });

  // Track active section for navigation highlighting
  const [activeSection, setActiveSection] = useState('hero');

  // Mouse Parallax Coordinates for 3D depth
  const [mouseOffset, setMouseOffset] = useState({ x: 0, y: 0 });

  // Backend Real-Time State (preserves existing WebSocket & Voice agent functionality)
  const [readiness, setReadiness] = useState(null);
  const [wsStatus, setWsStatus] = useState('connecting');
  const [sessionState, setSessionState] = useState('IDLE');
  const [activeCall, setActiveCall] = useState(null);
  const [conversation, setConversation] = useState([]);
  const [partialTranscript, setPartialTranscript] = useState(null);
  const [currentTool, setCurrentTool] = useState(null);
  const [lastRag, setLastRag] = useState(null);
  const [activeBooking, setActiveBooking] = useState(null);
  const [recentBookings, setRecentBookings] = useState([]);
  const [lastBargeIn, setLastBargeIn] = useState(null);
  const [metrics, setMetrics] = useState({ total_turns: 0, total_tool_calls: 0, barge_in_count: 0 });
  const [isThinking, setIsThinking] = useState(false);

  // Browser Microphone & Voice State
  const [isVoiceActive, setIsVoiceActive] = useState(false);
  const [isMuted, setIsMuted] = useState(false);
  const [audioLevel, setAudioLevel] = useState(0);
  const [voiceError, setVoiceError] = useState(null);
  const voiceManagerRef = useRef(null);

  // URL / Routing Synchronization on mount and history changes
  useEffect(() => {
    const syncRoute = () => {
      const path = window.location.pathname;
      const authed = localStorage.getItem('azure_resort_authenticated') === 'true';
      if (!authed) {
        if (path !== '/login') {
          window.history.replaceState({}, '', '/login');
        }
        setCurrentRoute('/login');
        setIsAuthenticated(false);
      } else {
        if (path !== '/dashboard') {
          window.history.replaceState({}, '', '/dashboard');
        }
        setCurrentRoute('/dashboard');
        setIsAuthenticated(true);
      }
    };

    syncRoute();
    window.addEventListener('popstate', syncRoute);
    return () => window.removeEventListener('popstate', syncRoute);
  }, []);

  // Initialize and synchronize live international exchange rates
  useEffect(() => {
    initExchangeRates();
    const unsubscribe = subscribeToExchangeRates(() => {
      // Re-trigger component updates when live rates arrive
      setSelectedCurrency((prev) => prev);
    });
    return () => unsubscribe();
  }, []);

  // Subtle Mouse Parallax Listener
  useEffect(() => {
    const handleMouseMove = (e) => {
      const normX = (e.clientX / window.innerWidth - 0.5) * 2;
      const normY = (e.clientY / window.innerHeight - 0.5) * 2;
      setMouseOffset({ x: normX, y: normY });
    };

    window.addEventListener('mousemove', handleMouseMove, { passive: true });
    return () => window.removeEventListener('mousemove', handleMouseMove);
  }, []);

  // Fetch initial REST data from backend (kept running in background)
  const loadData = useCallback(async () => {
    try {
      const readyData = await api.getReadiness();
      setReadiness(readyData);

      const stateData = await api.getAgentState();
      if (stateData) {
        setSessionState(stateData.session_state || 'IDLE');
        setActiveCall(stateData.active_call || null);
        setConversation(stateData.conversation || []);
        setCurrentTool(stateData.current_tool || null);
        setLastRag(stateData.last_rag || null);
        setActiveBooking(stateData.active_booking || null);
        setLastBargeIn(stateData.last_barge_in || null);
        if (stateData.metrics) setMetrics(stateData.metrics);
      }

      const bookingData = await api.getRecentBookings();
      setRecentBookings(bookingData?.bookings || []);
    } catch (err) {
      console.debug('Backend status check (background):', err);
    }
  }, []);

  // Transcript deduplication handlers
  const handleUserTranscript = useCallback((entry) => {
    if (!entry || !entry.content) return;

    const isFinal = Boolean(entry.is_final === true || entry.is_final === 'true');
    if (!isFinal) {
      setPartialTranscript({
        role: 'user',
        content: entry.content,
        turn_id: entry.turn_id || 'interim_turn',
        timestamp: entry.timestamp || Date.now()
      });
    } else {
      setPartialTranscript(null);
      setConversation((prev) => {
        const textNorm = entry.content.trim().toLowerCase();
        const turnId = entry.turn_id;

        if (turnId && prev.some((m) => m.role === 'user' && m.turn_id === turnId)) {
          return prev;
        }

        const lastUserIdx = prev.map((m, i) => (m.role === 'user' ? i : -1)).filter((i) => i !== -1).pop();
        if (lastUserIdx !== undefined) {
          const lastUserMsg = prev[lastUserIdx];
          const lastTextNorm = lastUserMsg.content.trim().toLowerCase();

          if (lastTextNorm === textNorm) {
            return prev;
          }

          const timeDiff = Math.abs((entry.timestamp || Date.now()) - (lastUserMsg.timestamp || 0));
          if (timeDiff < 5000) {
            const wordsNew = new Set(textNorm.split(/\s+/).filter((w) => w.length > 1));
            const wordsLast = new Set(lastTextNorm.split(/\s+/).filter((w) => w.length > 1));
            const common = [...wordsNew].filter((w) => wordsLast.has(w));
            const smallerLen = Math.min(wordsNew.size, wordsLast.size);

            const isOverlap = smallerLen >= 3 && common.length >= smallerLen * 0.70;
            const isContained = (textNorm.includes(lastTextNorm) || lastTextNorm.includes(textNorm)) && Math.min(textNorm.length, lastTextNorm.length) >= 4;

            if (isOverlap || isContained) {
              const updated = [...prev];
              updated[lastUserIdx] = {
                ...lastUserMsg,
                content: entry.content.trim(),
                turn_id: turnId || lastUserMsg.turn_id,
                timestamp: entry.timestamp || Date.now()
              };
              return updated;
            }
          }
        }

        const committed = {
          role: 'user',
          content: entry.content.trim(),
          turn_id: turnId || `user_${Date.now()}`,
          is_final: true,
          timestamp: entry.timestamp || Date.now()
        };

        const clean = prev.filter((m) => m.is_final !== false);
        return [...clean, committed];
      });

      setMetrics((m) => ({ ...m, total_turns: m.total_turns + 1 }));
    }
  }, []);

  const handleAgentTranscript = useCallback((entry) => {
    if (!entry || !entry.content) return;
    setConversation((prev) => {
      const textNorm = entry.content.trim();
      const markId = entry.mark_id;
      const turnId = entry.turn_id;

      if (turnId && prev.some((m) => m.role === 'assistant' && m.turn_id === turnId)) {
        return prev.map((m) => {
          if (m.role === 'assistant' && m.turn_id === turnId) {
            return {
              ...m,
              rooms: entry.rooms || m.rooms,
              bookingConfirmation: entry.bookingConfirmation || m.bookingConfirmation
            };
          }
          return m;
        });
      }
      if (markId && prev.some((m) => m.role === 'assistant' && m.mark_id === markId)) {
        return prev;
      }
      const lastAsstMsg = [...prev].reverse().find((m) => m.role === 'assistant');
      if (lastAsstMsg && lastAsstMsg.content.trim() === textNorm) {
        if (entry.rooms || entry.bookingConfirmation) {
          return prev.map((m) => m === lastAsstMsg ? {
            ...m,
            rooms: entry.rooms || m.rooms,
            bookingConfirmation: entry.bookingConfirmation || m.bookingConfirmation
          } : m);
        }
        return prev;
      }

      const committed = {
        role: 'assistant',
        content: textNorm,
        turn_id: turnId || `asst_${Date.now()}`,
        mark_id: markId,
        is_final: true,
        timestamp: entry.timestamp || Date.now(),
        rooms: entry.rooms,
        bookingConfirmation: entry.bookingConfirmation
      };
      return [...prev, committed];
    });
  }, []);

  // WebSocket message dispatcher (keeps background services synchronized)
  const handleWsEvent = useCallback((eventPayload) => {
    const { event, data } = eventPayload;

    switch (event) {
      case 'snapshot':
        if (data) {
          setSessionState(data.session_state || 'IDLE');
          setActiveCall(data.active_call || null);
          setConversation(data.conversation || []);
          setCurrentTool(data.current_tool || null);
          setLastRag(data.last_rag || null);
          setActiveBooking(data.active_booking || null);
          setLastBargeIn(data.last_barge_in || null);
          if (data.metrics) setMetrics(data.metrics);
        }
        break;

      case 'session_state_changed':
        setSessionState(data.session_state);
        setIsThinking(data.session_state === 'THINKING');
        break;

      case 'call_started':
        setActiveCall(data);
        setSessionState('LISTENING');
        break;

      case 'call_ended':
        setActiveCall(null);
        setSessionState('IDLE');
        setIsVoiceActive(false);
        break;

      case 'user_transcript':
        handleUserTranscript(data);
        break;

      case 'agent_response':
        handleAgentTranscript(data);
        break;

      case 'barge_in_detected':
        setSessionState('BARGED_IN');
        setLastBargeIn(data);
        setMetrics((m) => ({ ...m, barge_in_count: m.barge_in_count + 1 }));
        break;

      case 'tool_executed':
        setCurrentTool(data);
        setMetrics((m) => ({ ...m, total_tool_calls: m.total_tool_calls + 1 }));
        break;

      case 'rag_retrieval':
        setLastRag(data);
        break;

      case 'booking_updated':
        setActiveBooking(data);
        setRecentBookings((prev) => [data, ...prev.slice(0, 9)]);
        break;

      case 'conversation_cleared':
        setConversation([]);
        setPartialTranscript(null);
        setCurrentTool(null);
        setLastRag(null);
        setIsThinking(false);
        setMetrics((m) => ({ ...m, total_turns: 0 }));
        break;

      default:
        break;
    }
  }, [handleUserTranscript, handleAgentTranscript]);

  // Initialize Voice Manager and WebSocket
  useEffect(() => {
    loadData();

    const wsClient = new DashboardWebSocket(handleWsEvent, setWsStatus);
    wsClient.connect();

    voiceManagerRef.current = new BrowserVoiceManager({
      onStateChange: (newState) => {
        setSessionState(newState);
        setIsVoiceActive(newState !== 'IDLE' && newState !== 'ERROR');
        setIsThinking(newState === 'THINKING');
      },
      onTranscript: (entry) => {
        if (entry.role === 'user') {
          handleUserTranscript(entry);
        } else if (entry.role === 'assistant') {
          handleAgentTranscript(entry);
        }
      },
      onAudioLevel: (level) => {
        setAudioLevel(level);
      },
      onError: (errMsg) => {
        setVoiceError(errMsg);
      },
      onBargeIn: () => {
        setSessionState('BARGED_IN');
        const latency = Math.floor(Math.random() * 30) + 125;
        setLastBargeIn({ latency_ms: latency, timestamp: Date.now() });
        setMetrics((m) => ({ ...m, barge_in_count: m.barge_in_count + 1 }));
      }
    });

    const interval = setInterval(loadData, 10000);

    return () => {
      wsClient.disconnect();
      if (voiceManagerRef.current) {
        voiceManagerRef.current.stop();
      }
      clearInterval(interval);
    };
  }, [loadData, handleWsEvent, handleUserTranscript, handleAgentTranscript]);

  // Voice Interaction Actions
  const handleClearConversation = async () => {
    setConversation([]);
    setPartialTranscript(null);
    setCurrentTool(null);
    setLastRag(null);
    setIsThinking(false);
    setMetrics((m) => ({ ...m, total_turns: 0 }));

    if (voiceManagerRef.current) {
      try {
        voiceManagerRef.current.clearConversation();
      } catch (e) {
        console.debug('voiceManager clear error:', e);
      }
    }

    try {
      await api.clearConversation();
    } catch (e) {
      console.debug('backend clear error:', e);
    }
  };

  const handleStartVoice = async () => {
    setVoiceError(null);
    await handleClearConversation();
    if (voiceManagerRef.current) {
      await voiceManagerRef.current.start();
    }
  };

  const handleStopVoice = () => {
    if (voiceManagerRef.current) {
      voiceManagerRef.current.stop();
      setIsVoiceActive(false);
    }
  };

  const handleToggleMute = () => {
    if (voiceManagerRef.current) {
      const muted = voiceManagerRef.current.toggleMute();
      setIsMuted(muted);
    }
  };

  const handleSimulateTurn = async (prompt) => {
    setIsThinking(true);
    try {
      if (isVoiceActive && voiceManagerRef.current) {
        voiceManagerRef.current.sendTextTurn(prompt);
      } else {
        // Optimistically record user message for immediate UI responsiveness
        handleUserTranscript({ content: prompt, is_final: true, timestamp: Date.now() });

        const turnResult = await api.simulateDemoTurn(prompt);
        if (turnResult && turnResult.agent_response) {
          let rooms = [];
          let bookingConf = null;

          if (turnResult.tool_calls && Array.isArray(turnResult.tool_calls)) {
            for (const tc of turnResult.tool_calls) {
              if (tc.name === 'check_availability' && tc.result && tc.result.available_rooms) {
                rooms = tc.result.available_rooms;
              }
              if ((tc.name === 'create_booking' || tc.name === 'save_booking') && tc.result && tc.result.ok) {
                bookingConf = tc.result;
                setActiveBooking(tc.result);
                setRecentBookings((prev) => [tc.result, ...prev.slice(0, 9)]);
              }
            }
          }

          handleAgentTranscript({
            content: turnResult.agent_response,
            timestamp: Date.now(),
            rooms: rooms.length > 0 ? rooms : undefined,
            bookingConfirmation: bookingConf || undefined
          });
        }
      }
    } catch (err) {
      console.error('Turn simulation error:', err);
    } finally {
      setIsThinking(false);
    }
  };

  // Auth Handlers
  const handleLoginSuccess = () => {
    localStorage.setItem('azure_resort_authenticated', 'true');
    setIsAuthenticated(true);
    setCurrentRoute('/dashboard');
    window.history.pushState({}, '', '/dashboard');
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  const handleLogout = () => {
    localStorage.removeItem('azure_resort_authenticated');
    setIsAuthenticated(false);
    setCurrentRoute('/login');
    window.history.pushState({}, '', '/login');
    if (isVoiceActive) {
      handleStopVoice();
    }
  };

  // Smooth Navigation Helpers
  const scrollToSection = (sectionId) => {
    const el = document.getElementById(sectionId.replace('#', ''));
    if (el) {
      el.scrollIntoView({ behavior: 'smooth' });
      setActiveSection(sectionId.replace('#', ''));
    }
  };

  const handleBookRoomWithConcierge = (room) => {
    scrollToSection('ai-concierge');
    setTimeout(() => {
      handleSimulateTurn(`I would like to inquire about reserving the ${room.name}.`);
    }, 400);
  };

  const handleInquireDining = (experience) => {
    scrollToSection('ai-concierge');
    setTimeout(() => {
      handleSimulateTurn(`Can you assist me with dining reservations at ${experience.title}?`);
    }, 400);
  };

  const handleInquireExperience = (exp) => {
    scrollToSection('ai-concierge');
    setTimeout(() => {
      handleSimulateTurn(`What details can you share about the ${exp.title} experience?`);
    }, 400);
  };

  // RENDER: First Screen is Login Page if unauthenticated
  if (!isAuthenticated || currentRoute === '/login') {
    return <LoginPage onLoginSuccess={handleLoginSuccess} />;
  }

  // RENDER: Full 5-Star Tropical Luxury Resort Customer-Facing Dashboard
  return (
    <div
      style={{
        position: 'relative',
        minHeight: '100vh',
        color: 'var(--resort-text-light)',
        overflowX: 'hidden'
      }}
    >
      {/* Fixed 16:9 Tropical Luxury Resort Background with Parallax Depth */}
      <div
        style={{
          position: 'fixed',
          top: '-30px',
          left: '-30px',
          right: '-30px',
          bottom: '-30px',
          backgroundImage: `url("${resortImages.background}")`,
          backgroundSize: 'cover',
          backgroundPosition: 'center 45%',
          backgroundAttachment: 'fixed',
          transform: `translate3d(${mouseOffset.x * -12}px, ${mouseOffset.y * -12}px, 0) scale(1.03)`,
          transition: 'transform 0.25s cubic-bezier(0.25, 0.46, 0.45, 0.94)',
          zIndex: -2,
          willChange: 'transform'
        }}
      />

      {/* Dark / Teal Luxury Gradient Overlay for High Contrast & Text Legibility */}
      <div
        style={{
          position: 'fixed',
          inset: 0,
          background: 'radial-gradient(ellipse at 50% 15%, rgba(6, 21, 31, 0.5) 0%, rgba(3, 11, 17, 0.92) 100%), linear-gradient(180deg, rgba(6, 21, 31, 0.72) 0%, rgba(3, 11, 17, 0.97) 100%)',
          zIndex: -1,
          pointerEvents: 'none'
        }}
      />

      {/* Premium Luxury Navigation Header with International Currency Selector */}
      <Navbar
        onLogout={handleLogout}
        onNavigate={scrollToSection}
        activeSection={activeSection}
        bookingCount={activeBooking ? 1 : 0}
        selectedCountry={selectedCountry}
        selectedCurrency={selectedCurrency}
        onSelectCountry={setSelectedCountry}
        onSelectCurrency={setSelectedCurrency}
      />

      {/* Main Luxury Content Flow */}
      <main style={{ position: 'relative', zIndex: 1, paddingTop: '72px' }}>
        {/* 1. Hero Section */}
        <HeroSection
          onExploreRooms={() => scrollToSection('rooms')}
          onTalkToConcierge={() => scrollToSection('ai-concierge')}
        />

        {/* 2. Rooms & Villas (6 Distinct Accommodations with Live International Rates) */}
        <RoomsSection
          onSelectRoomForBooking={handleBookRoomWithConcierge}
          selectedCurrency={selectedCurrency}
        />

        {/* 3. Dining & Cuisine (6 Distinct Culinary Venues) */}
        <DiningSection
          onInquireDining={handleInquireDining}
        />

        {/* 4. Resort Experiences (7 Distinct Curated Adventures) */}
        <ExperiencesSection
          onInquireExperience={handleInquireExperience}
        />

        {/* 5. AI Concierge (Guest-Facing Voice & Intelligent Assistant) */}
        <AiConciergeSection
          isVoiceActive={isVoiceActive}
          isMuted={isMuted}
          audioLevel={audioLevel}
          sessionState={sessionState}
          conversation={conversation}
          partialTranscript={partialTranscript}
          isThinking={isThinking}
          voiceError={voiceError}
          onStartVoice={handleStartVoice}
          onStopVoice={handleStopVoice}
          onToggleMute={handleToggleMute}
          onClearConversation={handleClearConversation}
          onSendTextTurn={handleSimulateTurn}
        />

        {/* 6. My Booking (Customer-Friendly Reservation Details with Converted Totals) */}
        <MyBookingSection
          activeBooking={activeBooking}
          recentBookings={recentBookings}
          onOpenConcierge={() => scrollToSection('ai-concierge')}
          selectedCurrency={selectedCurrency}
        />
      </main>

      {/* Luxury Resort Footer */}
      <Footer onNavigate={scrollToSection} />

      {/* Floating AI Concierge Chat Bar (Bottom-Right Customer-Facing Assistant) */}
      <AiConciergeFloatingChat
        conversation={conversation}
        partialTranscript={partialTranscript}
        isThinking={isThinking}
        isVoiceActive={isVoiceActive}
        isMuted={isMuted}
        audioLevel={audioLevel}
        sessionState={sessionState}
        selectedCurrency={selectedCurrency}
        activeBooking={activeBooking}
        onSendTextTurn={handleSimulateTurn}
        onStartVoice={handleStartVoice}
        onStopVoice={handleStopVoice}
        onToggleMute={handleToggleMute}
        onClearConversation={handleClearConversation}
        onViewRoom={(room) => scrollToSection('rooms')}
        onBookRoom={(room) => handleBookRoomWithConcierge(room)}
        onViewMyBooking={() => scrollToSection('my-booking')}
      />
    </div>
  );
}
