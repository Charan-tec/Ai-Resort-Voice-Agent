import React, { useState, useEffect, useRef } from 'react';
import { Search, X, Check, Globe, ChevronDown, Sparkles } from 'lucide-react';
import {
  COUNTRIES,
  CURRENCIES,
  getCountryByCode,
  getCurrencyInfo,
  getCurrencyDisplayLabel,
  saveUserCurrencyPreference
} from '../services/currency';

export default function CurrencySelectorModal({
  selectedCountry = 'IN',
  selectedCurrency = 'INR',
  onSelectCountry,
  onSelectCurrency
}) {
  const [isOpen, setIsOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const modalRef = useRef(null);
  const searchInputRef = useRef(null);

  const activeCountry = getCountryByCode(selectedCountry);
  const activeCurrency = getCurrencyInfo(selectedCurrency);

  // Focus search input when modal opens
  useEffect(() => {
    if (isOpen) {
      setTimeout(() => {
        searchInputRef.current?.focus();
      }, 50);
    } else {
      setSearchQuery('');
    }
  }, [isOpen]);

  // Close on Escape key
  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key === 'Escape' && isOpen) {
        setIsOpen(false);
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen]);

  // Filter countries by search term
  const filteredCountries = COUNTRIES.filter((c) => {
    const query = searchQuery.trim().toLowerCase();
    if (!query) return true;
    return (
      c.name.toLowerCase().includes(query) ||
      c.code.toLowerCase().includes(query) ||
      c.currency.toLowerCase().includes(query)
    );
  });

  const handleSelect = (c) => {
    onSelectCountry(c.code);
    onSelectCurrency(c.currency);
    saveUserCurrencyPreference(c.code, c.currency);
    setIsOpen(false);
  };

  const quickPicks = [
    { code: 'IN', currency: 'INR' },
    { code: 'US', currency: 'USD' },
    { code: 'GB', currency: 'GBP' },
    { code: 'EU', currency: 'EUR' },
    { code: 'AE', currency: 'AED' },
    { code: 'SG', currency: 'SGD' },
    { code: 'AU', currency: 'AUD' },
    { code: 'CA', currency: 'CAD' },
    { code: 'JP', currency: 'JPY' }
  ];

  return (
    <>
      {/* Compact Trigger Button for Navbar */}
      <button
        id="btn-currency-selector"
        onClick={() => setIsOpen(true)}
        aria-label="Select Country and Currency"
        style={{
          display: 'inline-flex',
          alignItems: 'center',
          gap: '7px',
          padding: '7px 14px',
          borderRadius: '9999px',
          background: 'rgba(6, 21, 31, 0.75)',
          backdropFilter: 'blur(12px)',
          WebkitBackdropFilter: 'blur(12px)',
          border: '1px solid rgba(212, 175, 55, 0.35)',
          color: '#F8FAFC',
          fontSize: '12px',
          fontWeight: 600,
          cursor: 'pointer',
          transition: 'all 0.25s ease',
          boxShadow: '0 2px 10px rgba(0, 0, 0, 0.3)',
          letterSpacing: '0.02em',
          whiteSpace: 'nowrap'
        }}
        onMouseEnter={(e) => {
          e.currentTarget.style.borderColor = 'rgba(212, 175, 55, 0.7)';
          e.currentTarget.style.boxShadow = '0 0 15px rgba(212, 175, 55, 0.25)';
          e.currentTarget.style.transform = 'translateY(-1px)';
        }}
        onMouseLeave={(e) => {
          e.currentTarget.style.borderColor = 'rgba(212, 175, 55, 0.35)';
          e.currentTarget.style.boxShadow = '0 2px 10px rgba(0, 0, 0, 0.3)';
          e.currentTarget.style.transform = 'translateY(0)';
        }}
      >
        <span style={{ fontSize: '15px', lineHeight: 1 }}>{activeCountry.flag}</span>
        <span style={{ color: '#F8FAFC' }}>{activeCountry.name}</span>
        <span style={{ color: 'rgba(212, 175, 55, 0.8)' }}>·</span>
        <span style={{ color: '#FCE09B', fontWeight: 700 }}>{activeCurrency.code}</span>
        <ChevronDown size={13} style={{ color: '#94A3B8', marginLeft: '1px' }} />
      </button>

      {/* Luxury Backdrop & Dropdown Modal */}
      {isOpen && (
        <div
          style={{
            position: 'fixed',
            inset: 0,
            zIndex: 9999,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            background: 'rgba(3, 11, 17, 0.75)',
            backdropFilter: 'blur(16px)',
            WebkitBackdropFilter: 'blur(16px)',
            padding: '16px',
            animation: 'fadeIn 0.2s ease-out'
          }}
          onClick={(e) => {
            if (e.target === e.currentTarget) setIsOpen(false);
          }}
        >
          <div
            ref={modalRef}
            className="glass-panel"
            style={{
              width: '100%',
              maxWidth: '520px',
              maxHeight: '90vh',
              background: 'rgba(8, 26, 38, 0.95)',
              border: '1px solid rgba(212, 175, 55, 0.4)',
              borderRadius: '24px',
              padding: '24px',
              display: 'flex',
              flexDirection: 'column',
              boxShadow: '0 25px 60px -10px rgba(0, 0, 0, 0.8), 0 0 35px rgba(212, 175, 55, 0.15)',
              position: 'relative'
            }}
          >
            {/* Header */}
            <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: '18px' }}>
              <div>
                <div style={{ display: 'inline-flex', alignItems: 'center', gap: '6px', color: '#FCE09B', fontSize: '11px', fontWeight: 600, letterSpacing: '0.1em', textTransform: 'uppercase', marginBottom: '4px' }}>
                  <Sparkles size={13} />
                  <span>Global Guest Preferences</span>
                </div>
                <h3 className="font-brand" style={{ fontSize: '22px', fontWeight: 600, color: '#FFFFFF', margin: 0 }}>
                  Select Country & Currency
                </h3>
                <p style={{ color: '#94A3B8', fontSize: '12px', marginTop: '4px' }}>
                  Prices dynamically converted from resort canonical USD rates.
                </p>
              </div>

              <button
                onClick={() => setIsOpen(false)}
                style={{
                  background: 'rgba(255, 255, 255, 0.06)',
                  border: '1px solid rgba(255, 255, 255, 0.12)',
                  color: '#CBD5E1',
                  borderRadius: '50%',
                  width: '32px',
                  height: '32px',
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
                  e.currentTarget.style.background = 'rgba(255, 255, 255, 0.06)';
                  e.currentTarget.style.color = '#CBD5E1';
                }}
              >
                <X size={16} />
              </button>
            </div>

            {/* Search Input */}
            <div style={{ position: 'relative', marginBottom: '16px' }}>
              <input
                ref={searchInputRef}
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Search country, currency, or code (e.g. India, GBP, EUR)..."
                className="luxury-input"
                style={{
                  paddingLeft: '38px',
                  fontSize: '13px',
                  borderRadius: '12px',
                  background: 'rgba(6, 20, 28, 0.85)'
                }}
              />
              <Search
                size={16}
                style={{
                  position: 'absolute',
                  left: '12px',
                  top: '50%',
                  transform: 'translateY(-50%)',
                  color: '#64748B'
                }}
              />
            </div>

            {/* Quick Destinations Row */}
            <div style={{ marginBottom: '14px' }}>
              <div style={{ fontSize: '11px', color: '#94A3B8', fontWeight: 600, letterSpacing: '0.04em', textTransform: 'uppercase', marginBottom: '8px' }}>
                Popular Currencies:
              </div>
              <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
                {quickPicks.map((pick) => {
                  const countryObj = getCountryByCode(pick.code);
                  const isSelected = selectedCountry === pick.code && selectedCurrency === pick.currency;
                  return (
                    <button
                      key={pick.code}
                      onClick={() => handleSelect(countryObj)}
                      style={{
                        background: isSelected
                          ? 'linear-gradient(135deg, rgba(212, 175, 55, 0.25) 0%, rgba(2, 132, 199, 0.25) 100%)'
                          : 'rgba(255, 255, 255, 0.04)',
                        border: isSelected
                          ? '1px solid rgba(212, 175, 55, 0.6)'
                          : '1px solid rgba(255, 255, 255, 0.1)',
                        color: isSelected ? '#FCE09B' : '#CBD5E1',
                        borderRadius: '9999px',
                        padding: '4px 10px',
                        fontSize: '11px',
                        fontWeight: 600,
                        cursor: 'pointer',
                        display: 'inline-flex',
                        alignItems: 'center',
                        gap: '5px',
                        transition: 'all 0.15s ease'
                      }}
                      onMouseEnter={(e) => {
                        if (!isSelected) {
                          e.currentTarget.style.background = 'rgba(212, 175, 55, 0.15)';
                          e.currentTarget.style.color = '#FFFFFF';
                        }
                      }}
                      onMouseLeave={(e) => {
                        if (!isSelected) {
                          e.currentTarget.style.background = 'rgba(255, 255, 255, 0.04)';
                          e.currentTarget.style.color = '#CBD5E1';
                        }
                      }}
                    >
                      <span>{countryObj.flag}</span>
                      <span>{pick.currency}</span>
                      {isSelected && <Check size={11} style={{ color: '#D4AF37' }} />}
                    </button>
                  );
                })}
              </div>
            </div>

            {/* Scrollable Countries List */}
            <div
              style={{
                flex: 1,
                overflowY: 'auto',
                maxHeight: '340px',
                display: 'flex',
                flexDirection: 'column',
                gap: '6px',
                paddingRight: '4px'
              }}
            >
              {filteredCountries.map((c) => {
                const isSelected = selectedCountry === c.code && selectedCurrency === c.currency;
                const curr = getCurrencyInfo(c.currency);

                return (
                  <button
                    key={c.code}
                    onClick={() => handleSelect(c)}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      padding: '10px 14px',
                      borderRadius: '12px',
                      background: isSelected ? 'rgba(212, 175, 55, 0.12)' : 'rgba(255, 255, 255, 0.03)',
                      border: isSelected ? '1px solid rgba(212, 175, 55, 0.45)' : '1px solid rgba(255, 255, 255, 0.06)',
                      color: '#F8FAFC',
                      cursor: 'pointer',
                      textAlign: 'left',
                      transition: 'all 0.15s ease'
                    }}
                    onMouseEnter={(e) => {
                      if (!isSelected) {
                        e.currentTarget.style.background = 'rgba(255, 255, 255, 0.08)';
                        e.currentTarget.style.borderColor = 'rgba(212, 175, 55, 0.3)';
                      }
                    }}
                    onMouseLeave={(e) => {
                      if (!isSelected) {
                        e.currentTarget.style.background = 'rgba(255, 255, 255, 0.03)';
                        e.currentTarget.style.borderColor = 'rgba(255, 255, 255, 0.06)';
                      }
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                      <span style={{ fontSize: '18px', lineHeight: 1 }}>{c.flag}</span>
                      <div>
                        <div style={{ fontSize: '13px', fontWeight: 600, color: isSelected ? '#FCE09B' : '#FFFFFF' }}>
                          {c.name}
                        </div>
                        <div style={{ fontSize: '11px', color: '#94A3B8' }}>
                          {c.code}
                        </div>
                      </div>
                    </div>

                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <div style={{ textAlign: 'right' }}>
                        <span style={{ fontSize: '13px', fontWeight: 700, color: isSelected ? '#FCE09B' : '#38BDF8', letterSpacing: '0.02em' }}>
                          {getCurrencyDisplayLabel(c.currency)}
                        </span>
                      </div>
                      {isSelected ? (
                        <div style={{ width: '20px', height: '20px', borderRadius: '50%', background: '#D4AF37', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#06151F' }}>
                          <Check size={12} strokeWidth={3} />
                        </div>
                      ) : (
                        <div style={{ width: '20px' }} />
                      )}
                    </div>
                  </button>
                );
              })}

              {filteredCountries.length === 0 && (
                <div style={{ textAlign: 'center', padding: '32px', color: '#64748B', fontSize: '13px' }}>
                  No countries matching "{searchQuery}".
                </div>
              )}
            </div>

            {/* Footer Note */}
            <div style={{ marginTop: '14px', paddingTop: '12px', borderTop: '1px solid rgba(255, 255, 255, 0.08)', display: 'flex', alignItems: 'center', justifyContent: 'space-between', fontSize: '11px', color: '#64748B' }}>
              <span>Resort Base Rates: USD ($)</span>
              <span>Live ISO-4217 Currency Display</span>
            </div>
          </div>
        </div>
      )}

      <style>{`
        @keyframes fadeIn {
          from { opacity: 0; }
          to { opacity: 1; }
        }
      `}</style>
    </>
  );
}
