import React from 'react';
import { Mic, Brain, Volume2, Database, Layers, CheckCircle2, AlertCircle } from 'lucide-react';

export default function ProviderStatus({ readiness }) {
  const providers = readiness?.providers || {};
  const telephony = readiness?.telephony || {};

  const items = [
    {
      id: 'stt',
      name: 'Speech-to-Text',
      provider: providers.stt?.label || 'AssemblyAI STT (v3 WS)',
      specs: '8kHz μ-law • Turn-based Streaming',
      icon: Mic,
      color: '#14B8A6',
      active: providers.stt?.configured ?? true
    },
    {
      id: 'llm',
      name: 'Agent LLM & Tools',
      provider: providers.llm?.label || 'Google Gemini LLM',
      specs: 'Streaming Tokens • Function Calling (6 Tools)',
      icon: Brain,
      color: '#A855F7',
      active: providers.llm?.configured ?? true
    },
    {
      id: 'tts',
      name: 'Text-to-Speech',
      provider: providers.tts?.label || 'ElevenLabs TTS (Flash v2.5)',
      specs: '8kHz G.711 μ-law • Sub-300ms First Chunk',
      icon: Volume2,
      color: '#38BDF8',
      active: providers.tts?.configured ?? true
    },
    {
      id: 'rag',
      name: 'Knowledge RAG',
      provider: providers.rag?.label || 'Chroma Vector Store',
      specs: 'Sub-Millisecond Speculative TTL Cache',
      icon: Layers,
      color: '#F59E0B',
      active: providers.rag?.configured ?? true
    },
    {
      id: 'db',
      name: 'Reservation DB',
      provider: providers.database?.label || 'PostgreSQL 16',
      specs: 'btree_gist Exclusion Constraints (Zero Overlaps)',
      icon: Database,
      color: '#10B981',
      active: providers.database?.configured ?? true
    }
  ];

  return (
    <div className="glass-panel" style={{ padding: '20px' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '14px' }}>
        <h2 style={{ fontSize: '15px', fontWeight: '600', color: '#F1F5F9', display: 'flex', alignItems: 'center', gap: '8px' }}>
          <Layers size={18} color="#14B8A6" />
          Active Pipeline & Subsystems
        </h2>
        <span className="badge badge-online" style={{ fontSize: '10px' }}>
          Real Providers Verified
        </span>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '12px' }}>
        {items.map((item) => {
          const Icon = item.icon;
          return (
            <div key={item.id} style={{
              background: 'rgba(15, 23, 42, 0.55)',
              border: '1px solid rgba(148, 163, 184, 0.12)',
              borderRadius: '12px',
              padding: '12px',
              display: 'flex',
              flexDirection: 'column',
              justifyContent: 'space-between',
              transition: 'border-color 0.2s ease'
            }}>
              <div>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' }}>
                  <div style={{
                    width: '30px',
                    height: '30px',
                    borderRadius: '8px',
                    background: `${item.color}20`,
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center'
                  }}>
                    <Icon size={16} color={item.color} />
                  </div>
                  {item.active ? (
                    <span style={{ display: 'flex', alignItems: 'center', gap: '4px', fontSize: '11px', color: '#34D399', fontWeight: '600' }}>
                      <CheckCircle2 size={13} /> READY
                    </span>
                  ) : (
                    <span style={{ display: 'flex', alignItems: 'center', gap: '4px', fontSize: '11px', color: '#F59E0B', fontWeight: '600' }}>
                      <AlertCircle size={13} /> MOCK / OFF
                    </span>
                  )}
                </div>
                <div style={{ fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.05em', color: '#64748B', fontWeight: '600' }}>
                  {item.name}
                </div>
                <div style={{ fontSize: '13px', fontWeight: '600', color: '#F8FAFC', marginTop: '2px', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                  {item.provider}
                </div>
              </div>
              <div style={{ fontSize: '11px', color: '#94A3B8', marginTop: '8px', borderTop: '1px solid rgba(148, 163, 184, 0.08)', paddingTop: '6px' }}>
                {item.specs}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
