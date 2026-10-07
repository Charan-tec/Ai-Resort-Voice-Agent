import React from 'react';
import { resortImages } from '../config/resortImages';
import { Utensils, Clock, Sparkles, MessageSquare } from 'lucide-react';

const DINING_EXPERIENCES = [
  {
    title: 'Oceanfront Fine Dining',
    venue: 'Azure Ocean Grill',
    description: 'Savor Pacific Rim delicacies, line-caught seafood, and prime Hawaiian wagyu seated just feet from gentle ocean waves.',
    hours: '5:30 PM – 10:00 PM',
    highlight: 'Award-winning Pacific Rim Cuisine',
    image: resortImages.dining.fineDining
  },
  {
    title: 'Tropical Breakfast',
    venue: 'Palm Terrace',
    description: 'Awaken your senses with exotic Hawaiian fruit harvests, house-baked pastries, artisanal avocado toasts, and 100% Kona reserve coffee.',
    hours: '6:30 AM – 11:00 AM',
    highlight: 'Gourmet Island Breakfast Buffet',
    image: resortImages.dining.breakfast
  },
  {
    title: 'Sunset Restaurant',
    venue: 'Sunset Terrace',
    description: 'An open-air culinary theatre bathed in the crimson hues of dusk, featuring sommelier reserve vintages and wood-fired preparations.',
    hours: '5:00 PM – 9:30 PM',
    highlight: 'Panoramic Sunset Dining',
    image: resortImages.dining.sunsetDining
  },
  {
    title: 'Poolside Dining',
    venue: 'Azure Lagoon Bar',
    description: 'Relax with light island poke bowls, wood-fired flatbreads, and chilled artisan cocktails delivered directly to your water-lounge cabana.',
    hours: '11:00 AM – 7:00 PM',
    highlight: 'Waterfront Bites & Craft Cocktails',
    image: resortImages.dining.poolside
  },
  {
    title: 'Private Villa Dining',
    venue: 'Bespoke In-Villa Experience',
    description: 'Indulge in a customized multi-course culinary journey orchestrated in your private villa terrace by your personal executive chef.',
    hours: 'Available 24 Hours on Request',
    highlight: 'Personal Executive Chef & Butler',
    image: resortImages.dining.privateDining
  },
  {
    title: 'Premium Desserts & Cocktails',
    venue: 'Sunset Lounge',
    description: 'Conclude your evenings with decadent passionfruit soufflés, rare vintage rums, craft mixology, and acoustic Polynesian music.',
    hours: '4:00 PM – Midnight',
    highlight: 'Artisanal Mixology & Live Music',
    image: resortImages.dining.desserts
  }
];

export default function DiningSection({ onInquireDining }) {
  return (
    <section id="dining" style={{ padding: '80px 24px', maxWidth: '1440px', margin: '0 auto' }}>
      {/* Section Header */}
      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', textAlign: 'center', marginBottom: '48px' }}>
        <span className="section-tag">CULINARY ARTS</span>
        <h2 className="section-title">
          Dining & <span className="gold-gradient-text">Gastronomy</span>
        </h2>
        <p className="section-desc">
          From sunrise Kona espresso overlooking the Pacific to torchlit private beach dining, experience culinary mastery rooted in fresh island produce.
        </p>
      </div>

      {/* 6 Dining Cards Grid */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(340px, 1fr))',
          gap: '28px'
        }}
      >
        {DINING_EXPERIENCES.map((exp, idx) => (
          <div
            key={idx}
            className="glass-card-interactive"
            style={{
              display: 'flex',
              flexDirection: 'column',
              background: 'rgba(8, 26, 38, 0.82)',
              borderRadius: '24px'
            }}
          >
            {/* Image Container */}
            <div
              className="img-zoom-container"
              style={{
                width: '100%',
                height: '220px',
                position: 'relative'
              }}
            >
              <img
                src={exp.image}
                alt={exp.title}
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
                  background: 'linear-gradient(180deg, rgba(6, 21, 31, 0.2) 0%, rgba(6, 21, 31, 0.85) 100%)'
                }}
              />

              <span
                className="badge-gold"
                style={{
                  position: 'absolute',
                  top: '16px',
                  left: '16px',
                  background: 'rgba(6, 21, 31, 0.8)',
                  backdropFilter: 'blur(8px)'
                }}
              >
                {exp.venue}
              </span>
            </div>

            {/* Dining Content */}
            <div style={{ padding: '24px', display: 'flex', flexDirection: 'column', flex: 1 }}>
              <h3
                className="font-brand"
                style={{ fontSize: '20px', fontWeight: 600, color: '#FFFFFF', marginBottom: '6px' }}
              >
                {exp.title}
              </h3>

              {/* Service Hours */}
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px', color: '#94A3B8', fontSize: '12px', marginBottom: '14px' }}>
                <Clock size={13} style={{ color: '#FCE09B' }} />
                <span>{exp.hours}</span>
              </div>

              {/* Description */}
              <p style={{ color: '#CBD5E1', fontSize: '13px', lineHeight: 1.6, marginBottom: '20px', flex: 1 }}>
                {exp.description}
              </p>

              {/* Highlight Pill & Inquire Button */}
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', borderTop: '1px solid rgba(255, 255, 255, 0.08)', paddingTop: '16px', gap: '10px' }}>
                <span style={{ fontSize: '11px', color: '#38BDF8', fontWeight: 600 }}>
                  {exp.highlight}
                </span>

                <button
                  onClick={() => onInquireDining(exp.title)}
                  style={{
                    background: 'rgba(255, 255, 255, 0.06)',
                    border: '1px solid rgba(212, 175, 55, 0.3)',
                    color: '#FCE09B',
                    borderRadius: '9999px',
                    padding: '6px 14px',
                    fontSize: '11px',
                    fontWeight: 600,
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '4px',
                    transition: 'all 0.2s ease'
                  }}
                  onMouseEnter={(e) => {
                    e.currentTarget.style.background = 'rgba(212, 175, 55, 0.2)';
                    e.currentTarget.style.borderColor = '#D4AF37';
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.background = 'rgba(255, 255, 255, 0.06)';
                    e.currentTarget.style.borderColor = 'rgba(212, 175, 55, 0.3)';
                  }}
                >
                  <MessageSquare size={12} />
                  <span>Ask Concierge</span>
                </button>
              </div>
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}
