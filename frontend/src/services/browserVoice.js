// Production-Quality Browser Voice Service for Azure Paradise Resort AI Voice Agent
// Manages getUserMedia, Web Audio API streaming, real-time barge-in, Web Speech API fallback, and WebSocket transport

const getBrowserVoiceWsUrl = () => {
  if (typeof window === 'undefined') return 'ws://localhost:8000/ws/browser-voice';
  const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  if (window.location.port === '5173') {
    return 'ws://localhost:8000/ws/browser-voice';
  }
  return `${proto}//${window.location.host}/ws/browser-voice`;
};

export class BrowserVoiceManager {
  constructor({
    onStateChange,
    onTranscript,
    onAudioLevel,
    onError,
    onBargeIn
  }) {
    this.onStateChange = onStateChange || (() => {});
    this.onTranscript = onTranscript || (() => {});
    this.onAudioLevel = onAudioLevel || (() => {});
    this.onError = onError || (() => {});
    this.onBargeIn = onBargeIn || (() => {});

    // State
    this.state = 'IDLE'; // IDLE, LISTENING, THINKING, SPEAKING, BARGED_IN, ERROR, RECONNECTING
    this.isMuted = false;
    this.sessionId = null;

    // Web Audio
    this.audioContext = null;
    this.micStream = null;
    this.micSource = null;
    this.scriptProcessor = null;
    this.analyser = null;
    this.silentGain = null;
    this._micSamples8k = [];

    // Playback Queue & Barge-In
    this.activeSources = [];
    this.nextPlayTime = 0;
    this.isAgentSpeaking = false;
    this._lastPlayedSeq = 0;

    // WebSocket
    this.ws = null;
    this.shouldReconnect = false;
    this.reconnectAttempts = 0;
    this.reconnectTimer = null;
    this.pingInterval = null;

    // Web Speech API fallback
    this.speechRecognition = null;
  }

  // Set internal and UI state
  setState(newState) {
    if (this.state === newState) return;
    this.state = newState;
    this.isAgentSpeaking = (newState === 'SPEAKING');
    this.onStateChange(newState);
  }

  // 1. START VOICE CONVERSATION
  async start() {
    this.shouldReconnect = true;
    this.reconnectAttempts = 0;
    this.setState('CONNECTING');

    try {
      // 1. Request microphone permission
      let stream;
      try {
        stream = await navigator.mediaDevices.getUserMedia({
          audio: {
            channelCount: 1,
            echoCancellation: true,
            noiseSuppression: true,
            autoGainControl: true
          }
        });
      } catch (micErr) {
        if (micErr.name === 'NotAllowedError' || micErr.name === 'PermissionDeniedError') {
          throw new Error('Microphone permission was denied. Please allow microphone access in your browser settings.');
        } else if (micErr.name === 'NotFoundError') {
          throw new Error('No microphone device found on your system.');
        } else {
          throw new Error(`Microphone error: ${micErr.message}`);
        }
      }

      this.micStream = stream;

      // 2. Initialize Web Audio Context at native hardware sample rate
      const AudioCtxClass = window.AudioContext || window.webkitAudioContext;
      this.audioContext = new AudioCtxClass();
      if (this.audioContext.state === 'suspended') {
        await this.audioContext.resume();
      }
      this._micSamples8k = [];
      this._lastPlayedSeq = 0;

      // 3. Connect to Backend WebSocket
      await this._connectWebSocket();

      // 4. Setup microphone audio processing & visualizer
      this._setupMicrophoneAudio(stream);

    } catch (err) {
      console.error('Failed to start voice conversation:', err);
      this.setState('ERROR');
      this.onError(err.message || 'Could not connect to voice service.');
      this.stop();
    }
  }

  // 2. STOP VOICE CONVERSATION
  stop() {
    this.shouldReconnect = false;
    clearTimeout(this.reconnectTimer);
    clearInterval(this.pingInterval);

    // Stop playback immediately
    this._stopAllPlayback();
    this._micSamples8k = [];

    // Stop Speech Recognition
    if (this.speechRecognition) {
      try {
        this.speechRecognition.stop();
      } catch (e) {}
      this.speechRecognition = null;
    }

    // Stop microphone tracks
    if (this.micStream) {
      this.micStream.getTracks().forEach((track) => track.stop());
      this.micStream = null;
    }

    // Disconnect Web Audio nodes
    if (this.silentGain) {
      try { this.silentGain.disconnect(); } catch (e) {}
      this.silentGain = null;
    }
    if (this.scriptProcessor) {
      try { this.scriptProcessor.disconnect(); } catch (e) {}
      this.scriptProcessor = null;
    }
    if (this.micSource) {
      try { this.micSource.disconnect(); } catch (e) {}
      this.micSource = null;
    }
    if (this.analyser) {
      try { this.analyser.disconnect(); } catch (e) {}
      this.analyser = null;
    }
    if (this.audioContext && this.audioContext.state !== 'closed') {
      try { this.audioContext.close(); } catch (e) {}
      this.audioContext = null;
    }

    // Close WebSocket
    if (this.ws) {
      if (this.ws.readyState === WebSocket.OPEN) {
        try {
          this.ws.send(JSON.stringify({ event: 'stop' }));
        } catch (e) {}
      }
      try {
        this.ws.close();
      } catch (e) {}
      this.ws = null;
    }

    this.onAudioLevel(0);
    this.setState('IDLE');
  }

  // 3. MUTE / UNMUTE
  toggleMute() {
    this.isMuted = !this.isMuted;
    this._micSamples8k = []; // Clear any residual microphone samples immediately
    if (this.micStream) {
      this.micStream.getAudioTracks().forEach((track) => {
        track.enabled = !this.isMuted;
      });
    }
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({ event: 'mute', muted: this.isMuted }));
    }
    return this.isMuted;
  }

  // 4. TRIGGER BARGE-IN
  triggerBargeIn() {
    // 1. Immediately cut all browser audio output
    this._stopAllPlayback();
    this.setState('BARGED_IN');
    this.onBargeIn();

    // 2. Notify backend to flush pacer queue & cancel LLM/TTS tasks
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({ event: 'barge_in' }));
    }

    // 3. Transition back to listening after brief interruption animation
    setTimeout(() => {
      if (this.state === 'BARGED_IN') {
        this.setState('LISTENING');
      }
    }, 400);
  }

  // 5. SEND DIRECT TEXT TURN (Fallback for quiet / typing interaction)
  sendTextTurn(text) {
    if (!text || !text.trim()) return;
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.setState('THINKING');
      this.ws.send(JSON.stringify({
        event: 'transcript',
        text: text.trim(),
        is_final: true
      }));
    }
  }

  // 6. CLEAR CONVERSATION & RESET SESSION STATE
  clearConversation() {
    // 1. Immediately stop any pending or playing audio chunks
    this._stopAllPlayback();
    this._micSamples8k = [];

    // 2. Abort & restart SpeechRecognition if active to purge interim speech buffers
    if (this.speechRecognition) {
      try {
        this.speechRecognition.abort();
      } catch (e) {}
      if (this.state !== 'IDLE' && this.state !== 'ERROR') {
        try {
          this.speechRecognition.start();
        } catch (e) {}
      }
    }

    // 3. Notify backend voice WebSocket to reset active session state & pacer
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      try {
        this.ws.send(JSON.stringify({
          event: 'clear_conversation',
          session_id: this.sessionId
        }));
      } catch (e) {
        console.debug('Failed to send clear_conversation over browser voice WS:', e);
      }
    }

    // 4. Return to LISTENING if it was in an active speech state
    if (this.state === 'SPEAKING' || this.state === 'THINKING' || this.state === 'BARGED_IN') {
      this.setState('LISTENING');
    }
  }

  // --------------------------------------------------------------------------
  // Private Helper: WebSocket Transport
  // --------------------------------------------------------------------------

  _connectWebSocket() {
    return new Promise((resolve, reject) => {
      const url = getBrowserVoiceWsUrl();
      this.sessionId = `browser_${Date.now()}`;

      try {
        this.ws = new WebSocket(url);

        const connectionTimeout = setTimeout(() => {
          if (this.ws && this.ws.readyState !== WebSocket.OPEN) {
            this.ws.close();
            reject(new Error('WebSocket connection timed out after 10s.'));
          }
        }, 10000);

        this.ws.onopen = () => {
          clearTimeout(connectionTimeout);
          this.reconnectAttempts = 0;

          // Send start message to initiate voice session
          this.ws.send(JSON.stringify({
            event: 'start',
            session_id: this.sessionId
          }));

          // Heartbeat ping every 15s
          this.pingInterval = setInterval(() => {
            if (this.ws && this.ws.readyState === WebSocket.OPEN) {
              this.ws.send(JSON.stringify({ event: 'ping' }));
            }
          }, 15000);

          resolve();
        };

        this.ws.onmessage = (event) => {
          this._handleWsMessage(event.data);
        };

        this.ws.onerror = (err) => {
          console.debug('Browser voice WS error:', err);
        };

        this.ws.onclose = () => {
          clearInterval(this.pingInterval);
          if (this.shouldReconnect) {
            this.setState('RECONNECTING');
            const delay = Math.min(1000 * Math.pow(1.5, this.reconnectAttempts), 8000);
            this.reconnectAttempts++;
            this.reconnectTimer = setTimeout(() => {
              this._connectWebSocket().catch((e) => {
                this.setState('ERROR');
                this.onError('Connection to voice agent lost. Retrying...');
              });
            }, delay);
          } else {
            this.setState('IDLE');
          }
        };

      } catch (err) {
        reject(err);
      }
    });
  }

  // --------------------------------------------------------------------------
  // Private Helper: Handle Inbound WebSocket Messages
  // --------------------------------------------------------------------------
  _handleWsMessage(dataStr) {
    let msg;
    try {
      msg = JSON.parse(dataStr);
    } catch (e) {
      return;
    }

    const { event } = msg;

    switch (event) {
      case 'session_state':
        if (msg.state) {
          this.setState(msg.state);
        }
        break;

      case 'media':
        // Incoming audio frame from assistant TTS
        if (msg.media && msg.media.payload) {
          // If we are currently in BARGED_IN, ignore in-flight audio from interrupted turn
          if (this.state === 'BARGED_IN') {
            return;
          }
          if (msg.turn_id) {
            if (this._currentPlayingTurnId && msg.turn_id !== this._currentPlayingTurnId) {
              // Reset playback queue when starting a new assistant turn
              this._stopAllPlayback();
              this._lastPlayedSeq = 0;
            }
            this._currentPlayingTurnId = msg.turn_id;
          }
          // Outbound sequence number deduplication: drop duplicate or out-of-order frame delivery
          if (msg.seq) {
            if (this._lastPlayedSeq && msg.seq <= this._lastPlayedSeq) {
              return;
            }
            this._lastPlayedSeq = msg.seq;
          }
          this._enqueueAudioPlayback(msg.media.payload, msg.mark);
          this.setState('SPEAKING');
        }
        break;

      case 'clear':
        // Interruption received from backend: stop playback instantly and discard stale queue
        this._stopAllPlayback();
        this._currentPlayingTurnId = null;
        this.setState('LISTENING');
        break;

      case 'conversation_cleared':
        this._stopAllPlayback();
        if (this.state === 'SPEAKING' || this.state === 'THINKING' || this.state === 'BARGED_IN') {
          this.setState('LISTENING');
        }
        break;


      case 'mark':
        // Playback mark arrived
        if (msg.name && this.ws && this.ws.readyState === WebSocket.OPEN) {
          this.ws.send(JSON.stringify({
            event: 'mark_ack',
            mark: msg.name
          }));
        }
        break;

      case 'transcript':
        this.onTranscript({
          role: msg.role,
          content: msg.content,
          turn_id: msg.turn_id,
          is_final: msg.is_final
        });
        if (msg.role === 'assistant' && msg.is_final) {
          this.setState('SPEAKING');
        } else if (msg.role === 'user' && msg.is_final) {
          this.setState('THINKING');
        }
        break;

      case 'error':
        this.onError(msg.message || 'Voice pipeline error.');
        break;

      default:
        break;
    }
  }

  // --------------------------------------------------------------------------
  // Private Helper: Microphone Audio Capture & Barge-In Detection
  // --------------------------------------------------------------------------
  _setupMicrophoneAudio(stream) {
    if (!this.audioContext) return;

    this.micSource = this.audioContext.createMediaStreamSource(stream);
    this.analyser = this.audioContext.createAnalyser();
    this.analyser.fftSize = 256;

    // Buffer size 2048 samples at native hardware rate (e.g. 48kHz = ~42.6ms)
    const bufferSize = 2048;
    this.scriptProcessor = this.audioContext.createScriptProcessor(bufferSize, 1, 1);
    this._micSamples8k = [];

    this.scriptProcessor.onaudioprocess = (audioProcessingEvent) => {
      // 1. Mute outputBuffer to completely prevent microphone audio from playing through speakers (NO self-monitoring/echo)
      const outputBuffer = audioProcessingEvent.outputBuffer;
      for (let ch = 0; ch < outputBuffer.numberOfChannels; ch++) {
        outputBuffer.getChannelData(ch).fill(0);
      }

      if (this.isMuted) return;

      const inputBuffer = audioProcessingEvent.inputBuffer;
      const inputData = inputBuffer.getChannelData(0);
      const inputRate = inputBuffer.sampleRate || this.audioContext.sampleRate || 48000;

      // 2. Compute RMS energy for visualizer & client-side barge-in
      let sum = 0;
      for (let i = 0; i < inputData.length; i++) {
        sum += inputData[i] * inputData[i];
      }
      const rms = Math.sqrt(sum / inputData.length);
      const level = Math.min(100, Math.round(rms * 400));
      this.onAudioLevel(level);

      // BROWSER-SIDE BARGE-IN:
      // If user voice energy crosses threshold while agent is speaking:
      if (this.isAgentSpeaking && level > 25) {
        console.info('⚡ Browser-Side Barge-In triggered by microphone energy');
        this.triggerBargeIn();
      }

      // Suppress microphone transmission while agent is speaking to prevent speaker bleed into STT
      if (this.isAgentSpeaking) {
        this._micSamples8k = [];
        return;
      }

      // 3. Downsample microphone input to 8000 Hz
      const downsampled = this._downsampleTo8kHz(inputData, inputRate);
      for (let i = 0; i < downsampled.length; i++) {
        this._micSamples8k.push(downsampled[i]);
      }

      // 4. Stream exact 160-sample (20ms) 8kHz Little-Endian PCM16 frames to backend
      const SAMPLES_PER_FRAME = 160;
      while (this._micSamples8k.length >= SAMPLES_PER_FRAME) {
        const frameSamples = this._micSamples8k.splice(0, SAMPLES_PER_FRAME);
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
          const buffer = new ArrayBuffer(SAMPLES_PER_FRAME * 2);
          const view = new DataView(buffer);
          for (let i = 0; i < SAMPLES_PER_FRAME; i++) {
            const s = Math.max(-1, Math.min(1, frameSamples[i]));
            const pcmVal = s < 0 ? s * 0x8000 : s * 0x7FFF;
            view.setInt16(i * 2, Math.round(pcmVal), true); // Explicitly Little-Endian
          }

          const bytes = new Uint8Array(buffer);
          let binary = '';
          const bLen = bytes.byteLength;
          for (let i = 0; i < bLen; i++) {
            binary += String.fromCharCode(bytes[i]);
          }
          const b64 = btoa(binary);

          this.ws.send(JSON.stringify({
            event: 'media',
            media: { payload: b64 },
            format: 'pcm16_8000'
          }));
        }
      }
    };

    // Connect audio processing graph:
    // micSource -> analyser -> scriptProcessor -> silentGain (gain=0) -> destination
    // silentGain keeps scriptProcessor alive without outputting mic sound to user's speakers
    this.silentGain = this.audioContext.createGain();
    this.silentGain.gain.setValueAtTime(0, this.audioContext.currentTime);

    this.micSource.connect(this.analyser);
    this.analyser.connect(this.scriptProcessor);
    this.scriptProcessor.connect(this.silentGain);
    this.silentGain.connect(this.audioContext.destination);
  }

  // Downsample input Float32 audio to 8000 Hz using area-averaging integration
  _downsampleTo8kHz(inputData, inputRate) {
    if (inputRate === 8000) return inputData;
    const ratio = inputRate / 8000;
    const outLen = Math.floor(inputData.length / ratio);
    const result = new Float32Array(outLen);

    for (let i = 0; i < outLen; i++) {
      const start = Math.floor(i * ratio);
      const end = Math.floor((i + 1) * ratio);
      let sum = 0;
      let count = 0;
      for (let j = start; j < end && j < inputData.length; j++) {
        sum += inputData[j];
        count++;
      }
      result[i] = count > 0 ? sum / count : inputData[start];
    }
    return result;
  }

  // --------------------------------------------------------------------------
  // Private Helper: Gapless Audio Playback Queue
  // --------------------------------------------------------------------------
  _enqueueAudioPlayback(base64Payload, mark) {
    if (!this.audioContext || this.audioContext.state === 'closed') return;

    try {
      const binaryString = atob(base64Payload);
      const len = binaryString.length;
      if (len < 2) return;

      const bytes = new Uint8Array(len);
      for (let i = 0; i < len; i++) {
        bytes[i] = binaryString.charCodeAt(i);
      }

      // Convert Little-Endian 16-bit signed linear PCM to Float32 [-1.0, 1.0]
      const numSamples = Math.floor(len / 2);
      const dataView = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
      const float32_8k = new Float32Array(numSamples);
      for (let i = 0; i < numSamples; i++) {
        float32_8k[i] = dataView.getInt16(i * 2, true) / 32768.0;
      }

      // Create AudioBuffer directly with native 8000 Hz sample rate.
      // The browser's Web Audio API automatically resamples this buffer to hardware rate
      // (e.g. 48kHz) using high-quality, band-limited sinc interpolation, avoiding naive
      // linear-interpolation buzz, boundary plateau distortion, and muffled speech.
      const audioBuffer = this.audioContext.createBuffer(1, numSamples, 8000);
      audioBuffer.getChannelData(0).set(float32_8k);

      const source = this.audioContext.createBufferSource();
      source.buffer = audioBuffer;
      source.connect(this.audioContext.destination);

      // Schedule gapless playback with 60ms initial lookahead jitter buffer
      const currentTime = this.audioContext.currentTime;
      const INITIAL_JITTER_BUFFER = 0.06;
      if (this.nextPlayTime < currentTime + 0.005) {
        this.nextPlayTime = currentTime + INITIAL_JITTER_BUFFER;
      } else if (this.nextPlayTime > currentTime + 0.3) {
        this.nextPlayTime = currentTime + INITIAL_JITTER_BUFFER;
      }

      source.start(this.nextPlayTime);
      this.nextPlayTime += audioBuffer.duration;

      this.activeSources.push(source);

      source.onended = () => {
        const idx = this.activeSources.indexOf(source);
        if (idx !== -1) {
          this.activeSources.splice(idx, 1);
        }
        if (this.activeSources.length === 0) {
          if (this.state === 'SPEAKING') {
            this.setState('LISTENING');
          }
        }
      };

    } catch (err) {
      console.error('Error decoding audio playback frame:', err);
    }
  }

  _stopAllPlayback() {
    for (const src of this.activeSources) {
      try {
        src.stop();
        src.disconnect();
      } catch (e) {}
    }
    this.activeSources = [];
    this.nextPlayTime = 0;
    this._lastPlayedSeq = 0;
    this.isAgentSpeaking = false;
  }

  // --------------------------------------------------------------------------
  // Private Helper: Web Speech API for Browser-Side STT Fallback
  // --------------------------------------------------------------------------
  _setupSpeechRecognition() {
    const SpeechRecognitionClass = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognitionClass) return;

    try {
      this.speechRecognition = new SpeechRecognitionClass();
      this.speechRecognition.continuous = true;
      this.speechRecognition.interimResults = true;
      this.speechRecognition.lang = 'en-US';

      this.speechRecognition.onresult = (event) => {
        for (let i = event.resultIndex; i < event.results.length; i++) {
          const result = event.results[i];
          const transcript = result[0].transcript.trim();
          const isFinal = result.isFinal;

          if (transcript) {
            // Forward to backend
            if (this.ws && this.ws.readyState === WebSocket.OPEN) {
              this.ws.send(JSON.stringify({
                event: 'transcript',
                text: transcript,
                is_final: isFinal
              }));
            }

            // Immediately reflect in UI
            this.onTranscript({
              role: 'user',
              content: transcript,
              is_final: isFinal
            });

            if (isFinal) {
              this.setState('THINKING');
            }
          }
        }
      };

      this.speechRecognition.onerror = (e) => {
        // Ignored benign warnings (no-speech, aborted on stop)
        if (e.error !== 'no-speech' && e.error !== 'aborted') {
          console.debug('Speech recognition event:', e.error);
        }
      };

      this.speechRecognition.onend = () => {
        // Auto-restart if voice conversation is still active
        if (this.state !== 'IDLE' && this.state !== 'ERROR' && this.speechRecognition) {
          try {
            this.speechRecognition.start();
          } catch (e) {}
        }
      };

      this.speechRecognition.start();

    } catch (e) {
      console.debug('Speech recognition not available or active:', e);
    }
  }
}
