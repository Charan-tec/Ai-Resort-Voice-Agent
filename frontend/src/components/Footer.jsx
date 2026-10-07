import React from 'react';
import { Sparkles, MapPin, Phone, Mail, Clock, ShieldCheck, Heart } from 'lucide-react';

export default function Footer({ onNavigate }) {
  const currentYear = new Date().getFullYear();

  return (
    <footer style={{
      background: 'linear-gradient(180deg, rgba(6, 21, 31, 0.75) 0%, rgba(3, 11, 17, 0.98) 100%)',
      borderTop: '1px solid rgba(212, 175, 55, 0.2)',
      padding: '64px 24px 32px',
      position: 'relative',
      zIndex: 10
    }}>
      <div style={{ maxWidth: '1200px', margin: '0 auto' }}>
        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))',
          gap: '40px',
          marginBottom: '48px'
        }}>
          {/* Resort Identity */}
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '14px' }}>
              <div style={{
                width: '32px',
                height: '32px',
                borderRadius: '8px',
                background: 'linear-gradient(135deg, var(--resort-gold) 0%, #B89628 100%)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: '#06151F',
                boxShadow: '0 4px 12px rgba(212, 175, 55, 0.3)'
              }}>
                <Sparkles size={18} />
              </div>
              <span style={{
                fontFamily: "'Cinzel', serif",
                fontSize: '20px',
                fontWeight: '700',
                letterSpacing: '0.08em',
                color: 'var(--resort-text-light)'
              }}>
                Azure Paradise
              </span>
            </div>
            <p style={{
              fontSize: '13px',
              color: 'var(--resort-text-muted)',
              lineHeight: '1.7',
              marginBottom: '20px'
            }}>
              An ultra-luxury 5-star oceanfront retreat where bespoke tropical elegance harmonizes with seamless artificial intelligence hospitality.
            </p>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--resort-gold)', fontSize: '12px' }}>
              <ShieldCheck size={14} />
              <span>Verified 5-Star Luxury Hospitality</span>
            </div>
          </div>

          {/* Quick Navigation */}
          <div>
            <h4 style={{
              fontFamily: "'Cinzel', serif",
              fontSize: '15px',
              fontWeight: '600',
              color: 'var(--resort-text-light)',
              letterSpacing: '0.06em',
              marginBottom: '18px'
            }}>
              Quick Navigation
            </h4>
            <ul style={{ listStyle: 'none', padding: 0, margin: 0, display: 'flex', flexDirection: 'column', gap: '10px', fontSize: '13px' }}>
              <li>
                <a href="#hero" style={{ color: 'var(--resort-text-muted)', textDecoration: 'none', transition: 'color 0.2s' }}
                   onMouseEnter={(e) => e.target.style.color = 'var(--resort-gold)'}
                   onMouseLeave={(e) => e.target.style.color = 'var(--resort-text-muted)'}>
                  Home & Overview
                </a>
              </li>
              <li>
                <a href="#rooms" style={{ color: 'var(--resort-text-muted)', textDecoration: 'none', transition: 'color 0.2s' }}
                   onMouseEnter={(e) => e.target.style.color = 'var(--resort-gold)'}
                   onMouseLeave={(e) => e.target.style.color = 'var(--resort-text-muted)'}>
                  Suites & Oceanfront Villas
                </a>
              </li>
              <li>
                <a href="#dining" style={{ color: 'var(--resort-text-muted)', textDecoration: 'none', transition: 'color 0.2s' }}
                   onMouseEnter={(e) => e.target.style.color = 'var(--resort-gold)'}
                   onMouseLeave={(e) => e.target.style.color = 'var(--resort-text-muted)'}>
                  Dining & Culinary Arts
                </a>
              </li>
              <li>
                <a href="#experiences" style={{ color: 'var(--resort-text-muted)', textDecoration: 'none', transition: 'color 0.2s' }}
                   onMouseEnter={(e) => e.target.style.color = 'var(--resort-gold)'}
                   onMouseLeave={(e) => e.target.style.color = 'var(--resort-text-muted)'}>
                  Resort Experiences & Spa
                </a>
              </li>
              <li>
                <a href="#concierge" style={{ color: 'var(--resort-text-muted)', textDecoration: 'none', transition: 'color 0.2s' }}
                   onMouseEnter={(e) => e.target.style.color = 'var(--resort-gold)'}
                   onMouseLeave={(e) => e.target.style.color = 'var(--resort-text-muted)'}>
                  Rachel — AI Concierge
                </a>
              </li>
              <li>
                <a href="#booking" style={{ color: 'var(--resort-text-muted)', textDecoration: 'none', transition: 'color 0.2s' }}
                   onMouseEnter={(e) => e.target.style.color = 'var(--resort-gold)'}
                   onMouseLeave={(e) => e.target.style.color = 'var(--resort-text-muted)'}>
                  My Reservation
                </a>
              </li>
            </ul>
          </div>

          {/* Contact & Location */}
          <div>
            <h4 style={{
              fontFamily: "'Cinzel', serif",
              fontSize: '15px',
              fontWeight: '600',
              color: 'var(--resort-text-light)',
              letterSpacing: '0.06em',
              marginBottom: '18px'
            }}>
              Private Sanctuary
            </h4>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', fontSize: '13px', color: 'var(--resort-text-muted)' }}>
              <div style={{ display: 'flex', alignItems: 'flex-start', gap: '10px' }}>
                <MapPin size={16} color="var(--resort-gold)" style={{ flexShrink: 0, marginTop: '2px' }} />
                <span>100 Paradise Cove Boulevard, Maui Coast, HI 96761</span>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                <Phone size={16} color="var(--resort-gold)" style={{ flexShrink: 0 }} />
                <span>+1 (808) 555-AZURE (2987)</span>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                <Mail size={16} color="var(--resort-gold)" style={{ flexShrink: 0 }} />
                <span>concierge@azureparadiseresort.com</span>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                <Clock size={16} color="var(--resort-gold)" style={{ flexShrink: 0 }} />
                <span>24/7 Dedicated AI Concierge Service</span>
              </div>
            </div>
          </div>
        </div>

        {/* Bottom Bar */}
        <div style={{
          borderTop: '1px solid rgba(255, 255, 255, 0.08)',
          paddingTop: '24px',
          display: 'flex',
          flexWrap: 'wrap',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: '16px',
          fontSize: '12px',
          color: 'var(--resort-text-muted)'
        }}>
          <div>
            © {currentYear} Azure Paradise Resort & Luxury Spa. All rights reserved.
          </div>
          <div style={{ display: 'flex', gap: '20px' }}>
            <span>Privacy Policy</span>
            <span>Terms of Service</span>
            <span>Guest Accessibility</span>
          </div>
        </div>
      </div>
    </footer>
  );
}
