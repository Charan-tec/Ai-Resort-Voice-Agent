import React from 'react';
import { resortImages } from '../config/resortImages';
import { Sparkles, PhoneCall, BedDouble, Compass, ShieldCheck } from 'lucide-react';

export default function HeroSection({ onExploreRooms, onTalkToConcierge }) {
  return (
    <section
      id="hero"
      style={{
        position: 'relative',
        minHeight: '88vh',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '120px 24px 60px',
        overflow: 'hidden'
      }}
    >
      {/* Hero Visual Card Frame */}
      <div
        style={{
          position: 'absolute',
          inset: '20px 20px 0',
          borderRadius: '32px',
          overflow: 'hidden',
          backgroundImage: `url("${resortImages.hero}")`,
          backgroundSize: 'cover',
          backgroundPosition: 'center 40%',
          boxShadow: '0 30px 80px rgba(0, 0, 0, 0.8)'
        }}
      >
        {/* Layered Tropical Twilight Gradient Overlay */}
        <div
          style={{
            position: 'absolute',
            inset: 0,
            background: 'linear-gradient(180deg, rgba(6, 21, 31, 0.5) 0%, rgba(6, 21, 31, 0.75) 60%, rgba(6, 21, 31, 0.95) 100%)'
          }}
        />
        <div
          style={{
            position: 'absolute',
            inset: 0,
            background: 'radial-gradient(circle at 50% 30%, transparent 20%, rgba(6, 21, 31, 0.8) 100%)'
          }}
        />
      </div>

      {/* Hero Center Content */}
      <div
        style={{
          position: 'relative',
          zIndex: 10,
          maxWidth: '920px',
          margin: '0 auto',
          textAlign: 'center',
          padding: '40px 20px'
        }}
      >
        {/* Top Eyebrow Tag */}
        <div
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: '8px',
            padding: '6px 18px',
            borderRadius: '9999px',
            background: 'rgba(212, 175, 55, 0.18)',
            border: '1px solid rgba(212, 175, 55, 0.4)',
            color: '#FCE09B',
            fontSize: '12px',
            fontWeight: 600,
            letterSpacing: '0.14em',
            textTransform: 'uppercase',
            marginBottom: '24px',
            boxShadow: '0 4px 20px rgba(212, 175, 55, 0.2)'
          }}
        >
          <Sparkles size={14} />
          <span>Hawaiian Oceanfront Sanctuary • Maui</span>
        </div>

        {/* Hero Title */}
        <h1
          className="font-brand"
          style={{
            fontSize: 'clamp(38px, 6vw, 68px)',
            fontWeight: 600,
            color: '#FFFFFF',
            letterSpacing: '-0.02em',
            lineHeight: 1.1,
            marginBottom: '20px',
            textShadow: '0 4px 30px rgba(0, 0, 0, 0.7)'
          }}
        >
          Welcome to <span className="gold-gradient-text">Azure Paradise Resort</span>
        </h1>

        {/* Subtitle */}
        <p
          style={{
            fontSize: 'clamp(16px, 2.2vw, 20px)',
            color: '#E2E8F0',
            fontWeight: 300,
            lineHeight: 1.6,
            maxWidth: '680px',
            margin: '0 auto 36px',
            textShadow: '0 2px 10px rgba(0, 0, 0, 0.5)'
          }}
        >
          Luxury, comfort and intelligent hospitality — all in one place.
        </p>

        {/* Call-to-Action Buttons */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            gap: '16px',
            flexWrap: 'wrap'
          }}
        >
          <button
            onClick={onExploreRooms}
            className="btn-gold"
            style={{
              padding: '16px 36px',
              fontSize: '15px',
              fontWeight: 600
            }}
          >
            <BedDouble size={18} />
            <span>Explore Rooms</span>
          </button>

          <button
            onClick={onTalkToConcierge}
            className="btn-glass"
            style={{
              padding: '16px 36px',
              fontSize: '15px',
              fontWeight: 600,
              background: 'rgba(255, 255, 255, 0.1)',
              borderColor: 'rgba(212, 175, 55, 0.4)'
            }}
          >
            <PhoneCall size={18} style={{ color: '#38BDF8' }} />
            <span>Talk to AI Concierge</span>
          </button>
        </div>

        {/* Resort Features Highlights Row */}
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))',
            gap: '16px',
            marginTop: '56px',
            maxWidth: '780px',
            marginLeft: 'auto',
            marginRight: 'auto'
          }}
        >
          <div
            style={{
              padding: '16px',
              borderRadius: '16px',
              background: 'rgba(6, 21, 31, 0.65)',
              backdropFilter: 'blur(12px)',
              border: '1px solid rgba(255, 255, 255, 0.1)',
              textAlign: 'center'
            }}
          >
            <div style={{ color: '#FCE09B', fontWeight: 600, fontSize: '18px', marginBottom: '4px' }}>
              6 Private Sanctuaries
            </div>
            <div style={{ color: '#94A3B8', fontSize: '12px' }}>Oceanfront Villas & Suites</div>
          </div>

          <div
            style={{
              padding: '16px',
              borderRadius: '16px',
              background: 'rgba(6, 21, 31, 0.65)',
              backdropFilter: 'blur(12px)',
              border: '1px solid rgba(255, 255, 255, 0.1)',
              textAlign: 'center'
            }}
          >
            <div style={{ color: '#38BDF8', fontWeight: 600, fontSize: '18px', marginBottom: '4px' }}>
              Real-time Voice AI
            </div>
            <div style={{ color: '#94A3B8', fontSize: '12px' }}>Instant Concierge & Booking</div>
          </div>

          <div
            style={{
              padding: '16px',
              borderRadius: '16px',
              background: 'rgba(6, 21, 31, 0.65)',
              backdropFilter: 'blur(12px)',
              border: '1px solid rgba(255, 255, 255, 0.1)',
              textAlign: 'center'
            }}
          >
            <div style={{ color: '#4ADE80', fontWeight: 600, fontSize: '18px', marginBottom: '4px' }}>
              Private Oceanfront
            </div>
            <div style={{ color: '#94A3B8', fontSize: '12px' }}>Cliffside Infinity Pools</div>
          </div>
        </div>
      </div>
    </section>
  );
}
