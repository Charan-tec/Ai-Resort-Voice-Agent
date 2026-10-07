import React, { useState, useMemo } from 'react';
import { resortImages } from '../config/resortImages';
import {
  Users,
  Bed,
  Sparkles,
  Check,
  ArrowRight,
  Eye,
  Calendar,
  X,
  Coffee,
  Car,
  Heart,
  Wine,
  ShieldCheck,
  Info
} from 'lucide-react';
import { formatPriceDisplay, calculateBookingBreakdown } from '../services/currency';

const ROOM_CATALOG = [
  {
    id: 'villa-ocean-101',
    name: 'Oceanfront Luxury Villa',
    category: 'Villa',
    rate: 650,
    capacity: 4,
    description: 'Sprawling private beachfront villa with an infinity plunge pool, dedicated butler service, and panoramic Pacific sunsets.',
    image: resortImages.rooms.oceanfrontVilla,
    amenities: ['Private Infinity Pool', 'Ocean View Terrace', 'King Bed & Butler', 'Complimentary Breakfast']
  },
  {
    id: 'suite-deluxe-201',
    name: 'Deluxe Sunset Suite',
    category: 'Suite',
    rate: 380,
    capacity: 2,
    description: 'An intimate sunset haven featuring a panoramic balcony, deep whirlpool spa tub, master king bed, and artisanal espresso bar.',
    image: resortImages.rooms.deluxeSunsetSuite,
    amenities: ['Sunset Balcony', 'Whirlpool Spa Tub', 'King Bed', 'Espresso Bar']
  },
  {
    id: 'bungalow-garden-301',
    name: 'Garden Tropical Bungalow',
    category: 'Bungalow',
    rate: 290,
    capacity: 3,
    description: 'Tranquil secluded tropical bungalow nestled among lush orchids, featuring a private outdoor zen rain shower and hammock terrace.',
    image: resortImages.rooms.gardenBungalow,
    amenities: ['Private Zen Garden', 'Rain Shower', 'Queen Bed', 'Hammock Terrace']
  },
  {
    id: 'suite-presidential-401',
    name: 'Presidential Ocean Suite',
    category: 'Suite',
    rate: 850,
    capacity: 4,
    description: 'The pinnacle of resort luxury with wraparound oceanfront terraces, grand master king bedroom, and vintage champagne service.',
    image: resortImages.rooms.presidentialSuite,
    amenities: ['Oceanfront Terrace', 'Master King Suite', 'Spa Tub & Butler', 'Vintage Champagne']
  },
  {
    id: 'villa-family-501',
    name: 'Family Pool Villa',
    category: 'Villa',
    rate: 520,
    capacity: 6,
    description: 'Generous multi-room estate with private swimming pool, sun deck, kitchenette, and bunk suite designed for family retreat.',
    image: resortImages.rooms.familyPoolVilla,
    amenities: ['Private Swimming Pool', 'Sun Deck & Garden', 'Two King Beds & Bunks', 'Full Kitchenette']
  },
  {
    id: 'suite-premium-302',
    name: 'Premium Garden Suite',
    category: 'Suite',
    rate: 450,
    capacity: 3,
    description: 'Refined garden elegance with Italian marble soaking tub, king daybed, private veranda overlooking botanical grounds.',
    image: resortImages.rooms.premiumGardenSuite,
    amenities: ['Botanical Garden View', 'Marble Soaking Tub', 'King Bed & Daybed', 'Complimentary Breakfast']
  }
];

const ADD_ONS = [
  { id: 'breakfast', name: 'Artisan Breakfast Buffet', priceUsd: 35, perNight: true, icon: Coffee },
  { id: 'shuttle', name: 'Luxury Airport Escort', priceUsd: 80, perNight: false, icon: Car },
  { id: 'spa', name: 'Oceanfront Spa Credit', priceUsd: 150, perNight: false, icon: Heart },
  { id: 'champagne', name: 'Welcome Vintage Champagne', priceUsd: 95, perNight: false, icon: Wine }
];

export default function RoomsSection({ onSelectRoomForBooking, selectedCurrency = 'INR' }) {
  const [selectedCategory, setSelectedCategory] = useState('ALL');
  const [activeModalRoom, setActiveModalRoom] = useState(null);

  // Booking Summary Modal state
  const [modalNights, setModalNights] = useState(4);
  const [checkInDate, setCheckInDate] = useState('2026-10-10');
  const [checkOutDate, setCheckOutDate] = useState('2026-10-14');
  const [selectedAddons, setSelectedAddons] = useState(['breakfast']);

  const filteredRooms = selectedCategory === 'ALL'
    ? ROOM_CATALOG
    : ROOM_CATALOG.filter((r) => r.category.toUpperCase() === selectedCategory);

  const handleOpenRoomModal = (room) => {
    setActiveModalRoom(room);
  };

  const handleCloseModal = () => {
    setActiveModalRoom(null);
  };

  const handleToggleAddon = (addonId) => {
    setSelectedAddons((prev) =>
      prev.includes(addonId) ? prev.filter((id) => id !== addonId) : [...prev, addonId]
    );
  };

  // Calculate nights dynamically from date inputs
  const calculatedNights = useMemo(() => {
    try {
      const d1 = new Date(checkInDate);
      const d2 = new Date(checkOutDate);
      const diff = Math.round((d2 - d1) / (1000 * 60 * 60 * 24));
      return diff > 0 ? diff : 1;
    } catch {
      return modalNights || 4;
    }
  }, [checkInDate, checkOutDate, modalNights]);

  // Calculate total USD for selected add-ons
  const totalAddonsUsd = useMemo(() => {
    return selectedAddons.reduce((sum, id) => {
      const a = ADD_ONS.find((item) => item.id === id);
      if (!a) return sum;
      return sum + (a.perNight ? a.priceUsd * calculatedNights : a.priceUsd);
    }, 0);
  }, [selectedAddons, calculatedNights]);

  // Complete breakdown using centralized currency calculator
  const modalBreakdown = useMemo(() => {
    if (!activeModalRoom) return null;
    return calculateBookingBreakdown(
      {
        nightlyRateUsd: activeModalRoom.rate,
        nights: calculatedNights,
        resortFeePerNightUsd: 45,
        taxRate: 0.12,
        addonsUsd: totalAddonsUsd
      },
      selectedCurrency
    );
  }, [activeModalRoom, calculatedNights, totalAddonsUsd, selectedCurrency]);

  return (
    <section id="rooms" style={{ padding: '80px 24px', maxWidth: '1440px', margin: '0 auto' }}>
      {/* Section Header */}
      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', textAlign: 'center', marginBottom: '48px' }}>
        <span className="section-tag">ACCOMMODATIONS</span>
        <h2 className="section-title">
          Rooms & <span className="gold-gradient-text">Private Villas</span>
        </h2>
        <p className="section-desc">
          Unrivaled oceanfront sanctuaries tailored for restorative island living, thoughtfully furnished with bespoke Hawaiian craftsmanship.
        </p>

        {/* Category Filter Pills */}
        <div style={{ display: 'flex', gap: '8px', marginTop: '24px', flexWrap: 'wrap', justifyContent: 'center' }}>
          {['ALL', 'VILLA', 'SUITE', 'BUNGALOW'].map((cat) => (
            <button
              key={cat}
              onClick={() => setSelectedCategory(cat)}
              style={{
                background: selectedCategory === cat ? 'linear-gradient(135deg, #F59E0B 0%, #D4AF37 100%)' : 'rgba(255, 255, 255, 0.06)',
                color: selectedCategory === cat ? '#06151F' : '#CBD5E1',
                border: selectedCategory === cat ? 'none' : '1px solid rgba(255, 255, 255, 0.12)',
                borderRadius: '9999px',
                padding: '6px 18px',
                fontSize: '12px',
                fontWeight: 600,
                letterSpacing: '0.04em',
                cursor: 'pointer',
                transition: 'all 0.2s ease'
              }}
            >
              {cat === 'ALL' ? 'All Accommodations' : `${cat}s`}
            </button>
          ))}
        </div>
      </div>

      {/* 6 Room Cards Grid */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(340px, 1fr))',
          gap: '28px'
        }}
      >
        {filteredRooms.map((room) => {
          // Dynamic live price formatting
          const priceInfo = formatPriceDisplay(room.rate, selectedCurrency);

          return (
            <div
              key={room.id}
              className="glass-card-interactive"
              style={{
                display: 'flex',
                flexDirection: 'column',
                background: 'rgba(8, 26, 38, 0.82)',
                borderRadius: '24px'
              }}
            >
              {/* Room Image Container */}
              <div
                className="img-zoom-container"
                style={{
                  width: '100%',
                  height: '240px',
                  position: 'relative'
                }}
              >
                <img
                  src={room.image}
                  alt={room.name}
                  loading="lazy"
                  style={{
                    width: '100%',
                    height: '100%',
                    objectFit: 'cover'
                  }}
                />
                <div
                  style={{
                    position: 'absolute',
                    inset: 0,
                    background: 'linear-gradient(180deg, rgba(6, 21, 31, 0.2) 0%, rgba(6, 21, 31, 0.8) 100%)'
                  }}
                />

                {/* Category Badge */}
                <span
                  className="badge-azure"
                  style={{
                    position: 'absolute',
                    top: '16px',
                    left: '16px',
                    background: 'rgba(6, 21, 31, 0.75)',
                    backdropFilter: 'blur(8px)'
                  }}
                >
                  {room.category}
                </span>

                {/* Nightly Rate Badge */}
                <div
                  style={{
                    position: 'absolute',
                    bottom: '16px',
                    right: '16px',
                    background: 'rgba(6, 21, 31, 0.88)',
                    backdropFilter: 'blur(10px)',
                    padding: '8px 14px',
                    borderRadius: '12px',
                    border: '1px solid rgba(212, 175, 55, 0.4)',
                    color: '#FFFFFF',
                    textAlign: 'right'
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'flex-end', gap: '4px' }}>
                    <span style={{ fontSize: '18px', fontWeight: 700, color: '#FCE09B' }}>
                      {priceInfo.primary}
                    </span>
                    <span style={{ fontSize: '11px', color: '#94A3B8' }}>/ night</span>
                  </div>

                  {/* Secondary Base USD Indicator */}
                  {priceInfo.secondary && (
                    <div style={{ fontSize: '10px', color: '#CBD5E1', opacity: 0.85, marginTop: '2px' }}>
                      {priceInfo.secondary}
                    </div>
                  )}

                  {/* If FX service unavailable */}
                  {priceInfo.isConversionUnavailable && (
                    <div style={{ fontSize: '10px', color: '#FBBF24', marginTop: '2px' }}>
                      Local currency conversion temporarily unavailable.
                    </div>
                  )}
                </div>
              </div>

              {/* Room Details Body */}
              <div style={{ padding: '24px', display: 'flex', flexDirection: 'column', flex: 1 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '8px' }}>
                  <h3
                    className="font-brand"
                    style={{ fontSize: '21px', fontWeight: 600, color: '#FFFFFF', lineHeight: 1.2 }}
                  >
                    {room.name}
                  </h3>
                </div>

                {/* Capacity Spec */}
                <div style={{ display: 'flex', alignItems: 'center', gap: '6px', color: '#38BDF8', fontSize: '12px', fontWeight: 500, marginBottom: '12px' }}>
                  <Users size={14} />
                  <span>Accommodates up to {room.capacity} guests</span>
                </div>

                {/* Short Description */}
                <p style={{ color: '#94A3B8', fontSize: '13px', lineHeight: 1.6, marginBottom: '18px', flex: 1 }}>
                  {room.description}
                </p>

                {/* Amenities Grid */}
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px', marginBottom: '22px' }}>
                  {room.amenities.map((amenity, idx) => (
                    <div key={idx} style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '11px', color: '#CBD5E1' }}>
                      <div style={{ width: '4px', height: '4px', borderRadius: '50%', background: '#D4AF37' }} />
                      <span style={{ whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{amenity}</span>
                    </div>
                  ))}
                </div>

                {/* View / Book Button */}
                <button
                  onClick={() => handleOpenRoomModal(room)}
                  className="btn-gold"
                  style={{
                    width: '100%',
                    padding: '12px',
                    fontSize: '13px',
                    fontWeight: 600
                  }}
                >
                  <span>View / Book</span>
                  <ArrowRight size={14} />
                </button>
              </div>
            </div>
          );
        })}
      </div>

      {/* Room Details & Booking Summary Modal */}
      {activeModalRoom && modalBreakdown && (
        <div
          style={{
            position: 'fixed',
            inset: 0,
            zIndex: 9999,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            background: 'rgba(3, 11, 17, 0.8)',
            backdropFilter: 'blur(16px)',
            WebkitBackdropFilter: 'blur(16px)',
            padding: '20px'
          }}
          onClick={(e) => {
            if (e.target === e.currentTarget) handleCloseModal();
          }}
        >
          <div
            className="glass-panel"
            style={{
              width: '100%',
              maxWidth: '820px',
              maxHeight: '92vh',
              overflowY: 'auto',
              background: 'rgba(8, 26, 38, 0.96)',
              border: '1px solid rgba(212, 175, 55, 0.4)',
              borderRadius: '24px',
              padding: '28px',
              boxShadow: '0 25px 60px rgba(0, 0, 0, 0.85)',
              position: 'relative'
            }}
          >
            {/* Modal Header */}
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '20px' }}>
              <div>
                <span className="section-tag">RESERVATION SUMMARY</span>
                <h3 className="font-brand" style={{ fontSize: '26px', fontWeight: 600, color: '#FFFFFF', margin: 0 }}>
                  {activeModalRoom.name}
                </h3>
                <p style={{ color: '#94A3B8', fontSize: '13px', marginTop: '4px' }}>
                  Base rates calculated in USD. Displayed in your selected currency ({selectedCurrency}).
                </p>
              </div>

              <button
                onClick={handleCloseModal}
                style={{
                  background: 'rgba(255, 255, 255, 0.08)',
                  border: '1px solid rgba(255, 255, 255, 0.15)',
                  color: '#CBD5E1',
                  borderRadius: '50%',
                  width: '36px',
                  height: '36px',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  cursor: 'pointer'
                }}
              >
                <X size={18} />
              </button>
            </div>

            {/* Top Grid: Room Preview & Stay Dates */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '20px', marginBottom: '24px' }}>
              {/* Room Image & Capacity */}
              <div style={{ borderRadius: '16px', overflow: 'hidden', height: '180px', position: 'relative' }}>
                <img
                  src={activeModalRoom.image}
                  alt={activeModalRoom.name}
                  style={{ width: '100%', height: '100%', objectFit: 'cover' }}
                />
                <div style={{ position: 'absolute', bottom: '12px', left: '12px', background: 'rgba(6, 21, 31, 0.85)', padding: '4px 10px', borderRadius: '8px', fontSize: '11px', color: '#FCE09B' }}>
                  {activeModalRoom.category} • Up to {activeModalRoom.capacity} guests
                </div>
              </div>

              {/* Date & Nights Selector */}
              <div style={{ background: 'rgba(255, 255, 255, 0.03)', border: '1px solid rgba(255, 255, 255, 0.08)', borderRadius: '16px', padding: '16px' }}>
                <div style={{ fontSize: '12px', color: '#CBD5E1', fontWeight: 600, marginBottom: '10px' }}>
                  Selected Itinerary ({calculatedNights} Nights)
                </div>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px', marginBottom: '10px' }}>
                  <div>
                    <label style={{ fontSize: '11px', color: '#94A3B8', display: 'block', marginBottom: '4px' }}>Check-in</label>
                    <input
                      type="date"
                      value={checkInDate}
                      onChange={(e) => setCheckInDate(e.target.value)}
                      className="luxury-input"
                      style={{ padding: '8px 10px', fontSize: '12px' }}
                    />
                  </div>
                  <div>
                    <label style={{ fontSize: '11px', color: '#94A3B8', display: 'block', marginBottom: '4px' }}>Check-out</label>
                    <input
                      type="date"
                      value={checkOutDate}
                      onChange={(e) => setCheckOutDate(e.target.value)}
                      className="luxury-input"
                      style={{ padding: '8px 10px', fontSize: '12px' }}
                    />
                  </div>
                </div>
                <div style={{ fontSize: '11px', color: '#38BDF8' }}>
                  ✓ Includes private beach club & complimentary high-speed WiFi
                </div>
              </div>
            </div>

            {/* Optional Luxury Add-ons */}
            <div style={{ marginBottom: '24px' }}>
              <div style={{ fontSize: '12px', color: '#CBD5E1', fontWeight: 600, marginBottom: '10px' }}>
                Enhance Your Stay (Optional Add-ons)
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '10px' }}>
                {ADD_ONS.map((addon) => {
                  const isChecked = selectedAddons.includes(addon.id);
                  const IconComp = addon.icon;
                  const addonPriceInfo = formatPriceDisplay(addon.priceUsd, selectedCurrency);
                  return (
                    <button
                      key={addon.id}
                      onClick={() => handleToggleAddon(addon.id)}
                      style={{
                        background: isChecked ? 'rgba(212, 175, 55, 0.15)' : 'rgba(255, 255, 255, 0.03)',
                        border: isChecked ? '1px solid #D4AF37' : '1px solid rgba(255, 255, 255, 0.08)',
                        borderRadius: '12px',
                        padding: '10px 12px',
                        textAlign: 'left',
                        cursor: 'pointer',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'space-between',
                        transition: 'all 0.15s ease'
                      }}
                    >
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <IconComp size={15} style={{ color: isChecked ? '#FCE09B' : '#94A3B8' }} />
                        <div>
                          <div style={{ fontSize: '12px', color: '#FFFFFF', fontWeight: 500 }}>{addon.name}</div>
                          <div style={{ fontSize: '11px', color: isChecked ? '#FCE09B' : '#94A3B8' }}>
                            {addonPriceInfo.primary} {addon.perNight ? '/ night' : ''}
                          </div>
                        </div>
                      </div>
                      {isChecked && <Check size={14} style={{ color: '#D4AF37' }} />}
                    </button>
                  );
                })}
              </div>
            </div>

            {/* Itemized Price Breakdown Table */}
            <div
              style={{
                background: 'linear-gradient(135deg, rgba(6, 21, 31, 0.8) 0%, rgba(10, 36, 50, 0.7) 100%)',
                border: '1px solid rgba(212, 175, 55, 0.3)',
                borderRadius: '16px',
                padding: '20px',
                marginBottom: '24px'
              }}
            >
              <div style={{ fontSize: '13px', fontWeight: 600, color: '#FCE09B', marginBottom: '14px', letterSpacing: '0.04em', textTransform: 'uppercase' }}>
                Itemized Price Breakdown
              </div>

              <div style={{ display: 'flex', flexDirection: 'column', gap: '10px', fontSize: '13px' }}>
                {/* Nightly Room Rate */}
                <div style={{ display: 'flex', justifyContent: 'space-between', color: '#CBD5E1' }}>
                  <span>Room Rate ({calculatedNights} Nights @ {modalBreakdown.display.nightly.primary}):</span>
                  <div style={{ textAlign: 'right' }}>
                    <span style={{ fontWeight: 600, color: '#FFFFFF' }}>{modalBreakdown.display.subtotal.primary}</span>
                    {modalBreakdown.display.subtotal.secondary && (
                      <span style={{ fontSize: '11px', color: '#94A3B8', marginLeft: '6px' }}>({modalBreakdown.display.subtotal.secondary})</span>
                    )}
                  </div>
                </div>

                {/* Resort Fee */}
                <div style={{ display: 'flex', justifyContent: 'space-between', color: '#CBD5E1' }}>
                  <span>Resort Service Fee (USD 45 / night):</span>
                  <div style={{ textAlign: 'right' }}>
                    <span style={{ fontWeight: 600, color: '#FFFFFF' }}>{modalBreakdown.display.resortFees.primary}</span>
                    {modalBreakdown.display.resortFees.secondary && (
                      <span style={{ fontSize: '11px', color: '#94A3B8', marginLeft: '6px' }}>({modalBreakdown.display.resortFees.secondary})</span>
                    )}
                  </div>
                </div>

                {/* Taxes */}
                <div style={{ display: 'flex', justifyContent: 'space-between', color: '#CBD5E1' }}>
                  <span>Hawaiian Occupancy & Resort Taxes (12%):</span>
                  <div style={{ textAlign: 'right' }}>
                    <span style={{ fontWeight: 600, color: '#FFFFFF' }}>{modalBreakdown.display.taxes.primary}</span>
                    {modalBreakdown.display.taxes.secondary && (
                      <span style={{ fontSize: '11px', color: '#94A3B8', marginLeft: '6px' }}>({modalBreakdown.display.taxes.secondary})</span>
                    )}
                  </div>
                </div>

                {/* Add-ons if any */}
                {totalAddonsUsd > 0 && (
                  <div style={{ display: 'flex', justifyContent: 'space-between', color: '#CBD5E1' }}>
                    <span>Selected Guest Experiences & Add-ons:</span>
                    <div style={{ textAlign: 'right' }}>
                      <span style={{ fontWeight: 600, color: '#FFFFFF' }}>{modalBreakdown.display.addons.primary}</span>
                      {modalBreakdown.display.addons.secondary && (
                        <span style={{ fontSize: '11px', color: '#94A3B8', marginLeft: '6px' }}>({modalBreakdown.display.addons.secondary})</span>
                      )}
                    </div>
                  </div>
                )}

                {/* Total Line */}
                <div
                  style={{
                    borderTop: '1px solid rgba(255, 255, 255, 0.12)',
                    paddingTop: '14px',
                    marginTop: '6px',
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'baseline'
                  }}
                >
                  <div>
                    <span style={{ fontSize: '15px', fontWeight: 700, color: '#FFFFFF' }}>Total Estimated Price:</span>
                    <div style={{ fontSize: '11px', color: '#94A3B8', marginTop: '2px' }}>
                      Canonical Resort Rate: USD {modalBreakdown.baseUsd.total.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                    </div>
                  </div>

                  <div style={{ textAlign: 'right' }}>
                    <div style={{ fontSize: '24px', fontWeight: 700, color: '#FCE09B' }}>
                      {modalBreakdown.display.total.primary}
                    </div>
                    {modalBreakdown.display.total.secondary && (
                      <div style={{ fontSize: '12px', color: '#CBD5E1' }}>
                        {modalBreakdown.display.total.secondary}
                      </div>
                    )}
                  </div>
                </div>
              </div>
            </div>

            {/* Modal Actions */}
            <div style={{ display: 'flex', gap: '12px', justifyContent: 'flex-end', flexWrap: 'wrap' }}>
              <button
                onClick={handleCloseModal}
                className="btn-glass"
                style={{ padding: '12px 24px', fontSize: '13px' }}
              >
                Close
              </button>

              <button
                onClick={() => {
                  handleCloseModal();
                  onSelectRoomForBooking(activeModalRoom);
                }}
                className="btn-gold"
                style={{ padding: '12px 28px', fontSize: '13px', fontWeight: 600 }}
              >
                <Sparkles size={16} />
                <span>Book with AI Concierge</span>
              </button>
            </div>
          </div>
        </div>
      )}
    </section>
  );
}
