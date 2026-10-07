import React from 'react';
import { Terminal, Cpu, FileText, Search, Code2, CheckCircle2 } from 'lucide-react';

export default function AgentActivity({ currentTool, lastRag }) {
  return (
    <div className="glass-panel" style={{ padding: '20px', display: 'flex', flexDirection: 'column', gap: '16px' }}>
      
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <Cpu size={18} color="#14B8A6" />
          <h2 style={{ fontSize: '15px', fontWeight: '600', color: '#F1F5F9' }}>
            Agent Brain & Tool Execution
          </h2>
        </div>
        <span className="badge badge-thinking" style={{ fontSize: '10px' }}>
          6 Active Tools
        </span>
      </div>

      {/* Tool Call Activity Card */}
      <div style={{
        background: 'rgba(15, 23, 42, 0.65)',
        border: '1px solid rgba(148, 163, 184, 0.12)',
        borderRadius: '12px',
        padding: '14px'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '12px', fontWeight: '600', color: '#38BDF8' }}>
            <Terminal size={14} />
            Function / Tool Invocation
          </div>
          {currentTool ? (
            <span style={{ display: 'flex', alignItems: 'center', gap: '4px', fontSize: '11px', color: '#34D399', fontWeight: '600' }}>
              <CheckCircle2 size={12} /> {currentTool.status || 'COMPLETED'}
            </span>
          ) : (
            <span style={{ fontSize: '11px', color: '#64748B' }}>Standby</span>
          )}
        </div>

        {currentTool ? (
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '6px' }}>
              <span className="mono-font" style={{ fontSize: '13px', fontWeight: '700', color: '#F8FAFC' }}>
                {currentTool.name}()
              </span>
            </div>
            
            {/* Arguments */}
            <div style={{
              background: 'rgba(2, 6, 23, 0.6)',
              borderRadius: '8px',
              padding: '8px 10px',
              fontSize: '11px',
              fontFamily: 'JetBrains Mono, monospace',
              color: '#94A3B8',
              overflowX: 'auto',
              maxHeight: '120px'
            }}>
              {JSON.stringify(currentTool.arguments || {}, null, 2)}
            </div>

            {/* Spoken Hint / Spoken Result if any */}
            {currentTool.result && (
              <div style={{ marginTop: '8px', fontSize: '11px', color: '#CBD5E1' }}>
                <span style={{ color: '#14B8A6', fontWeight: '600' }}>Result: </span>
                {typeof currentTool.result === 'object' 
                  ? (currentTool.result.spoken_hint || currentTool.result.message || JSON.stringify(currentTool.result))
                  : String(currentTool.result)}
              </div>
            )}
          </div>
        ) : (
          <div style={{ fontSize: '12px', color: '#64748B', fontStyle: 'italic', padding: '6px 0' }}>
            No tools invoked yet in this session. Ask for availability, pricing, or room booking.
          </div>
        )}
      </div>

      {/* RAG Speculative Retrieval Card */}
      <div style={{
        background: 'rgba(15, 23, 42, 0.65)',
        border: '1px solid rgba(148, 163, 184, 0.12)',
        borderRadius: '12px',
        padding: '14px'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '12px', fontWeight: '600', color: '#F59E0B' }}>
            <Search size={14} />
            Speculative RAG Retrieval
          </div>
          <span style={{ fontSize: '10px', color: '#94A3B8', fontFamily: 'monospace' }}>
            Chroma Vector DB
          </span>
        </div>

        {lastRag ? (
          <div>
            <div style={{ fontSize: '11px', color: '#94A3B8', marginBottom: '6px' }}>
              <span style={{ color: '#F59E0B', fontWeight: '600' }}>Query: </span>
              "{lastRag.query}"
            </div>
            {lastRag.docs && lastRag.docs.length > 0 ? (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                {lastRag.docs.slice(0, 2).map((doc, i) => (
                  <div key={i} style={{
                    background: 'rgba(2, 6, 23, 0.5)',
                    borderLeft: '2px solid #F59E0B',
                    padding: '6px 8px',
                    borderRadius: '4px',
                    fontSize: '11px',
                    color: '#E2E8F0',
                    lineHeight: '1.4'
                  }}>
                    {doc.content?.slice(0, 140)}...
                  </div>
                ))}
              </div>
            ) : (
              <div style={{ fontSize: '11px', color: '#64748B' }}>Query probed into TTL cache</div>
            )}
          </div>
        ) : (
          <div style={{ fontSize: '12px', color: '#64748B', fontStyle: 'italic', padding: '6px 0' }}>
            Interim transcripts will automatically probe the LangChain Chroma vector store here.
          </div>
        )}
      </div>

    </div>
  );
}
