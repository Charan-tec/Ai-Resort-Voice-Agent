import React, { useState } from 'react';
import { Phone, Wifi, WifiOff, Copy, Check, Sparkles, Radio, Globe } from 'lucide-react';
import { getCountryByCode, CURRENCIES } from '../services/currency';

export default function Header({ readiness, wsStatus, activeCall, onQuickDemo, selectedCountry = 'US', selectedCurrency = 'USD' }) {
  const [copied, setCopied] = useState(false);
  const countryObj = getCountryByCode(selectedCountry);
  const currencyObj = CURRENCIES[selectedCurrency] || CURRENCIES.USD;

  const phoneNumber = readiness?.telephony?.phone_number_configured 
    ? (readiness?.telephony?.phone_number || '+1-Twilio-Configured') 
    : 'Twilio Number Configured';

  const copyNumber = () => {
    if (readiness?.telephony?.phone_number) {
      navigator.clipboard.writeText(readiness.telephony.phone_number);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  const isWsConnected = wsStatus === 'connected';

  return (
    <header className="glass-panel" style={{ padding: '16px 24px', marginBottom: '24px' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '16px' }}>
        
        {/* Brand & Title */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '14px' }}>
          <div style={{
            width: '44px',
            height: '44px',
            borderRadius: '12px',
            background: 'linear-gradient(135deg, #0D9488 0%, #14B8A6 50%, #38BDF8 100%)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            boxShadow: '0 0 20px rgba(20, 184, 166, 0.4)'
          }}>
            <Sparkles size={24} color="#FFFFFF" />
          </div>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <h1 className="brand-font" style={{ fontSize: '20px', fontWeight: '700', letterSpacing: '-0.02em', color: '#F8FAFC' }}>
                Azure Paradise Resort
              </h1>
              <span className="badge badge-online">PROD V2.5</span>
            </div>
            <p style={{ fontSize: '13px', color: '#94A3B8', marginTop: '2px' }}>
              Voice-to-Voice Telephony AI Agent — Sub-200ms Barge-In Concierge
            </p>
          </div>
        </div>

        {/* Live Call Alert & Status Indicators */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '14px', flexWrap: 'wrap' }}>
          
          {/* Active Inbound Call Banner */}
          {activeCall ? (
            <div style={{
              display: 'flex',
              alignItems: 'center',
              gap: '10px',
              padding: '6px 14px',
              background: 'rgba(56, 189, 248, 0.15)',
              border: '1px solid rgba(56, 189, 248, 0.4)',
              borderRadius: '9999px',
              animation: 'dot-pulse 1.5s infinite'
            }}>
              <Radio size={16} color="#38BDF8" className="dot-pulse" />
              <span style={{ fontSize: '12px', fontWeight: '600', color: '#38BDF8' }}>
                ACTIVE CALL: {activeCall.caller_number}
              </span>
            </div>
          ) : (
            <div style={{
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
              padding: '6px 12px',
              background: 'rgba(15, 23, 42, 0.6)',
              border: '1px solid rgba(148, 163, 184, 0.15)',
              borderRadius: '9999px'
            }}>
              <span className="dot dot-pulse" style={{ background: '#10B981' }}></span>
              <span style={{ fontSize: '12px', fontWeight: '500', color: '#94A3B8' }}>
                Awaiting Inbound PSTN Call
              </span>
            </div>
          )}

          {/* Twilio Phone Number Badge */}
          <div style={{
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            padding: '6px 12px',
            background: 'rgba(20, 184, 166, 0.1)',
            border: '1px solid rgba(20, 184, 166, 0.25)',
            borderRadius: '9999px',
            cursor: 'pointer'
          }} onClick={copyNumber} title="Click to copy Twilio number">
            <Phone size={14} color="#14B8A6" />
            <span className="mono-font" style={{ fontSize: '12px', color: '#2DD4BF', fontWeight: '600' }}>
              {phoneNumber}
            </span>
            {copied ? <Check size={14} color="#34D399" /> : <Copy size={13} color="#94A3B8" />}
          </div>

          {/* Active International Currency Badge */}
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              padding: '6px 12px',
              background: 'rgba(56, 189, 248, 0.1)',
              border: '1px solid rgba(56, 189, 248, 0.25)',
              borderRadius: '9999px',
              cursor: 'pointer'
            }}
            onClick={() => {
              const el = document.getElementById('currency-country-selector');
              if (el) el.scrollIntoView({ behavior: 'smooth' });
            }}
            title="Active country & billing currency. Click to reconfigure."
          >
            <Globe size={14} color="#38BDF8" />
            <span style={{ fontSize: '12px', fontWeight: '600', color: '#7DD3FC' }}>
              {countryObj.flag} {selectedCurrency} ({currencyObj.symbol})
            </span>
          </div>

          {/* Backend Connection Status */}
          <div style={{
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
            fontSize: '12px',
            color: isWsConnected ? '#34D399' : '#FB7185'
          }}>
            {isWsConnected ? <Wifi size={15} /> : <WifiOff size={15} />}
            <span style={{ fontWeight: '500' }}>
              {isWsConnected ? 'Live WS Connected' : 'Reconnecting...'}
            </span>
          </div>

        </div>

      </div>
    </header>
  );
}
