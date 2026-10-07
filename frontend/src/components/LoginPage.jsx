import React, { useState } from 'react';
import { resortImages } from '../config/resortImages';
import { Eye, EyeOff, Sparkles, Lock, Mail, ArrowRight } from 'lucide-react';

export default function LoginPage({ onLoginSuccess }) {
  const [email, setEmail] = useState('guest@azureparadise-resort.com');
  const [password, setPassword] = useState('resort2026');
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState('');
  const [isLoading, setIsLoading] = useState(false);

  const handleSubmit = (e) => {
    e.preventDefault();
    setError('');

    if (!email.trim() || !password.trim()) {
      setError('Please provide both your email and password.');
      return;
    }

    setIsLoading(true);

    // Smooth luxury login transition
    setTimeout(() => {
      setIsLoading(false);
      onLoginSuccess({ email: email.trim() });
    }, 450);
  };

  return (
    <div
      style={{
        position: 'relative',
        width: '100vw',
        height: '100vh',
        minHeight: '600px',
        overflow: 'hidden',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        backgroundImage: `url("${resortImages.loginBackground}")`,
        backgroundSize: 'cover',
        backgroundPosition: 'center',
        backgroundRepeat: 'no-repeat'
      }}
    >
      {/* Dark / Teal Cinematic Gradient Overlay */}
      <div
        style={{
          position: 'absolute',
          inset: 0,
          background: 'linear-gradient(135deg, rgba(6, 21, 31, 0.72) 0%, rgba(10, 36, 50, 0.6) 45%, rgba(6, 21, 31, 0.85) 100%)',
          backdropFilter: 'blur(2px)',
          WebkitBackdropFilter: 'blur(2px)'
        }}
      />

      {/* Decorative Gold & Teal Light Accents */}
      <div
        style={{
          position: 'absolute',
          top: '-10%',
          right: '-5%',
          width: '500px',
          height: '500px',
          borderRadius: '50%',
          background: 'radial-gradient(circle, rgba(212, 175, 55, 0.15) 0%, transparent 70%)',
          pointerEvents: 'none'
        }}
      />
      <div
        style={{
          position: 'absolute',
          bottom: '-10%',
          left: '-5%',
          width: '550px',
          height: '550px',
          borderRadius: '50%',
          background: 'radial-gradient(circle, rgba(2, 132, 199, 0.2) 0%, transparent 70%)',
          pointerEvents: 'none'
        }}
      />

      {/* Glassmorphic Login Card */}
      <div
        className="glass-panel"
        style={{
          position: 'relative',
          zIndex: 10,
          width: '100%',
          maxWidth: '440px',
          margin: '20px',
          padding: '40px 36px',
          background: 'rgba(8, 26, 38, 0.75)',
          backdropFilter: 'blur(24px)',
          WebkitBackdropFilter: 'blur(24px)',
          border: '1px solid rgba(212, 175, 55, 0.3)',
          borderRadius: '24px',
          boxShadow: '0 30px 60px -15px rgba(0, 0, 0, 0.75), 0 0 30px rgba(212, 175, 55, 0.15)'
        }}
      >
        {/* Brand Crest & Header */}
        <div style={{ textAlign: 'center', marginBottom: '32px' }}>
          <div
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              justifyContent: 'center',
              width: '52px',
              height: '52px',
              borderRadius: '50%',
              background: 'linear-gradient(135deg, rgba(212, 175, 55, 0.2) 0%, rgba(2, 132, 199, 0.2) 100%)',
              border: '1px solid rgba(212, 175, 55, 0.4)',
              color: '#FCE09B',
              marginBottom: '16px'
            }}
          >
            <Sparkles size={24} />
          </div>

          <h1
            className="font-brand gold-gradient-text"
            style={{
              fontSize: '28px',
              fontWeight: 600,
              letterSpacing: '0.02em',
              lineHeight: 1.2,
              marginBottom: '6px'
            }}
          >
            Azure Paradise Resort
          </h1>

          <p
            style={{
              color: '#94A3B8',
              fontSize: '13px',
              letterSpacing: '0.08em',
              textTransform: 'uppercase',
              fontWeight: 500
            }}
          >
            Luxury AI-Powered Resort
          </p>
        </div>

        {/* Error Notification */}
        {error && (
          <div
            style={{
              background: 'rgba(244, 63, 94, 0.15)',
              border: '1px solid rgba(244, 63, 94, 0.4)',
              color: '#FDA4AF',
              padding: '10px 14px',
              borderRadius: '10px',
              fontSize: '13px',
              marginBottom: '20px',
              textAlign: 'center'
            }}
          >
            {error}
          </div>
        )}

        {/* Sign In Form */}
        <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
          {/* Email Field */}
          <div>
            <label
              htmlFor="login-email"
              style={{
                display: 'block',
                fontSize: '12px',
                fontWeight: 600,
                color: '#CBD5E1',
                marginBottom: '8px',
                letterSpacing: '0.04em',
                textTransform: 'uppercase'
              }}
            >
              Email Address
            </label>
            <div style={{ position: 'relative' }}>
              <input
                id="login-email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="guest@azureparadise-resort.com"
                className="luxury-input"
                style={{ paddingLeft: '40px' }}
                autoComplete="email"
                required
              />
              <Mail
                size={16}
                style={{
                  position: 'absolute',
                  left: '14px',
                  top: '50%',
                  transform: 'translateY(-50%)',
                  color: '#64748B'
                }}
              />
            </div>
          </div>

          {/* Password Field */}
          <div>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
              <label
                htmlFor="login-password"
                style={{
                  display: 'block',
                  fontSize: '12px',
                  fontWeight: 600,
                  color: '#CBD5E1',
                  letterSpacing: '0.04em',
                  textTransform: 'uppercase'
                }}
              >
                Password
              </label>
              <button
                type="button"
                onClick={(e) => {
                  e.preventDefault();
                  e.stopPropagation();
                  setShowPassword(!showPassword);
                }}
                style={{
                  background: 'none',
                  border: 'none',
                  color: '#94A3B8',
                  fontSize: '12px',
                  cursor: 'pointer',
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '4px',
                  padding: 0
                }}
              >
                {showPassword ? <EyeOff size={13} /> : <Eye size={13} />}
                <span>{showPassword ? 'Hide' : 'Show'}</span>
              </button>
            </div>
            <div style={{ position: 'relative' }}>
              <input
                id="login-password"
                type={showPassword ? 'text' : 'password'}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••••••"
                className="luxury-input"
                style={{ paddingLeft: '40px', paddingRight: '40px' }}
                autoComplete="current-password"
                required
              />
              <Lock
                size={16}
                style={{
                  position: 'absolute',
                  left: '14px',
                  top: '50%',
                  transform: 'translateY(-50%)',
                  color: '#64748B'
                }}
              />
            </div>
          </div>

          {/* Sign In CTA */}
          <button
            type="submit"
            className="btn-gold"
            disabled={isLoading}
            style={{
              width: '100%',
              padding: '14px',
              fontSize: '15px',
              marginTop: '8px',
              opacity: isLoading ? 0.8 : 1
            }}
          >
            {isLoading ? (
              <span>Entering Sanctuary...</span>
            ) : (
              <>
                <span>Sign In</span>
                <ArrowRight size={16} />
              </>
            )}
          </button>
        </form>

        {/* Subtle Luxury Footer Note */}
        <div style={{ marginTop: '28px', textAlign: 'center', borderTop: '1px solid rgba(255, 255, 255, 0.08)', paddingTop: '18px' }}>
          <p style={{ color: '#64748B', fontSize: '12px' }}>
            Azure Paradise Resort & Spa • Maui, Hawaii
          </p>
        </div>
      </div>
    </div>
  );
}
