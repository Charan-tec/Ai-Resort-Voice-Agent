import React from 'react';
import { resortImages } from '../config/resortImages';
import { Sparkles, Sun, Waves, Compass, Flame, Flower2, HeartHandshake } from 'lucide-react';

const EXPERIENCES = [
  {
    title: 'Cliffside Infinity Pool',
    category: 'Water & Leisure',
    tagline: 'Heated oceanfront waters merging with the Maui horizon.',
    image: resortImages.experiences.infinityPool,
    description: 'Immerse yourself in three cascading heated infinity pools overlooking turquoise reefs, complete with sunken lounge bars and poolside butler service.'
  },
  {
    title: 'Secluded Private Beach',
    category: 'Coastal Sanctuary',
    tagline: 'Pristine white coral sands sheltered by volcanic headlands.',
    image: resortImages.experiences.privateBeach,
    description: 'Reserved exclusively for guests, our tranquil cove offers shaded mahogany cabanas, refreshing coconut water service, and calm waters ideal for sunbathing.'
  },
  {
    title: 'The Serenity Spa & Wellness',
    category: 'Holistic Rejuvenation',
    tagline: 'Hawaiian Lomi Lomi and restorative volcanic stone therapies.',
    image: resortImages.experiences.spa,
    description: 'Open daily from 8:00 AM to 8:00 PM. Reclaim tranquility in private ocean-breeze pavilions with ancient Polynesian botanicals and couples massage suites.'
  },
  {
    title: 'Champagne Sunset Catamaran',
    category: 'Island Exploration',
    tagline: 'Golden-hour ocean sails accompanied by vintage champagne.',
    image: resortImages.experiences.sunset,
    description: 'Board our luxury resort catamaran at dusk to witness unforgettable Pacific sunsets, spinner dolphins, and seasonal humpback whale breaches.'
  },
  {
    title: 'Coral Reef Snorkeling & Watersports',
    category: 'Adventure',
    tagline: 'Pristine marine sanctuaries and guided paddleboard safaris.',
    image: resortImages.experiences.watersports,
    description: 'Explore vibrant coral reefs with master naturalists, complimentary stand-up paddleboards, sea kayaks, and certified PADI scuba diving tours.'
  },
  {
    title: 'Tropical Botanical Gardens',
    category: 'Zen & Nature',
    tagline: 'Ancient orchid pavilions and fragrant plumeria walking paths.',
    image: resortImages.experiences.gardens,
    description: 'Stroll winding stone pathways flanked by tropical palms, tranquil koi ponds, and morning beach yoga decks surrounded by native Hawaiian flora.'
  },
  {
    title: 'Starlight Fire-Pit Lounge',
    category: 'Evening Social',
    tagline: 'Artisan craft mixology around crackling volcanic fire pits.',
    image: resortImages.experiences.lounge,
    description: 'Unwind beneath the Pacific night sky with acoustic slack-key guitar performances, signature tropical cocktails, and guided astronomy sessions.'
  }
];

export default function ExperiencesSection({ onInquireExperience }) {
  return (
    <section id="experiences" style={{ padding: '80px 24px', maxWidth: '1440px', margin: '0 auto' }}>
      {/* Section Header */}
      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', textAlign: 'center', marginBottom: '48px' }}>
        <span className="section-tag">ISLAND SANCTUARY</span>
        <h2 className="section-title">
          Curated Resort <span className="gold-gradient-text">Experiences</span>
        </h2>
        <p className="section-desc">
          Craft unforgettable memories with bespoke excursions, holistic wellness sanctuaries, and legendary Hawaiian warmth.
        </p>
      </div>

      {/* Experiences Grid */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))',
          gap: '24px'
        }}
      >
        {EXPERIENCES.map((exp, idx) => (
          <div
            key={idx}
            className="glass-card-interactive"
            style={{
              position: 'relative',
              height: '340px',
              borderRadius: '24px',
              display: 'flex',
              flexDirection: 'column',
              justifyContent: 'flex-end',
              overflow: 'hidden'
            }}
          >
            {/* Background Image */}
            <img
              src={exp.image}
              alt={exp.title}
              loading="lazy"
              style={{
                position: 'absolute',
                inset: 0,
                width: '100%',
                height: '100%',
                objectFit: 'cover',
                transition: 'transform 0.6s ease'
              }}
            />

            {/* Gradient Overlay for Contrast */}
            <div
              style={{
                position: 'absolute',
                inset: 0,
                background: 'linear-gradient(180deg, rgba(6, 21, 31, 0.1) 0%, rgba(6, 21, 31, 0.6) 45%, rgba(6, 21, 31, 0.95) 100%)'
              }}
            />

            {/* Top Category Badge */}
            <span
              className="badge-gold"
              style={{
                position: 'absolute',
                top: '18px',
                left: '18px',
                background: 'rgba(6, 21, 31, 0.8)',
                backdropFilter: 'blur(8px)',
                zIndex: 2
              }}
            >
              {exp.category}
            </span>

            {/* Card Content Overlay */}
            <div style={{ position: 'relative', zIndex: 2, padding: '24px' }}>
              <h3
                className="font-brand"
                style={{ fontSize: '22px', fontWeight: 600, color: '#FFFFFF', marginBottom: '6px' }}
              >
                {exp.title}
              </h3>

              <p
                style={{
                  color: '#FCE09B',
                  fontSize: '12px',
                  fontWeight: 500,
                  marginBottom: '8px'
                }}
              >
                {exp.tagline}
              </p>

              <p
                style={{
                  color: '#CBD5E1',
                  fontSize: '12px',
                  lineHeight: 1.5,
                  display: '-webkit-box',
                  WebkitLineClamp: 2,
                  WebkitBoxOrient: 'vertical',
                  overflow: 'hidden'
                }}
              >
                {exp.description}
              </p>
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}
