import React, { useState } from 'react';
import { Send, Zap, Sparkles, CornerDownLeft } from 'lucide-react';

export default function InteractiveDemoBar({ onSimulateTurn, isThinking, onTriggerBargeIn, selectedCurrency = 'USD' }) {
  const [customPrompt, setCustomPrompt] = useState('');

  const quickPrompts = [
    { label: 'Check Availability', text: 'Do you have any suites or villas available for next weekend?' },
    { label: `Quote in ${selectedCurrency}`, text: `How much would 3 nights cost in the Oceanfront Villa for 2 people in ${selectedCurrency}?` },
    { label: `Book in ${selectedCurrency}`, text: `I want to reserve the Oceanfront Villa for 2 guests from Oct 10 to Oct 14 in ${selectedCurrency}.` },
    { label: 'Dining & Spa', text: 'What dining options and spa treatments do you offer at Azure Paradise?' }
  ];

  const handleSend = (text) => {
    const promptToSend = text || customPrompt;
    if (!promptToSend.trim() || isThinking) return;
    onSimulateTurn(promptToSend);
    setCustomPrompt('');
  };

  return (
    <div className="glass-panel" style={{ padding: '18px 24px', marginTop: '24px' }}>
      
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '12px', flexWrap: 'wrap', gap: '8px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <Sparkles size={16} color="#14B8A6" />
          <span style={{ fontSize: '13px', fontWeight: '600', color: '#F1F5F9' }}>
            Interactive Recruiter Demo Controls
          </span>
          <span style={{ fontSize: '11px', color: '#64748B' }}>
            (Live Real Pipeline: AssemblyAI • Gemini • ElevenLabs • RAG • Postgres)
          </span>
        </div>

        {/* Immediate Barge-In Tester */}
        <button
          onClick={onTriggerBargeIn}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
            background: 'rgba(244, 63, 94, 0.15)',
            border: '1px solid rgba(244, 63, 94, 0.4)',
            borderRadius: '8px',
            color: '#FDA4AF',
            padding: '6px 12px',
            fontSize: '11px',
            fontWeight: '600',
            cursor: 'pointer',
            transition: 'all 0.2s'
          }}
          title="Simulate speech onset while agent is speaking to test sub-200ms cancellation"
        >
          <Zap size={14} color="#F43F5E" />
          Test Barge-In Interruption
        </button>
      </div>

      {/* Quick Prompts Chips */}
      <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', marginBottom: '14px' }}>
        {quickPrompts.map((q, idx) => (
          <button
            key={idx}
            disabled={isThinking}
            onClick={() => handleSend(q.text)}
            style={{
              background: 'rgba(30, 41, 59, 0.6)',
              border: '1px solid rgba(148, 163, 184, 0.15)',
              borderRadius: '20px',
              padding: '6px 14px',
              color: '#CBD5E1',
              fontSize: '12px',
              fontWeight: '500',
              cursor: isThinking ? 'not-allowed' : 'pointer',
              transition: 'all 0.2s ease',
              display: 'flex',
              alignItems: 'center',
              gap: '6px'
            }}
            onMouseOver={(e) => { e.currentTarget.style.borderColor = '#14B8A6'; e.currentTarget.style.color = '#F8FAFC'; }}
            onMouseOut={(e) => { e.currentTarget.style.borderColor = 'rgba(148, 163, 184, 0.15)'; e.currentTarget.style.color = '#CBD5E1'; }}
          >
            <span>{q.label}</span>
          </button>
        ))}
      </div>

      {/* Input Bar */}
      <form
        onSubmit={(e) => { e.preventDefault(); handleSend(); }}
        style={{ display: 'flex', gap: '10px', alignItems: 'center' }}
      >
        <input
          type="text"
          value={customPrompt}
          onChange={(e) => setCustomPrompt(e.target.value)}
          placeholder="Speak to the agent (e.g., 'What are the check-in and checkout times?')"
          disabled={isThinking}
          style={{
            flex: 1,
            background: 'rgba(15, 23, 42, 0.8)',
            border: '1px solid rgba(148, 163, 184, 0.2)',
            borderRadius: '10px',
            padding: '10px 16px',
            color: '#F8FAFC',
            fontSize: '13px',
            outline: 'none',
            fontFamily: 'inherit'
          }}
          onFocus={(e) => { e.target.style.borderColor = '#14B8A6'; }}
          onBlur={(e) => { e.target.style.borderColor = 'rgba(148, 163, 184, 0.2)'; }}
        />

        <button
          type="submit"
          disabled={isThinking || !customPrompt.trim()}
          style={{
            background: isThinking ? 'rgba(20, 184, 166, 0.3)' : 'linear-gradient(135deg, #0D9488 0%, #14B8A6 100%)',
            border: 'none',
            borderRadius: '10px',
            padding: '10px 18px',
            color: '#FFFFFF',
            fontSize: '13px',
            fontWeight: '600',
            cursor: isThinking || !customPrompt.trim() ? 'not-allowed' : 'pointer',
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
            boxShadow: '0 2px 10px rgba(20, 184, 166, 0.3)'
          }}
        >
          {isThinking ? (
            <span>Reasoning...</span>
          ) : (
            <>
              <span>Send</span>
              <CornerDownLeft size={14} />
            </>
          )}
        </button>
      </form>

    </div>
  );
}
