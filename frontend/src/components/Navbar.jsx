import React, { useState, useEffect } from 'react';
import { Sparkles, Menu, X, LogOut, PhoneCall, CalendarCheck } from 'lucide-react';
import CurrencySelectorModal from './CurrencySelectorModal';

export default function Navbar({
  onLogout,
  onNavigate,
  activeSection,
  bookingCount = 0,
  selectedCountry = 'IN',
  selectedCurrency = 'INR',
  onSelectCountry,
  onSelectCurrency
}) {
  const [isScrolled, setIsScrolled] = useState(false);
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);

  useEffect(() => {
    const handleScroll = () => {
      setIsScrolled(window.scrollY > 20);
    };
    window.addEventListener('scroll', handleScroll);
    return () => window.removeEventListener('scroll', handleScroll);
  }, []);

  const navLinks = [
    { label: 'Home', href: '#hero' },
    { label: 'Rooms & Villas', href: '#rooms' },
    { label: 'Dining', href: '#dining' },
    { label: 'Experiences', href: '#experiences' },
    { label: 'AI Concierge', href: '#ai-concierge', icon: PhoneCall },
    { label: 'My Booking', href: '#my-booking', badge: bookingCount > 0 ? bookingCount : null }
  ];

  const handleLinkClick = (href) => {
    setIsMobileMenuOpen(false);
    if (onNavigate) {
      onNavigate(href);
    } else {
      const el = document.querySelector(href);
      if (el) {
        el.scrollIntoView({ behavior: 'smooth' });
      }
    }
  };

  return (
    <header
      style={{
        position: 'fixed',
        top: 0,
        left: 0,
        right: 0,
        zIndex: 100,
        padding: isScrolled ? '12px 24px' : '20px 32px',
        background: isScrolled
          ? 'rgba(6, 21, 31, 0.88)'
          : 'linear-gradient(180deg, rgba(6, 21, 31, 0.75) 0%, rgba(6, 21, 31, 0) 100%)',
        backdropFilter: isScrolled ? 'blur(20px)' : 'blur(8px)',
        WebkitBackdropFilter: isScrolled ? 'blur(20px)' : 'blur(8px)',
        borderBottom: isScrolled ? '1px solid rgba(255, 255, 255, 0.1)' : '1px solid transparent',
        transition: 'all 0.3s ease'
      }}
    >
      <div
        style={{
          maxWidth: '1440px',
          margin: '0 auto',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between'
        }}
      >
        {/* Brand Crest */}
        <a
          href="#hero"
          onClick={(e) => {
            e.preventDefault();
            handleLinkClick('#hero');
          }}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '10px',
            textDecoration: 'none',
            color: '#FFFFFF'
          }}
        >
          <div
            style={{
              width: '38px',
              height: '38px',
              borderRadius: '50%',
              background: 'linear-gradient(135deg, rgba(212, 175, 55, 0.25) 0%, rgba(2, 132, 199, 0.25) 100%)',
              border: '1px solid rgba(212, 175, 55, 0.5)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: '#FCE09B'
            }}
          >
            <Sparkles size={18} />
          </div>
          <div>
            <span
              className="font-brand gold-gradient-text"
              style={{
                fontSize: '20px',
                fontWeight: 600,
                letterSpacing: '0.02em',
                display: 'block',
                lineHeight: 1.1
              }}
            >
              Azure Paradise Resort
            </span>
            <span
              style={{
                fontSize: '10px',
                letterSpacing: '0.12em',
                textTransform: 'uppercase',
                color: '#94A3B8',
                display: 'block'
              }}
            >
              Maui • Hawaii
            </span>
          </div>
        </a>

        {/* Right Area: Currency Selector + Nav Links / Mobile Menu */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '14px' }}>
          {/* International Country & Currency Compact Selector */}
          <CurrencySelectorModal
            selectedCountry={selectedCountry}
            selectedCurrency={selectedCurrency}
            onSelectCountry={onSelectCountry}
            onSelectCurrency={onSelectCurrency}
          />

          {/* Desktop Navigation Links */}
          <nav
            style={{
              display: 'none',
              alignItems: 'center',
              gap: '24px'
            }}
            className="desktop-nav"
          >
            {navLinks.map((link) => (
              <a
                key={link.label}
                href={link.href}
                onClick={(e) => {
                  e.preventDefault();
                  handleLinkClick(link.href);
                }}
                style={{
                  color: activeSection === link.href ? '#FCE09B' : '#E2E8F0',
                  textDecoration: 'none',
                  fontSize: '13px',
                  fontWeight: 500,
                  letterSpacing: '0.02em',
                  transition: 'color 0.2s ease',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '6px',
                  position: 'relative'
                }}
                onMouseEnter={(e) => (e.currentTarget.style.color = '#FCE09B')}
                onMouseLeave={(e) => {
                  if (activeSection !== link.href) {
                    e.currentTarget.style.color = '#E2E8F0';
                  }
                }}
              >
                {link.icon && <link.icon size={14} style={{ color: '#38BDF8' }} />}
                <span>{link.label}</span>
                {link.badge && (
                  <span
                    style={{
                      background: 'rgba(212, 175, 55, 0.25)',
                      border: '1px solid rgba(212, 175, 55, 0.5)',
                      color: '#FCE09B',
                      fontSize: '10px',
                      padding: '1px 6px',
                      borderRadius: '9999px',
                      fontWeight: 700
                    }}
                  >
                    {link.badge}
                  </span>
                )}
              </a>
            ))}

            {/* Logout Button */}
            <button
              onClick={onLogout}
              style={{
                background: 'rgba(255, 255, 255, 0.06)',
                border: '1px solid rgba(255, 255, 255, 0.15)',
                color: '#CBD5E1',
                borderRadius: '9999px',
                padding: '7px 16px',
                fontSize: '12px',
                fontWeight: 500,
                cursor: 'pointer',
                display: 'inline-flex',
                alignItems: 'center',
                gap: '6px',
                transition: 'all 0.2s ease'
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.background = 'rgba(244, 63, 94, 0.15)';
                e.currentTarget.style.color = '#FDA4AF';
                e.currentTarget.style.borderColor = 'rgba(244, 63, 94, 0.3)';
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.background = 'rgba(255, 255, 255, 0.06)';
                e.currentTarget.style.color = '#CBD5E1';
                e.currentTarget.style.borderColor = 'rgba(255, 255, 255, 0.15)';
              }}
            >
              <LogOut size={13} />
              <span>Logout</span>
            </button>
          </nav>

          {/* Mobile Hamburger Button */}
          <button
            onClick={() => setIsMobileMenuOpen(!isMobileMenuOpen)}
            className="mobile-nav-toggle"
            style={{
              background: 'rgba(255, 255, 255, 0.08)',
              border: '1px solid rgba(255, 255, 255, 0.15)',
              color: '#FFFFFF',
              borderRadius: '8px',
              padding: '8px',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center'
            }}
            aria-label="Toggle navigation menu"
          >
            {isMobileMenuOpen ? <X size={20} /> : <Menu size={20} />}
          </button>
        </div>
      </div>

      {/* Mobile Menu Drawer */}
      {isMobileMenuOpen && (
        <div
          style={{
            position: 'absolute',
            top: '100%',
            left: 0,
            right: 0,
            background: 'rgba(6, 21, 31, 0.96)',
            backdropFilter: 'blur(24px)',
            WebkitBackdropFilter: 'blur(24px)',
            borderBottom: '1px solid rgba(212, 175, 55, 0.25)',
            padding: '24px',
            display: 'flex',
            flexDirection: 'column',
            gap: '16px',
            boxShadow: '0 20px 40px rgba(0, 0, 0, 0.7)'
          }}
        >
          {navLinks.map((link) => (
            <a
              key={link.label}
              href={link.href}
              onClick={(e) => {
                e.preventDefault();
                handleLinkClick(link.href);
              }}
              style={{
                color: '#E2E8F0',
                textDecoration: 'none',
                fontSize: '15px',
                fontWeight: 500,
                padding: '10px 14px',
                borderRadius: '8px',
                background: 'rgba(255, 255, 255, 0.04)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between'
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                {link.icon && <link.icon size={16} style={{ color: '#38BDF8' }} />}
                <span>{link.label}</span>
              </div>
              {link.badge && (
                <span
                  style={{
                    background: 'rgba(212, 175, 55, 0.25)',
                    color: '#FCE09B',
                    fontSize: '11px',
                    padding: '2px 8px',
                    borderRadius: '9999px',
                    fontWeight: 700
                  }}
                >
                  {link.badge}
                </span>
              )}
            </a>
          ))}

          <button
            onClick={() => {
              setIsMobileMenuOpen(false);
              onLogout();
            }}
            style={{
              background: 'rgba(244, 63, 94, 0.15)',
              border: '1px solid rgba(244, 63, 94, 0.3)',
              color: '#FDA4AF',
              borderRadius: '8px',
              padding: '12px',
              fontSize: '14px',
              fontWeight: 500,
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '8px',
              marginTop: '8px'
            }}
          >
            <LogOut size={16} />
            <span>Sign Out</span>
          </button>
        </div>
      )}

      {/* Responsive Inline CSS */}
      <style>{`
        @media (min-width: 992px) {
          .desktop-nav {
            display: flex !important;
          }
          .mobile-nav-toggle {
            display: none !important;
          }
        }
      `}</style>
    </header>
  );
}
