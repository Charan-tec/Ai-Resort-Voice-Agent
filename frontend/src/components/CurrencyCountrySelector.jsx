import React, { useState } from 'react';
import { Globe, ArrowRight, Check, Sparkles, RefreshCw, DollarSign } from 'lucide-react';
import { COUNTRIES, CURRENCIES, convertUsd, getCountryByCode } from '../services/currency';

export default function CurrencyCountrySelector({
  selectedCountry,
  onSelectCountry,
  selectedCurrency,
  onSelectCurrency,
  isUnlocked,
  onUnlockRates
}) {
  const [countrySearch, setCountrySearch] = useState('');
  const [justUpdated, setJustUpdated] = useState(false);

  // Quick preset destinations for recruiter demo
  const quickPresets = [
    { country: 'US', currency: 'USD', label: '🇺🇸 USA (USD $)' },
    { country: 'GB', currency: 'GBP', label: '🇬🇧 UK (GBP £)' },
    { country: 'DE', currency: 'EUR', label: '🇩🇪 Germany (EUR €)' },
    { country: 'IN', currency: 'INR', label: '🇮🇳 India (INR ₹)' },
    { country: 'AE', currency: 'AED', label: '🇦🇪 UAE (AED)' },
    { country: 'JP', currency: 'JPY', label: '🇯🇵 Japan (JPY ¥)' },
    { country: 'AU', currency: 'AUD', label: '🇦🇺 Australia (AUD A$)' },
    { country: 'CA', currency: 'CAD', label: '🇨🇦 Canada (CAD CA$)' }
  ];

  const currentCountryObj = getCountryByCode(selectedCountry);
  const currentCurrencyObj = CURRENCIES[selectedCurrency] || CURRENCIES.USD;
  const fxSample = convertUsd(100, selectedCurrency);

  const handleCountryChange = (e) => {
    const newCountryCode = e.target.value;
    onSelectCountry(newCountryCode);
    const country = COUNTRIES.find((c) => c.code === newCountryCode);
    if (country && country.currency && CURRENCIES[country.currency]) {
      onSelectCurrency(country.currency);
    }
    triggerFlash();
  };

  const handleCurrencyChange = (e) => {
    onSelectCurrency(e.target.value);
    triggerFlash();
  };

  const handleQuickPreset = (preset) => {
    onSelectCountry(preset.country);
    onSelectCurrency(preset.currency);
    if (!isUnlocked) {
      onUnlockRates();
    }
    triggerFlash();
  };

  const triggerFlash = () => {
    setJustUpdated(true);
    setTimeout(() => setJustUpdated(false), 1500);
  };

  const filteredCountries = countrySearch.trim()
    ? COUNTRIES.filter(
        (c) =>
          c.name.toLowerCase().includes(countrySearch.toLowerCase()) ||
          c.code.toLowerCase().includes(countrySearch.toLowerCase()) ||
          c.currency.toLowerCase().includes(countrySearch.toLowerCase())
      )
    : COUNTRIES;

  return (
    <div
      className="glass-panel"
      id="currency-country-selector"
      style={{
        padding: '20px 24px',
        marginBottom: '24px',
        border: isUnlocked ? '1px solid rgba(20, 184, 166, 0.35)' : '1px solid rgba(245, 158, 11, 0.4)',
        background: isUnlocked
          ? 'linear-gradient(135deg, rgba(15, 23, 42, 0.85) 0%, rgba(13, 148, 136, 0.08) 100%)'
          : 'linear-gradient(135deg, rgba(15, 23, 42, 0.85) 0%, rgba(245, 158, 11, 0.08) 100%)',
        position: 'relative',
        overflow: 'hidden'
      }}
    >
      {/* Top Banner Row */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '12px', marginBottom: '16px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <div
            style={{
              width: '36px',
              height: '36px',
              borderRadius: '10px',
              background: isUnlocked
                ? 'linear-gradient(135deg, #0D9488 0%, #14B8A6 100%)'
                : 'linear-gradient(135deg, #D97706 0%, #F59E0B 100%)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              boxShadow: isUnlocked ? '0 0 15px rgba(20, 184, 166, 0.4)' : '0 0 15px rgba(245, 158, 11, 0.3)'
            }}
          >
            <Globe size={20} color="#FFFFFF" />
          </div>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <h2 style={{ fontSize: '16px', fontWeight: '700', color: '#F8FAFC' }}>
                International Country & Currency Configuration
              </h2>
              <span className={isUnlocked ? 'badge badge-online' : 'badge badge-thinking'}>
                {isUnlocked ? 'RATES UNLOCKED' : 'REQUIRED BEFORE PRICING'}
              </span>
            </div>
            <p style={{ fontSize: '12px', color: '#94A3B8', marginTop: '2px' }}>
              Base rates stored in USD ($). Real-time dynamic conversion applied across all resort accommodations and bookings.
            </p>
          </div>
        </div>

        {/* Live FX Badge */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            padding: '6px 14px',
            background: 'rgba(15, 23, 42, 0.7)',
            border: '1px solid rgba(148, 163, 184, 0.18)',
            borderRadius: '9999px',
            fontSize: '12px'
          }}
        >
          <span style={{ color: '#14B8A6', fontWeight: '600' }}>⚡ Exchange Rate:</span>
          <span className="mono-font" style={{ color: '#F8FAFC', fontWeight: '700' }}>
            {fxSample.rateDisplay}
          </span>
          {justUpdated && (
            <span style={{ fontSize: '11px', color: '#34D399', fontWeight: '600', animation: 'dot-pulse 1s infinite' }}>
              • Converted
            </span>
          )}
        </div>
      </div>

      {/* Main Selectors Row */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))',
          gap: '16px',
          alignItems: 'end',
          marginBottom: '16px'
        }}
      >
        {/* Country Selector */}
        <div>
          <label style={{ display: 'block', fontSize: '12px', fontWeight: '600', color: '#CBD5E1', marginBottom: '6px' }}>
            Step 1: Select Your Country of Residence ({COUNTRIES.length} Countries)
          </label>
          <div style={{ position: 'relative' }}>
            <select
              id="country-selector"
              value={selectedCountry}
              onChange={handleCountryChange}
              style={{
                width: '100%',
                background: 'rgba(11, 19, 43, 0.85)',
                border: '1px solid rgba(148, 163, 184, 0.25)',
                borderRadius: '10px',
                padding: '10px 14px',
                color: '#F8FAFC',
                fontSize: '14px',
                fontWeight: '500',
                outline: 'none',
                cursor: 'pointer',
                fontFamily: 'inherit'
              }}
            >
              {COUNTRIES.map((c) => (
                <option key={c.code} value={c.code} style={{ background: '#0F172A', color: '#F8FAFC' }}>
                  {c.flag} {c.name} ({c.code}) — {c.currency}
                </option>
              ))}
            </select>
          </div>
          <div style={{ fontSize: '11px', color: '#64748B', marginTop: '4px' }}>
            Selecting a country automatically recommends its national currency.
          </div>
        </div>

        {/* Currency Selector */}
        <div>
          <label style={{ display: 'block', fontSize: '12px', fontWeight: '600', color: '#CBD5E1', marginBottom: '6px' }}>
            Step 2: Preferred Billing & Display Currency ({Object.keys(CURRENCIES).length} Currencies)
          </label>
          <div style={{ position: 'relative' }}>
            <select
              id="currency-selector"
              value={selectedCurrency}
              onChange={handleCurrencyChange}
              style={{
                width: '100%',
                background: 'rgba(11, 19, 43, 0.85)',
                border: '1px solid rgba(148, 163, 184, 0.25)',
                borderRadius: '10px',
                padding: '10px 14px',
                color: '#F8FAFC',
                fontSize: '14px',
                fontWeight: '600',
                outline: 'none',
                cursor: 'pointer',
                fontFamily: 'inherit'
              }}
            >
              {Object.values(CURRENCIES).map((curr) => (
                <option key={curr.code} value={curr.code} style={{ background: '#0F172A', color: '#F8FAFC' }}>
                  {curr.flag} {curr.code} — {curr.name} ({curr.symbol}) • Rate: {curr.rate}
                </option>
              ))}
            </select>
          </div>
          <div style={{ fontSize: '11px', color: '#64748B', marginTop: '4px' }}>
            You can override and choose any international currency you prefer.
          </div>
        </div>

        {/* Unlock / Confirm Action Button */}
        <div>
          <button
            id="btn-confirm-pricing-currency"
            onClick={onUnlockRates}
            style={{
              width: '100%',
              padding: '11px 20px',
              borderRadius: '10px',
              border: 'none',
              background: isUnlocked
                ? 'linear-gradient(135deg, #0D9488 0%, #14B8A6 100%)'
                : 'linear-gradient(135deg, #D97706 0%, #F59E0B 100%)',
              color: '#FFFFFF',
              fontSize: '13px',
              fontWeight: '700',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '8px',
              boxShadow: isUnlocked ? '0 4px 14px rgba(20, 184, 166, 0.35)' : '0 4px 14px rgba(245, 158, 11, 0.35)',
              transition: 'all 0.2s ease'
            }}
          >
            {isUnlocked ? (
              <>
                <Check size={16} />
                <span>Viewing Prices in {currentCurrencyObj.code} ({currentCurrencyObj.symbol})</span>
              </>
            ) : (
              <>
                <Sparkles size={16} />
                <span>Confirm & View Room Prices</span>
                <ArrowRight size={15} />
              </>
            )}
          </button>
          <div style={{ fontSize: '11px', color: '#94A3B8', marginTop: '4px', textAlign: 'center' }}>
            {isUnlocked ? 'Rates dynamically updated in real-time below' : 'Click to unlock live resort inventory & rates'}
          </div>
        </div>
      </div>

      {/* Quick Regional Presets Bar */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap', paddingTop: '10px', borderTop: '1px solid rgba(148, 163, 184, 0.1)' }}>
        <span style={{ fontSize: '11px', color: '#64748B', fontWeight: '600', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
          Quick Traveler Presets:
        </span>
        {quickPresets.map((preset) => {
          const isSelected = selectedCountry === preset.country && selectedCurrency === preset.currency;
          return (
            <button
              key={preset.country}
              onClick={() => handleQuickPreset(preset)}
              style={{
                background: isSelected ? 'rgba(20, 184, 166, 0.25)' : 'rgba(30, 41, 59, 0.5)',
                border: isSelected ? '1px solid #14B8A6' : '1px solid rgba(148, 163, 184, 0.15)',
                color: isSelected ? '#5EEAD4' : '#CBD5E1',
                borderRadius: '16px',
                padding: '4px 10px',
                fontSize: '11px',
                fontWeight: '500',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: '4px',
                transition: 'all 0.15s ease'
              }}
            >
              <span>{preset.label}</span>
              {isSelected && <Check size={12} />}
            </button>
          );
        })}
      </div>
    </div>
  );
}
