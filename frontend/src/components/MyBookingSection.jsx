import React from 'react';
import { Calendar, CheckCircle2, Clock, MapPin, Sparkles, User, Users, ShieldCheck, Download, MessageSquare } from 'lucide-react';
import { formatPriceDisplay } from '../services/currency';

export default function MyBookingSection({ activeBooking, recentBookings, onOpenConcierge, selectedCurrency = 'INR' }) {
  const displayBooking = activeBooking || (recentBookings && recentBookings.length > 0 ? recentBookings[0] : null);

  const priceDetails = displayBooking?.total_price
    ? formatPriceDisplay(displayBooking.total_price, selectedCurrency)
    : formatPriceDisplay(0, selectedCurrency);

  const formatConfirmationCode = (booking) => {
    if (!booking) return '';
    if (booking.confirmation_number) return String(booking.confirmation_number);
    if (booking.booking_code) return String(booking.booking_code);
    if (booking.booking_id) {
      const idStr = String(booking.booking_id);
      return idStr.startsWith('RES-') ? idStr : `APR-${idStr.padStart(6, '0')}`;
    }
    if (booking.pending_token) {
      return `HLD-${booking.pending_token.substring(0, 8).toUpperCase()}`;
    }
    return 'APR-849201';
  };

  const isConfirmed = displayBooking?.status === 'confirmed';
  const isPending = displayBooking?.status === 'pending';

  return (
    <section id="my-booking" style={{ padding: '80px 24px', maxWidth: '1200px', margin: '0 auto' }}>
      {/* Section Header */}
      <div style={{ textAlign: 'center', marginBottom: '40px' }}>
        <div style={{
          display: 'inline-flex',
          alignItems: 'center',
          gap: '8px',
          padding: '6px 16px',
          borderRadius: '9999px',
          background: 'rgba(212, 175, 55, 0.12)',
          border: '1px solid rgba(212, 175, 55, 0.3)',
          color: 'var(--resort-gold)',
          fontSize: '12px',
          fontWeight: '600',
          letterSpacing: '0.08em',
          textTransform: 'uppercase',
          marginBottom: '16px'
        }}>
          <ShieldCheck size={14} />
          Guest Reservation Services
        </div>
        <h2 style={{
          fontFamily: "'Cinzel', serif",
          fontSize: 'clamp(28px, 4vw, 42px)',
          fontWeight: '600',
          color: 'var(--resort-text-light)',
          letterSpacing: '0.03em',
          marginBottom: '12px'
        }}>
          My Reservation
        </h2>
        <p style={{ color: 'var(--resort-text-muted)', fontSize: '15px', maxWidth: '580px', margin: '0 auto' }}>
          Review your 5-star resort accommodations, itinerary dates, and tailored guest amenities.
        </p>
      </div>

      {displayBooking ? (
        /* Confirmed / Active Reservation Card */
        <div className="glass-panel" style={{
          borderRadius: '24px',
          padding: 'clamp(24px, 4vw, 40px)',
          border: isConfirmed ? '1px solid rgba(16, 185, 129, 0.4)' : '1px solid rgba(212, 175, 55, 0.35)',
          background: 'linear-gradient(135deg, rgba(6, 21, 31, 0.85) 0%, rgba(10, 37, 51, 0.9) 100%)',
          boxShadow: '0 24px 60px rgba(0, 0, 0, 0.5)',
          position: 'relative',
          overflow: 'hidden'
        }}>
          {/* Subtle Top Gold/Emerald Glow Accent */}
          <div style={{
            position: 'absolute',
            top: 0,
            left: 0,
            right: 0,
            height: '4px',
            background: isConfirmed
              ? 'linear-gradient(90deg, transparent, #10B981, transparent)'
              : 'linear-gradient(90deg, transparent, #D4AF37, transparent)'
          }} />

          {/* Status Bar */}
          <div style={{
            display: 'flex',
            flexWrap: 'wrap',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: '16px',
            paddingBottom: '24px',
            borderBottom: '1px solid rgba(255, 255, 255, 0.08)',
            marginBottom: '28px'
          }}>
            <div>
              <span style={{ fontSize: '12px', color: 'var(--resort-text-muted)', textTransform: 'uppercase', letterSpacing: '0.06em' }}>
                Confirmation Reference
              </span>
              <div style={{
                fontFamily: "'Cinzel', serif",
                fontSize: '22px',
                fontWeight: '700',
                color: 'var(--resort-gold)',
                letterSpacing: '0.05em',
                marginTop: '4px'
              }}>
                {formatConfirmationCode(displayBooking)}
              </div>
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
              <span style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '6px',
                padding: '6px 16px',
                borderRadius: '9999px',
                fontSize: '12px',
                fontWeight: '600',
                letterSpacing: '0.04em',
                textTransform: 'uppercase',
                background: isConfirmed ? 'rgba(16, 185, 129, 0.15)' : 'rgba(245, 158, 11, 0.15)',
                color: isConfirmed ? '#34D399' : '#FBBF24',
                border: isConfirmed ? '1px solid rgba(16, 185, 129, 0.3)' : '1px solid rgba(245, 158, 11, 0.3)'
              }}>
                {isConfirmed ? <CheckCircle2 size={14} /> : <Clock size={14} />}
                {isConfirmed ? 'Confirmed Reservation' : '15-Minute Courtesy Hold'}
              </span>
            </div>
          </div>

          {/* Room Title & Key Grid */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '32px' }}>
            {/* Left Details */}
            <div>
              <div style={{
                fontSize: '13px',
                color: 'var(--resort-gold)',
                textTransform: 'uppercase',
                letterSpacing: '0.08em',
                fontWeight: '600',
                marginBottom: '6px'
              }}>
                Reserved Suite / Villa
              </div>
              <h3 style={{
                fontFamily: "'Cinzel', serif",
                fontSize: '26px',
                fontWeight: '600',
                color: 'var(--resort-text-light)',
                marginBottom: '16px',
                lineHeight: 1.25
              }}>
                {displayBooking.room_name || displayBooking.room_id || 'Oceanfront Luxury Villa'}
              </h3>

              <div style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(2, 1fr)',
                gap: '16px',
                padding: '20px',
                borderRadius: '16px',
                background: 'rgba(255, 255, 255, 0.03)',
                border: '1px solid rgba(255, 255, 255, 0.06)'
              }}>
                <div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '6px', color: 'var(--resort-text-muted)', fontSize: '12px', marginBottom: '4px' }}>
                    <User size={13} />
                    Guest Name
                  </div>
                  <div style={{ color: 'var(--resort-text-light)', fontWeight: '600', fontSize: '15px' }}>
                    {displayBooking.guest_name || 'Valued Guest'}
                  </div>
                </div>

                <div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '6px', color: 'var(--resort-text-muted)', fontSize: '12px', marginBottom: '4px' }}>
                    <Users size={13} />
                    Guests
                  </div>
                  <div style={{ color: 'var(--resort-text-light)', fontWeight: '600', fontSize: '15px' }}>
                    {displayBooking.guests || 2} {Number(displayBooking.guests) === 1 ? 'Guest' : 'Guests'}
                  </div>
                </div>

                <div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '6px', color: 'var(--resort-text-muted)', fontSize: '12px', marginBottom: '4px' }}>
                    <Calendar size={13} />
                    Check-in
                  </div>
                  <div style={{ color: 'var(--resort-text-light)', fontWeight: '600', fontSize: '15px' }}>
                    {displayBooking.check_in || 'Flexible Check-in'}
                  </div>
                </div>

                <div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '6px', color: 'var(--resort-text-muted)', fontSize: '12px', marginBottom: '4px' }}>
                    <Calendar size={13} />
                    Check-out
                  </div>
                  <div style={{ color: 'var(--resort-text-light)', fontWeight: '600', fontSize: '15px' }}>
                    {displayBooking.check_out || 'Flexible Check-out'}
                  </div>
                </div>
              </div>
            </div>

            {/* Right Financial & Perks */}
            <div style={{
              display: 'flex',
              flexDirection: 'column',
              justifyContent: 'space-between',
              padding: '24px',
              borderRadius: '16px',
              background: 'linear-gradient(135deg, rgba(2, 132, 199, 0.1) 0%, rgba(6, 21, 31, 0.6) 100%)',
              border: '1px solid rgba(2, 132, 199, 0.2)'
            }}>
              <div>
                <span style={{ fontSize: '12px', color: 'var(--resort-text-muted)', textTransform: 'uppercase', letterSpacing: '0.06em' }}>
                  Total Accommodation Price
                </span>
                <div style={{
                  fontFamily: "'Cinzel', serif",
                  fontSize: '32px',
                  fontWeight: '700',
                  color: 'var(--resort-gold)',
                  marginTop: '4px',
                  marginBottom: '2px'
                }}>
                  {priceDetails.primary}
                </div>
                {priceDetails.secondary && (
                  <div style={{ fontSize: '13px', color: '#94A3B8', marginBottom: '10px' }}>
                    {priceDetails.secondary}
                  </div>
                )}
                {priceDetails.isConversionUnavailable && (
                  <div style={{ fontSize: '12px', color: '#FBBF24', marginBottom: '10px' }}>
                    Local currency conversion temporarily unavailable.
                  </div>
                )}
                <p style={{ fontSize: '12px', color: 'var(--resort-text-muted)', lineHeight: '1.6', margin: 0 }}>
                  Includes all resort access, private beach club entry, daily breakfast buffet, high-speed WiFi, and 24/7 dedicated AI concierge service.
                </p>
              </div>

              {/* Complimentary Inclusions */}
              <div style={{ marginTop: '20px', paddingTop: '16px', borderTop: '1px solid rgba(255, 255, 255, 0.08)' }}>
                <div style={{ fontSize: '12px', color: '#93C5FD', fontWeight: '600', marginBottom: '8px', display: 'flex', alignItems: 'center', gap: '6px' }}>
                  <Sparkles size={13} /> Complimentary VIP Inclusions
                </div>
                <div style={{ fontSize: '12px', color: 'var(--resort-text-light)', display: 'flex', flexDirection: 'column', gap: '4px' }}>
                  <span>✓ Welcome chilled Champagne & tropical fruit basket</span>
                  <span>✓ Priority dining reservations at Azure Reef</span>
                  <span>✓ Signature sunset cocktail voucher per guest</span>
                </div>
              </div>

              {/* Action Buttons */}
              <div style={{ marginTop: '24px', display: 'flex', gap: '12px', flexWrap: 'wrap' }}>
                <button
                  onClick={onOpenConcierge}
                  className="btn-gold"
                  style={{
                    flex: 1,
                    minWidth: '180px',
                    display: 'inline-flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    gap: '8px',
                    padding: '12px 20px',
                    fontSize: '13px'
                  }}
                >
                  <MessageSquare size={15} />
                  Speak with Concierge
                </button>
              </div>
            </div>
          </div>
        </div>
      ) : (
        /* Customer-Friendly Empty State */
        <div className="glass-panel" style={{
          borderRadius: '24px',
          padding: '48px 24px',
          textAlign: 'center',
          maxWidth: '680px',
          margin: '0 auto',
          border: '1px solid rgba(255, 255, 255, 0.1)'
        }}>
          <div style={{
            width: '64px',
            height: '64px',
            borderRadius: '50%',
            background: 'rgba(212, 175, 55, 0.1)',
            border: '1px solid rgba(212, 175, 55, 0.25)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            margin: '0 auto 20px',
            color: 'var(--resort-gold)'
          }}>
            <Calendar size={28} />
          </div>
          <h3 style={{
            fontFamily: "'Cinzel', serif",
            fontSize: '22px',
            fontWeight: '600',
            color: 'var(--resort-text-light)',
            marginBottom: '10px'
          }}>
            No Active Reservation
          </h3>
          <p style={{
            color: 'var(--resort-text-muted)',
            fontSize: '14px',
            maxWidth: '440px',
            margin: '0 auto 24px',
            lineHeight: 1.6
          }}>
            You have no active stays scheduled. Speak directly with Rachel, your dedicated AI Concierge, or browse our luxury oceanfront suites to arrange your retreat.
          </p>
          <div style={{ display: 'flex', justifyContent: 'center', gap: '14px', flexWrap: 'wrap' }}>
            <a href="#rooms" className="btn-secondary" style={{ textDecoration: 'none', padding: '10px 22px', fontSize: '13px' }}>
              Explore Rooms
            </a>
            <button
              onClick={onOpenConcierge}
              className="btn-gold"
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '8px',
                padding: '10px 22px',
                fontSize: '13px'
              }}
            >
              <Sparkles size={14} />
              Book via AI Concierge
            </button>
          </div>
        </div>
      )}
    </section>
  );
}
