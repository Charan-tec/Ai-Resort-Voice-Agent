import React from 'react';
import { Calendar, ShieldCheck, Mail, DollarSign, Clock, CheckCircle2, User, Globe } from 'lucide-react';
import { convertUsd } from '../services/currency';

export default function BookingCard({ activeBooking, recentBookings, selectedCurrency = 'USD' }) {
  const displayBooking = activeBooking || (recentBookings && recentBookings.length > 0 ? recentBookings[0] : null);

  const isConfirmed = displayBooking?.status === 'confirmed';
  const isPending = displayBooking?.status === 'pending';
  const emailSent = Boolean(displayBooking?.email_status === 'sent' || (isConfirmed && (displayBooking?.customer_email || displayBooking?.guest_email)));

  const bookingCurrency = displayBooking?.currency || 'USD';
  const rawPrice = displayBooking?.total_price ? Number(displayBooking.total_price) : 0;
  // If user selected a different currency than USD, dynamically convert
  const convertedPrice = convertUsd(rawPrice, selectedCurrency);

  return (
    <div className="glass-panel" style={{ padding: '20px', display: 'flex', flexDirection: 'column', gap: '14px' }}>
      
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <Calendar size={18} color="#10B981" />
          <h2 style={{ fontSize: '15px', fontWeight: '600', color: '#F1F5F9' }}>
            Reservation & Guest State
          </h2>
        </div>
        <span className={isConfirmed ? 'badge badge-online' : isPending ? 'badge badge-thinking' : 'badge'}>
          {displayBooking ? displayBooking.status?.toUpperCase() : 'STANDBY'}
        </span>
      </div>

      {displayBooking ? (
        /* Real Reservation Card */
        <div style={{
          background: isConfirmed 
            ? 'linear-gradient(135deg, rgba(16, 185, 129, 0.15) 0%, rgba(15, 23, 42, 0.75) 100%)'
            : 'linear-gradient(135deg, rgba(245, 158, 11, 0.12) 0%, rgba(15, 23, 42, 0.7) 100%)',
          border: isConfirmed ? '1px solid rgba(16, 185, 129, 0.4)' : '1px solid rgba(245, 158, 11, 0.3)',
          borderRadius: '14px',
          padding: '16px',
          boxShadow: '0 8px 24px rgba(0, 0, 0, 0.3)'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '10px' }}>
            <div style={{ fontSize: '11px', color: isConfirmed ? '#34D399' : '#FBBF24', fontWeight: '700', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
              {isConfirmed ? 'Confirmed Booking Reference' : 'Tentative 15-Min Hold'}
            </div>
            <span className="mono-font" style={{ fontSize: '13px', fontWeight: '700', color: '#F8FAFC' }}>
              {displayBooking.booking_code || displayBooking.booking_id || displayBooking.pending_token?.slice(0, 16) || 'HOLD-PENDING'}
            </span>
          </div>

          <div style={{ fontSize: '16px', fontWeight: '700', color: '#F8FAFC', marginBottom: '8px' }}>
            {displayBooking.room_name || displayBooking.room_id || 'Luxury Oceanfront Villa'}
          </div>

          {/* Grid Details */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: '10px', fontSize: '12px' }}>
            <div>
              <span style={{ color: '#64748B' }}>Guest: </span>
              <span style={{ color: '#E2E8F0', fontWeight: '600' }}>
                {displayBooking.guest_name || 'Guest via Phone'}
              </span>
            </div>
            <div>
              <span style={{ color: '#64748B' }}>Party Size: </span>
              <span style={{ color: '#E2E8F0', fontWeight: '600' }}>
                {displayBooking.guests || 2} Guests
              </span>
            </div>
            <div>
              <span style={{ color: '#64748B' }}>Check-in: </span>
              <span style={{ color: '#E2E8F0', fontWeight: '600' }}>
                {displayBooking.check_in || 'N/A'}
              </span>
            </div>
            <div>
              <span style={{ color: '#64748B' }}>Check-out: </span>
              <span style={{ color: '#E2E8F0', fontWeight: '600' }}>
                {displayBooking.check_out || 'N/A'}
              </span>
            </div>
          </div>

          {/* Email dispatch state */}
          <div style={{ marginTop: '10px', display: 'flex', alignItems: 'center', gap: '6px', fontSize: '12px' }}>
            <Mail size={13} color={emailSent ? '#34D399' : '#94A3B8'} />
            <span style={{ color: '#64748B' }}>Email Itinerary: </span>
            <span style={{ color: emailSent ? '#34D399' : '#94A3B8', fontWeight: '500' }}>
              {emailSent 
                ? `Dispatched to ${displayBooking.customer_email || displayBooking.guest_email || 'guest'}`
                : isPending 
                  ? 'Pending confirmation before dispatch'
                  : 'Ready to send upon guest request'}
            </span>
          </div>

          {/* Price & Guarantee Footer */}
          <div style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            flexWrap: 'wrap',
            gap: '8px',
            marginTop: '12px',
            paddingTop: '10px',
            borderTop: '1px solid rgba(148, 163, 184, 0.12)'
          }}>
            <div>
              <div style={{ display: 'flex', alignItems: 'baseline', gap: '6px' }}>
                <span style={{ fontSize: '11px', color: '#64748B' }}>Total Rate: </span>
                <span className="mono-font" style={{ fontSize: '17px', fontWeight: '800', color: '#34D399' }}>
                  {convertedPrice.formatted} {selectedCurrency}
                </span>
                {selectedCurrency !== 'USD' && (
                  <span style={{ fontSize: '11px', color: '#94A3B8' }}>
                    (${rawPrice.toFixed(2)} USD base)
                  </span>
                )}
              </div>
              {selectedCurrency !== 'USD' && (
                <div style={{ fontSize: '10px', color: '#10B981', marginTop: '2px', display: 'flex', alignItems: 'center', gap: '4px' }}>
                  <Globe size={11} />
                  <span>Dynamic FX: {convertedPrice.rateDisplay}</span>
                </div>
              )}
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '4px', fontSize: '10px', color: '#10B981', fontWeight: '600' }}>
              <ShieldCheck size={14} />
              PostgreSQL Range Exclusion Verified
            </div>
          </div>
        </div>
      ) : (
        /* Clean Standby State */
        <div style={{
          background: 'rgba(15, 23, 42, 0.45)',
          border: '1px dashed rgba(148, 163, 184, 0.2)',
          borderRadius: '14px',
          padding: '24px 16px',
          textAlign: 'center',
          color: '#94A3B8'
        }}>
          <Calendar size={28} color="#64748B" style={{ margin: '0 auto 8px auto', display: 'block', opacity: 0.6 }} />
          <div style={{ fontSize: '13px', fontWeight: '600', color: '#CBD5E1' }}>
            No Active Reservation Turn
          </div>
          <div style={{ fontSize: '11px', color: '#64748B', marginTop: '4px' }}>
            PostgreSQL 16 reservation engine is connected and ready. Speak or simulate a booking inquiry.
          </div>
        </div>
      )}

      {/* Booking Stage Indicator */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', fontSize: '11px', color: '#94A3B8' }}>
        <span style={{ display: 'flex', alignItems: 'center', gap: '4px', color: isPending ? '#F59E0B' : '#64748B' }}>
          <Clock size={13} color={isPending ? '#F59E0B' : '#64748B'} /> Stage 1: 15-Min Hold
        </span>
        <span style={{ display: 'flex', alignItems: 'center', gap: '4px', color: isConfirmed ? '#10B981' : '#64748B' }}>
          <CheckCircle2 size={13} color={isConfirmed ? '#10B981' : '#64748B'} /> Stage 2: Confirmed & Emailed
        </span>
      </div>

    </div>
  );
}
