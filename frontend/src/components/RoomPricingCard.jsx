import React, { useState, useEffect, useMemo } from 'react';
import {
  Bed,
  Users,
  Calendar,
  Sparkles,
  ShieldCheck,
  DollarSign,
  Coffee,
  Car,
  Wine,
  Heart,
  ArrowRight,
  Lock,
  CheckCircle2,
  TrendingUp,
  Info
} from 'lucide-react';
import { convertUsd, DEFAULT_ROOMS, CURRENCIES, getCountryByCode } from '../services/currency';
import { api } from '../services/api';

const ADD_ON_OPTIONS = [
  { id: 'breakfast', label: 'Artisan Breakfast', baseUsd: 35.0, perNight: true, icon: Coffee },
  { id: 'spa_credit', label: 'Spa & Wellness Credit', baseUsd: 150.0, perNight: false, icon: Heart },
  { id: 'airport_shuttle', label: 'Luxury Airport Shuttle', baseUsd: 80.0, perNight: false, icon: Car },
  { id: 'champagne', label: 'Welcome Champagne', baseUsd: 95.0, perNight: false, icon: Wine }
];

export default function RoomPricingCard({
  selectedCountry,
  selectedCurrency,
  isUnlocked,
  onUnlock,
  onSimulateInquiry
}) {
  const [rooms, setRooms] = useState(DEFAULT_ROOMS);
  const [selectedRoomId, setSelectedRoomId] = useState('villa-ocean-101');
  const [checkIn, setCheckIn] = useState('2026-10-10');
  const [checkOut, setCheckOut] = useState('2026-10-14');
  const [guests, setGuests] = useState(2);
  const [selectedAddons, setSelectedAddons] = useState(['breakfast']);
  const [isCalculating, setIsCalculating] = useState(false);

  // Fetch rooms from backend if available
  useEffect(() => {
    async function fetchRooms() {
      try {
        const data = await api.getRooms();
        if (data && data.rooms && data.rooms.length > 0) {
          setRooms(data.rooms);
        }
      } catch (e) {
        // Fallback to DEFAULT_ROOMS
      }
    }
    fetchRooms();
  }, []);

  const selectedRoom = rooms.find((r) => r.room_id === selectedRoomId) || rooms[0] || DEFAULT_ROOMS[0];

  // Calculate nights
  const nights = useMemo(() => {
    try {
      const d1 = new Date(checkIn);
      const d2 = new Date(checkOut);
      const diff = Math.round((d2 - d1) / (1000 * 60 * 60 * 24));
      return diff > 0 ? diff : 1;
    } catch {
      return 1;
    }
  }, [checkIn, checkOut]);

  // Base USD calculations strictly according to resort pricing policy
  const baseCalculationsUsd = useMemo(() => {
    const nightly = Number(selectedRoom?.base_rate_nightly) || 650.0;
    const subtotal = nightly * nights;
    const resortFees = 45.0 * nights;
    const taxes = (subtotal + resortFees) * 0.12;

    let addonsTotal = 0.0;
    selectedAddons.forEach((addonId) => {
      const opt = ADD_ON_OPTIONS.find((a) => a.id === addonId);
      if (opt) {
        addonsTotal += opt.perNight ? opt.baseUsd * nights : opt.baseUsd;
      }
    });

    const total = subtotal + resortFees + taxes + addonsTotal;

    return {
      nightly,
      subtotal,
      resortFees,
      taxes,
      addonsTotal,
      total
    };
  }, [selectedRoom, nights, selectedAddons]);

  // Converted values using live selectedCurrency
  const converted = useMemo(() => {
    return {
      nightly: convertUsd(baseCalculationsUsd.nightly, selectedCurrency),
      subtotal: convertUsd(baseCalculationsUsd.subtotal, selectedCurrency),
      resortFees: convertUsd(baseCalculationsUsd.resortFees, selectedCurrency),
      taxes: convertUsd(baseCalculationsUsd.taxes, selectedCurrency),
      addonsTotal: convertUsd(baseCalculationsUsd.addonsTotal, selectedCurrency),
      total: convertUsd(baseCalculationsUsd.total, selectedCurrency)
    };
  }, [baseCalculationsUsd, selectedCurrency]);

  const toggleAddon = (id) => {
    setSelectedAddons((prev) =>
      prev.includes(id) ? prev.filter((item) => item !== id) : [...prev, id]
    );
  };

  const handleInquireViaVoice = () => {
    const prompt = `I would like to quote the ${selectedRoom.name} for ${nights} nights from ${checkIn} to ${checkOut} for ${guests} guests${
      selectedAddons.length > 0 ? ` with ${selectedAddons.join(', ')}` : ''
    }. Please quote the total in ${selectedCurrency}.`;
    if (onSimulateInquiry) {
      onSimulateInquiry(prompt);
    }
  };

  const countryInfo = getCountryByCode(selectedCountry);
  const currencyInfo = CURRENCIES[selectedCurrency] || CURRENCIES.USD;

  // Gated state if country and currency not yet confirmed
  if (!isUnlocked) {
    return (
      <div
        className="glass-panel"
        style={{
          padding: '36px 24px',
          textAlign: 'center',
          borderRadius: '18px',
          marginBottom: '24px',
          background: 'linear-gradient(135deg, rgba(15, 23, 42, 0.9) 0%, rgba(30, 41, 59, 0.6) 100%)',
          border: '1px dashed rgba(245, 158, 11, 0.35)'
        }}
      >
        <div
          style={{
            width: '56px',
            height: '56px',
            borderRadius: '16px',
            background: 'linear-gradient(135deg, rgba(245, 158, 11, 0.2) 0%, rgba(245, 158, 11, 0.05) 100%)',
            border: '1px solid rgba(245, 158, 11, 0.4)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            margin: '0 auto 16px auto'
          }}
        >
          <Lock size={26} color="#F59E0B" />
        </div>

        <h3 style={{ fontSize: '18px', fontWeight: '700', color: '#F8FAFC', marginBottom: '8px' }}>
          Select Country & Currency Before Viewing Room Prices
        </h3>
        <p style={{ fontSize: '13px', color: '#94A3B8', maxWidth: '580px', margin: '0 auto 20px auto', lineHeight: '1.5' }}>
          To provide transparent, accurate international quotes, Azure Paradise Resort dynamically converts its base USD lodging inventory into your local currency. Please confirm your country and currency above to unlock real-time pricing.
        </p>

        <button
          onClick={onUnlock}
          style={{
            background: 'linear-gradient(135deg, #D97706 0%, #F59E0B 100%)',
            border: 'none',
            borderRadius: '10px',
            padding: '10px 22px',
            color: '#FFFFFF',
            fontSize: '13px',
            fontWeight: '700',
            cursor: 'pointer',
            display: 'inline-flex',
            alignItems: 'center',
            gap: '8px',
            boxShadow: '0 4px 14px rgba(245, 158, 11, 0.35)'
          }}
        >
          <Sparkles size={16} />
          <span>Confirm & Unlock Room Pricing ({countryInfo.flag} {selectedCurrency})</span>
          <ArrowRight size={15} />
        </button>
      </div>
    );
  }

  return (
    <div
      className="glass-panel"
      id="room-pricing-explorer"
      style={{
        padding: '24px',
        marginBottom: '24px',
        display: 'flex',
        flexDirection: 'column',
        gap: '20px'
      }}
    >
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '12px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <div
            style={{
              width: '40px',
              height: '40px',
              borderRadius: '12px',
              background: 'linear-gradient(135deg, #0D9488 0%, #14B8A6 100%)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              boxShadow: '0 0 16px rgba(20, 184, 166, 0.35)'
            }}
          >
            <Bed size={22} color="#FFFFFF" />
          </div>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <h2 style={{ fontSize: '17px', fontWeight: '700', color: '#F8FAFC' }}>
                Resort Accommodations & International Pricing
              </h2>
              <span className="badge badge-online">
                {countryInfo.flag} {selectedCurrency} CONVERTED
              </span>
            </div>
            <p style={{ fontSize: '12px', color: '#94A3B8', marginTop: '2px' }}>
              Base rates authored in USD ($) • Converted dynamically into {currencyInfo.name} ({currencyInfo.code}) at {converted.nightly.rateDisplay}
            </p>
          </div>
        </div>

        {/* Currency badge info */}
        <div
          style={{
            background: 'rgba(15, 23, 42, 0.6)',
            border: '1px solid rgba(148, 163, 184, 0.15)',
            borderRadius: '10px',
            padding: '6px 14px',
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            fontSize: '12px'
          }}
        >
          <span style={{ color: '#64748B' }}>Target Market:</span>
          <span style={{ color: '#F8FAFC', fontWeight: '600' }}>
            {countryInfo.flag} {countryInfo.name}
          </span>
          <span style={{ color: '#14B8A6', fontWeight: '700', marginLeft: '4px' }}>
            {currencyInfo.symbol} {currencyInfo.code}
          </span>
        </div>
      </div>

      {/* Room Selection Cards Grid */}
      <div>
        <div style={{ fontSize: '13px', fontWeight: '600', color: '#E2E8F0', marginBottom: '10px' }}>
          Select Accommodation:
        </div>
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))',
            gap: '14px'
          }}
        >
          {rooms.map((room) => {
            const isSelected = room.room_id === selectedRoomId;
            const roomConvertedNightly = convertUsd(room.base_rate_nightly, selectedCurrency);

            return (
              <div
                key={room.room_id}
                onClick={() => setSelectedRoomId(room.room_id)}
                style={{
                  background: isSelected
                    ? 'linear-gradient(135deg, rgba(20, 184, 166, 0.15) 0%, rgba(15, 23, 42, 0.8) 100%)'
                    : 'rgba(15, 23, 42, 0.55)',
                  border: isSelected ? '1.5px solid #14B8A6' : '1px solid rgba(148, 163, 184, 0.15)',
                  borderRadius: '14px',
                  padding: '16px',
                  cursor: 'pointer',
                  transition: 'all 0.2s ease',
                  position: 'relative',
                  boxShadow: isSelected ? '0 8px 24px rgba(20, 184, 166, 0.15)' : 'none'
                }}
              >
                {isSelected && (
                  <div
                    style={{
                      position: 'absolute',
                      top: '12px',
                      right: '12px',
                      display: 'flex',
                      alignItems: 'center',
                      gap: '4px',
                      fontSize: '11px',
                      fontWeight: '700',
                      color: '#14B8A6'
                    }}
                  >
                    <CheckCircle2 size={15} /> SELECTED
                  </div>
                )}

                <div style={{ fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.05em', color: '#14B8A6', fontWeight: '700' }}>
                  {room.room_type}
                </div>
                <div style={{ fontSize: '15px', fontWeight: '700', color: '#F8FAFC', marginTop: '2px', marginBottom: '8px' }}>
                  {room.name}
                </div>

                {/* Nightly Price with dynamic conversion */}
                <div style={{ marginBottom: '10px' }}>
                  <div style={{ display: 'flex', alignItems: 'baseline', gap: '6px' }}>
                    <span className="mono-font" style={{ fontSize: '20px', fontWeight: '800', color: '#34D399' }}>
                      {roomConvertedNightly.formatted}
                    </span>
                    <span style={{ fontSize: '12px', color: '#94A3B8' }}>/ night</span>
                  </div>
                  <div style={{ fontSize: '11px', color: '#64748B', marginTop: '2px' }}>
                    Base: ${room.base_rate_nightly.toFixed(2)} USD / night
                  </div>
                </div>

                {/* Occupancy */}
                <div style={{ display: 'flex', alignItems: 'center', gap: '5px', fontSize: '11px', color: '#94A3B8', marginBottom: '10px' }}>
                  <Users size={13} color="#64748B" />
                  <span>Max Occupancy: {room.max_occupancy} Guests</span>
                </div>

                {/* Amenities Badges */}
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '5px' }}>
                  {(room.amenities || []).slice(0, 3).map((amenity, i) => (
                    <span
                      key={i}
                      style={{
                        background: 'rgba(30, 41, 59, 0.6)',
                        border: '1px solid rgba(148, 163, 184, 0.1)',
                        borderRadius: '6px',
                        padding: '2px 8px',
                        fontSize: '10px',
                        color: '#CBD5E1'
                      }}
                    >
                      {amenity}
                    </span>
                  ))}
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Dynamic Stay Calculator & Price Breakdown Section */}
      <div
        style={{
          background: 'rgba(11, 19, 43, 0.7)',
          border: '1px solid rgba(148, 163, 184, 0.15)',
          borderRadius: '16px',
          padding: '20px'
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '10px', marginBottom: '16px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <TrendingUp size={16} color="#14B8A6" />
            <h3 style={{ fontSize: '15px', fontWeight: '700', color: '#F8FAFC' }}>
              Live Price Breakdown & Stay Estimator
            </h3>
          </div>
          <span style={{ fontSize: '11px', color: '#94A3B8' }}>
            Dates: {checkIn} → {checkOut} ({nights} {nights === 1 ? 'Night' : 'Nights'})
          </span>
        </div>

        {/* Controls Grid */}
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))',
            gap: '12px',
            marginBottom: '16px'
          }}
        >
          <div>
            <label style={{ display: 'block', fontSize: '11px', fontWeight: '600', color: '#94A3B8', marginBottom: '4px' }}>
              Check-In Date:
            </label>
            <input
              type="date"
              value={checkIn}
              onChange={(e) => setCheckIn(e.target.value)}
              style={{
                width: '100%',
                background: 'rgba(15, 23, 42, 0.8)',
                border: '1px solid rgba(148, 163, 184, 0.2)',
                borderRadius: '8px',
                padding: '8px 12px',
                color: '#F8FAFC',
                fontSize: '12px',
                outline: 'none',
                fontFamily: 'inherit'
              }}
            />
          </div>

          <div>
            <label style={{ display: 'block', fontSize: '11px', fontWeight: '600', color: '#94A3B8', marginBottom: '4px' }}>
              Check-Out Date:
            </label>
            <input
              type="date"
              value={checkOut}
              onChange={(e) => setCheckOut(e.target.value)}
              style={{
                width: '100%',
                background: 'rgba(15, 23, 42, 0.8)',
                border: '1px solid rgba(148, 163, 184, 0.2)',
                borderRadius: '8px',
                padding: '8px 12px',
                color: '#F8FAFC',
                fontSize: '12px',
                outline: 'none',
                fontFamily: 'inherit'
              }}
            />
          </div>

          <div>
            <label style={{ display: 'block', fontSize: '11px', fontWeight: '600', color: '#94A3B8', marginBottom: '4px' }}>
              Guests:
            </label>
            <select
              value={guests}
              onChange={(e) => setGuests(Number(e.target.value))}
              style={{
                width: '100%',
                background: 'rgba(15, 23, 42, 0.8)',
                border: '1px solid rgba(148, 163, 184, 0.2)',
                borderRadius: '8px',
                padding: '8px 12px',
                color: '#F8FAFC',
                fontSize: '12px',
                outline: 'none',
                fontFamily: 'inherit'
              }}
            >
              {[1, 2, 3, 4, 5, 6].map((g) => (
                <option key={g} value={g} style={{ background: '#0F172A' }}>
                  {g} {g === 1 ? 'Guest' : 'Guests'}
                </option>
              ))}
            </select>
          </div>
        </div>

        {/* Add-ons Toggles */}
        <div style={{ marginBottom: '16px' }}>
          <div style={{ fontSize: '11px', fontWeight: '600', color: '#94A3B8', marginBottom: '6px' }}>
            Optional Resort Add-ons:
          </div>
          <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
            {ADD_ON_OPTIONS.map((addon) => {
              const active = selectedAddons.includes(addon.id);
              const Icon = addon.icon;
              const convertedAddon = convertUsd(
                addon.perNight ? addon.baseUsd * nights : addon.baseUsd,
                selectedCurrency
              );

              return (
                <button
                  key={addon.id}
                  onClick={() => toggleAddon(addon.id)}
                  style={{
                    background: active ? 'rgba(20, 184, 166, 0.2)' : 'rgba(15, 23, 42, 0.6)',
                    border: active ? '1px solid #14B8A6' : '1px solid rgba(148, 163, 184, 0.15)',
                    borderRadius: '8px',
                    padding: '6px 12px',
                    color: active ? '#2DD4BF' : '#CBD5E1',
                    fontSize: '11px',
                    fontWeight: '500',
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '6px',
                    transition: 'all 0.15s ease'
                  }}
                >
                  <Icon size={13} color={active ? '#2DD4BF' : '#94A3B8'} />
                  <span>{addon.label}</span>
                  <span className="mono-font" style={{ fontWeight: '700' }}>
                    (+{convertedAddon.formatted})
                  </span>
                </button>
              );
            })}
          </div>
        </div>

        {/* Detailed Price Conversion Table */}
        <div
          style={{
            background: 'rgba(2, 6, 23, 0.6)',
            borderRadius: '12px',
            padding: '16px',
            display: 'flex',
            flexDirection: 'column',
            gap: '10px',
            fontSize: '13px'
          }}
        >
          {/* Base Lodging */}
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div>
              <span style={{ color: '#CBD5E1' }}>
                Base Lodging ({nights} nights @ {converted.nightly.formatted})
              </span>
              <span style={{ fontSize: '11px', color: '#64748B', marginLeft: '6px' }}>
                (${baseCalculationsUsd.nightly.toFixed(2)} USD/night)
              </span>
            </div>
            <div style={{ textAlign: 'right' }}>
              <span className="mono-font" style={{ fontWeight: '600', color: '#F1F5F9' }}>
                {converted.subtotal.formatted}
              </span>
              <div style={{ fontSize: '10px', color: '#64748B' }}>
                ${baseCalculationsUsd.subtotal.toFixed(2)} USD
              </div>
            </div>
          </div>

          {/* Daily Resort Fee */}
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div>
              <span style={{ color: '#CBD5E1' }}>
                Daily Resort Fee ($45 USD × {nights} nights)
              </span>
              <span style={{ fontSize: '11px', color: '#64748B', marginLeft: '6px' }}>
                (Pool, Butler, High-Speed WiFi)
              </span>
            </div>
            <div style={{ textAlign: 'right' }}>
              <span className="mono-font" style={{ fontWeight: '600', color: '#F1F5F9' }}>
                {converted.resortFees.formatted}
              </span>
              <div style={{ fontSize: '10px', color: '#64748B' }}>
                ${baseCalculationsUsd.resortFees.toFixed(2)} USD
              </div>
            </div>
          </div>

          {/* Resort & State Tax */}
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div>
              <span style={{ color: '#CBD5E1' }}>
                Resort & State Taxes (12%)
              </span>
            </div>
            <div style={{ textAlign: 'right' }}>
              <span className="mono-font" style={{ fontWeight: '600', color: '#F1F5F9' }}>
                {converted.taxes.formatted}
              </span>
              <div style={{ fontSize: '10px', color: '#64748B' }}>
                ${baseCalculationsUsd.taxes.toFixed(2)} USD
              </div>
            </div>
          </div>

          {/* Add-ons if selected */}
          {baseCalculationsUsd.addonsTotal > 0 && (
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div>
                <span style={{ color: '#CBD5E1' }}>Selected Resort Add-ons</span>
                <span style={{ fontSize: '11px', color: '#64748B', marginLeft: '6px' }}>
                  ({selectedAddons.join(', ')})
                </span>
              </div>
              <div style={{ textAlign: 'right' }}>
                <span className="mono-font" style={{ fontWeight: '600', color: '#F1F5F9' }}>
                  {converted.addonsTotal.formatted}
                </span>
                <div style={{ fontSize: '10px', color: '#64748B' }}>
                  ${baseCalculationsUsd.addonsTotal.toFixed(2)} USD
                </div>
              </div>
            </div>
          )}

          {/* Divider */}
          <div style={{ height: '1px', background: 'rgba(148, 163, 184, 0.15)', margin: '4px 0' }} />

          {/* Grand Total Row */}
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div>
              <div style={{ fontSize: '14px', fontWeight: '700', color: '#F8FAFC' }}>
                Total Quoted Stay Price
              </div>
              <div style={{ fontSize: '11px', color: '#10B981', display: 'flex', alignItems: 'center', gap: '4px', marginTop: '2px' }}>
                <ShieldCheck size={13} />
                <span>Base USD: ${baseCalculationsUsd.total.toFixed(2)} USD @ {converted.total.rateDisplay}</span>
              </div>
            </div>

            <div style={{ textAlign: 'right' }}>
              <span
                className="mono-font"
                style={{
                  fontSize: '22px',
                  fontWeight: '800',
                  color: '#34D399',
                  textShadow: '0 0 16px rgba(52, 211, 153, 0.3)'
                }}
              >
                {converted.total.formatted} {selectedCurrency}
              </span>
              <div style={{ fontSize: '11px', color: '#94A3B8' }}>
                Equivalent to ${baseCalculationsUsd.total.toFixed(2)} USD
              </div>
            </div>
          </div>
        </div>

        {/* Quick Action Button to Voice Agent */}
        <div style={{ marginTop: '16px', display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '10px' }}>
          <div style={{ fontSize: '11px', color: '#64748B' }}>
            💡 Recruiter Action: Test voice concierge quoting this live with currency conversion!
          </div>

          <button
            onClick={handleInquireViaVoice}
            style={{
              background: 'linear-gradient(135deg, #0D9488 0%, #14B8A6 100%)',
              border: 'none',
              borderRadius: '8px',
              padding: '8px 16px',
              color: '#FFFFFF',
              fontSize: '12px',
              fontWeight: '600',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              boxShadow: '0 2px 10px rgba(20, 184, 166, 0.3)',
              transition: 'all 0.2s'
            }}
          >
            <Sparkles size={14} />
            <span>Simulate Voice Inquiry for {converted.total.formatted} {selectedCurrency}</span>
          </button>
        </div>
      </div>
    </div>
  );
}
