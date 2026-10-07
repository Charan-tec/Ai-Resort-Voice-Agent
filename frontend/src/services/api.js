// API client & WebSocket connector for Resort AI Voice Agent backend

const PROD_BACKEND_HTTP = 'https://ai-resort-voice-agent.onrender.com';
const PROD_BACKEND_WSS = 'wss://ai-resort-voice-agent.onrender.com';

const getBaseUrl = () => {
  if (typeof window === 'undefined') return 'http://localhost:8000';
  // Local development
  if (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') {
    return 'http://localhost:8000';
  }
  // If frontend is hosted directly on the Render backend
  if (window.location.origin.includes('onrender.com')) {
    return window.location.origin;
  }
  // Production Vercel frontend or other external hosts
  return PROD_BACKEND_HTTP;
};

const getWebSocketUrl = () => {
  if (typeof window === 'undefined') return 'ws://localhost:8000/ws/media-stream?mode=dashboard';
  if (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') {
    return 'ws://localhost:8000/ws/media-stream?mode=dashboard';
  }
  if (window.location.host.includes('onrender.com')) {
    const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    return `${proto}//${window.location.host}/ws/media-stream?mode=dashboard`;
  }
  return `${PROD_BACKEND_WSS}/ws/media-stream?mode=dashboard`;
};

export const api = {
  async getReadiness() {
    try {
      const res = await fetch(`${getBaseUrl()}/health/ready`, { cache: 'no-store' });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      return await res.json();
    } catch (err) {
      return { status: 'error', error: err.message, ready_for_real_calls: false };
    }
  },

  async getAgentState() {
    try {
      const res = await fetch(`${getBaseUrl()}/api/agent/state`, { cache: 'no-store' });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      return await res.json();
    } catch (err) {
      return null;
    }
  },

  async getRecentBookings() {
    try {
      const res = await fetch(`${getBaseUrl()}/api/bookings`, { cache: 'no-store' });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      return await res.json();
    } catch (err) {
      return { bookings: [] };
    }
  },

  async getPricingCurrencies() {
    try {
      const res = await fetch(`${getBaseUrl()}/api/pricing/currencies`, { cache: 'no-store' });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      return await res.json();
    } catch (err) {
      return null;
    }
  },

  async getRooms() {
    try {
      const res = await fetch(`${getBaseUrl()}/api/rooms`, { cache: 'no-store' });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      return await res.json();
    } catch (err) {
      return null;
    }
  },

  async calculatePricing(params) {
    const res = await fetch(`${getBaseUrl()}/api/pricing/calculate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(params)
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return await res.json();
  },

  async simulateDemoTurn(prompt) {
    const res = await fetch(`${getBaseUrl()}/api/demo/simulate-turn`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ prompt })
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return await res.json();
  },

  async clearConversation() {
    try {
      const res = await fetch(`${getBaseUrl()}/api/conversation/clear`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' }
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      return await res.json();
    } catch (err) {
      console.debug('clearConversation error:', err);
      return { status: 'ok' };
    }
  }
};

export class DashboardWebSocket {
  constructor(onEvent, onStatusChange) {
    this.onEvent = onEvent;
    this.onStatusChange = onStatusChange;
    this.ws = null;
    this.shouldReconnect = true;
    this.reconnectAttempts = 0;
    this.reconnectTimer = null;
    this.pingInterval = null;
  }

  connect() {
    const url = getWebSocketUrl();
    this.onStatusChange('connecting');

    try {
      this.ws = new WebSocket(url);

      this.ws.onopen = () => {
        this.reconnectAttempts = 0;
        this.onStatusChange('connected');
        // Heartbeat
        this.pingInterval = setInterval(() => {
          if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            this.ws.send(JSON.stringify({ event: 'ping' }));
          }
        }, 15000);
      };

      this.ws.onmessage = (evt) => {
        try {
          const payload = JSON.parse(evt.data);
          this.onEvent(payload);
        } catch (e) {
          console.debug('Non-JSON WS message', evt.data);
        }
      };

      this.onerror = (err) => {
        console.debug('WS Error:', err);
      };

      this.ws.onclose = () => {
        clearInterval(this.pingInterval);
        this.onStatusChange('disconnected');
        if (this.shouldReconnect) {
          const delay = Math.min(1000 * Math.pow(1.5, this.reconnectAttempts), 10000);
          this.reconnectAttempts++;
          this.reconnectTimer = setTimeout(() => this.connect(), delay);
        }
      };
    } catch (err) {
      this.onStatusChange('error');
    }
  }

  disconnect() {
    this.shouldReconnect = false;
    clearInterval(this.pingInterval);
    clearTimeout(this.reconnectTimer);
    if (this.ws) {
      this.ws.close();
    }
  }
}
