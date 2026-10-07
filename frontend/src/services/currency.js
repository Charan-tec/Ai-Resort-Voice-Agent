// International Country & Currency Service for Azure Paradise Resort
// Supports automatic client-side country detection, live exchange-rate fetching & caching,
// manual user override persistence, and ISO-4217 Intl formatting.

export const COUNTRIES = [
  { code: 'IN', name: 'India', currency: 'INR', flag: '🇮🇳' },
  { code: 'US', name: 'United States', currency: 'USD', flag: '🇺🇸' },
  { code: 'GB', name: 'United Kingdom', currency: 'GBP', flag: '🇬🇧' },
  { code: 'EU', name: 'Europe', currency: 'EUR', flag: '🇪🇺' },
  { code: 'AE', name: 'UAE', currency: 'AED', flag: '🇦🇪' },
  { code: 'SG', name: 'Singapore', currency: 'SGD', flag: '🇸🇬' },
  { code: 'AU', name: 'Australia', currency: 'AUD', flag: '🇦🇺' },
  { code: 'CA', name: 'Canada', currency: 'CAD', flag: '🇨🇦' },
  { code: 'JP', name: 'Japan', currency: 'JPY', flag: '🇯🇵' },
  { code: 'CH', name: 'Switzerland', currency: 'CHF', flag: '🇨🇭' },
  { code: 'NZ', name: 'New Zealand', currency: 'NZD', flag: '🇳🇿' },
  { code: 'SA', name: 'Saudi Arabia', currency: 'SAR', flag: '🇸🇦' },
  { code: 'KR', name: 'South Korea', currency: 'KRW', flag: '🇰🇷' },
  { code: 'TH', name: 'Thailand', currency: 'THB', flag: '🇹🇭' },
  { code: 'CN', name: 'China', currency: 'CNY', flag: '🇨🇳' },
  { code: 'BR', name: 'Brazil', currency: 'BRL', flag: '🇧🇷' },
  { code: 'MX', name: 'Mexico', currency: 'MXN', flag: '🇲🇽' },
  { code: 'ZA', name: 'South Africa', currency: 'ZAR', flag: '🇿🇦' },
  { code: 'SE', name: 'Sweden', currency: 'SEK', flag: '🇸🇪' },
  { code: 'NO', name: 'Norway', currency: 'NOK', flag: '🇳🇴' },
  { code: 'TR', name: 'Turkey', currency: 'TRY', flag: '🇹🇷' },
  { code: 'ID', name: 'Indonesia', currency: 'IDR', flag: '🇮🇩' },
  { code: 'HK', name: 'Hong Kong', currency: 'HKD', flag: '🇭🇰' },
  { code: 'TW', name: 'Taiwan', currency: 'TWD', flag: '🇹🇼' },
  { code: 'MY', name: 'Malaysia', currency: 'MYR', flag: '🇲🇾' },
  { code: 'PH', name: 'Philippines', currency: 'PHP', flag: '🇵🇭' },
  { code: 'IL', name: 'Israel', currency: 'ILS', flag: '🇮🇱' },
  { code: 'QA', name: 'Qatar', currency: 'QAR', flag: '🇶🇦' },
  { code: 'KW', name: 'Kuwait', currency: 'KWD', flag: '🇰🇼' },
  { code: 'MV', name: 'Maldives', currency: 'MVR', flag: '🇲🇻' }
];

export const CURRENCIES = {
  USD: { code: 'USD', name: 'US Dollar', symbol: '$', rate: 1.0, decimals: 2, flag: '🇺🇸' },
  INR: { code: 'INR', name: 'Indian Rupee', symbol: '₹', rate: 83.50, decimals: 2, flag: '🇮🇳' },
  GBP: { code: 'GBP', name: 'British Pound', symbol: '£', rate: 0.79, decimals: 2, flag: '🇬🇧' },
  EUR: { code: 'EUR', name: 'Euro', symbol: '€', rate: 0.92, decimals: 2, flag: '🇪🇺' },
  AED: { code: 'AED', name: 'UAE Dirham', symbol: 'AED', rate: 3.67, decimals: 2, flag: '🇦🇪' },
  SGD: { code: 'SGD', name: 'Singapore Dollar', symbol: 'SGD', rate: 1.35, decimals: 2, flag: '🇸🇬' },
  AUD: { code: 'AUD', name: 'Australian Dollar', symbol: 'AUD', rate: 1.52, decimals: 2, flag: '🇦🇺' },
  CAD: { code: 'CAD', name: 'Canadian Dollar', symbol: 'CAD', rate: 1.36, decimals: 2, flag: '🇨🇦' },
  JPY: { code: 'JPY', name: 'Japanese Yen', symbol: '¥', rate: 155.20, decimals: 0, flag: '🇯🇵' },
  CHF: { code: 'CHF', name: 'Swiss Franc', symbol: 'CHF', rate: 0.90, decimals: 2, flag: '🇨🇭' },
  NZD: { code: 'NZD', name: 'New Zealand Dollar', symbol: 'NZ$', rate: 1.64, decimals: 2, flag: '🇳🇿' },
  SAR: { code: 'SAR', name: 'Saudi Riyal', symbol: 'SAR', rate: 3.75, decimals: 2, flag: '🇸🇦' },
  KRW: { code: 'KRW', name: 'South Korean Won', symbol: '₩', rate: 1380.0, decimals: 0, flag: '🇰🇷' },
  THB: { code: 'THB', name: 'Thai Baht', symbol: '฿', rate: 36.80, decimals: 2, flag: '🇹🇭' },
  CNY: { code: 'CNY', name: 'Chinese Yuan', symbol: '¥', rate: 7.25, decimals: 2, flag: '🇨🇳' },
  BRL: { code: 'BRL', name: 'Brazilian Real', symbol: 'R$', rate: 5.45, decimals: 2, flag: '🇧🇷' },
  MXN: { code: 'MXN', name: 'Mexican Peso', symbol: 'Mex$', rate: 18.20, decimals: 2, flag: '🇲🇽' },
  ZAR: { code: 'ZAR', name: 'South African Rand', symbol: 'R', rate: 18.40, decimals: 2, flag: '🇿🇦' },
  SEK: { code: 'SEK', name: 'Swedish Krona', symbol: 'kr', rate: 10.60, decimals: 2, flag: '🇸🇪' },
  NOK: { code: 'NOK', name: 'Norwegian Krone', symbol: 'kr', rate: 10.75, decimals: 2, flag: '🇳🇴' },
  TRY: { code: 'TRY', name: 'Turkish Lira', symbol: '₺', rate: 32.80, decimals: 2, flag: '🇹🇷' },
  IDR: { code: 'IDR', name: 'Indonesian Rupiah', symbol: 'Rp', rate: 16250.0, decimals: 0, flag: '🇮🇩' },
  HKD: { code: 'HKD', name: 'Hong Kong Dollar', symbol: 'HK$', rate: 7.81, decimals: 2, flag: '🇭🇰' },
  TWD: { code: 'TWD', name: 'New Taiwan Dollar', symbol: 'NT$', rate: 32.40, decimals: 2, flag: '🇹🇼' },
  MYR: { code: 'MYR', name: 'Malaysian Ringgit', symbol: 'RM', rate: 4.71, decimals: 2, flag: '🇲🇾' },
  PHP: { code: 'PHP', name: 'Philippine Peso', symbol: '₱', rate: 58.60, decimals: 2, flag: '🇵🇭' },
  ILS: { code: 'ILS', name: 'Israeli Shekel', symbol: '₪', rate: 3.72, decimals: 2, flag: '🇮🇱' },
  QAR: { code: 'QAR', name: 'Qatari Riyal', symbol: 'QR', rate: 3.64, decimals: 2, flag: '🇶🇦' },
  KWD: { code: 'KWD', name: 'Kuwaiti Dinar', symbol: 'KD', rate: 0.31, decimals: 3, flag: '🇰🇼' },
  MVR: { code: 'MVR', name: 'Maldivian Rufiyaa', symbol: 'Rf', rate: 15.4, decimals: 2, flag: '🇲🇻' }
};

// In-memory active exchange rates (initialized with defaults, updated via live API)
let dynamicRates = { ...CURRENCIES };
let ratesLoaded = false;
let ratesLoadError = false;
const listeners = new Set();

const CACHE_KEY = 'azure_resort_fx_cache_v2';
const CACHE_DURATION_MS = 30 * 60 * 1000; // 30 minutes cache

/**
 * Returns formatted currency label like 'INR ₹', 'USD $', 'GBP £', 'EUR €', 'AED', 'SGD', 'AUD', 'CAD', 'JPY ¥'
 */
export function getCurrencyDisplayLabel(code) {
  const c = (code || 'USD').toUpperCase();
  switch (c) {
    case 'INR': return 'INR ₹';
    case 'USD': return 'USD $';
    case 'GBP': return 'GBP £';
    case 'EUR': return 'EUR €';
    case 'JPY': return 'JPY ¥';
    case 'AED': return 'AED';
    case 'SGD': return 'SGD';
    case 'AUD': return 'AUD';
    case 'CAD': return 'CAD';
    default: {
      const info = CURRENCIES[c];
      return info ? `${c} ${info.symbol !== c ? info.symbol : ''}`.trim() : c;
    }
  }
}

/**
 * Initializes and fetches live exchange rates from reliable sources with caching.
 */
export async function initExchangeRates() {
  // 1. Try reading from localStorage cache
  try {
    const cached = localStorage.getItem(CACHE_KEY);
    if (cached) {
      const parsed = JSON.parse(cached);
      if (parsed && parsed.timestamp && (Date.now() - parsed.timestamp < CACHE_DURATION_MS) && parsed.rates) {
        applyLiveRates(parsed.rates);
        ratesLoaded = true;
        ratesLoadError = false;
        notifyListeners();
        return;
      }
    }
  } catch (e) {
    // ignore cache read error
  }

  // 2. Fetch from reliable live exchange rate API
  try {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 4000);
    const res = await fetch('https://open.er-api.com/v6/latest/USD', { signal: controller.signal });
    clearTimeout(timeout);

    if (res.ok) {
      const data = await res.json();
      if (data && data.result === 'success' && data.rates) {
        applyLiveRates(data.rates);
        ratesLoaded = true;
        ratesLoadError = false;
        try {
          localStorage.setItem(CACHE_KEY, JSON.stringify({ timestamp: Date.now(), rates: data.rates }));
        } catch (_) {}
        notifyListeners();
        return;
      }
    }
  } catch (err) {
    console.debug('Primary FX fetch error:', err.message);
  }

  // 3. Fallback to backend /api/pricing/currencies endpoint
  try {
    const baseUrl = typeof window !== 'undefined' && (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1')
      ? 'http://localhost:8000'
      : (typeof window !== 'undefined' && window.location.origin.includes('onrender.com') ? window.location.origin : 'https://ai-resort-voice-agent.onrender.com');
    const res = await fetch(`${baseUrl}/api/pricing/currencies`, { cache: 'no-store' });
    if (res.ok) {
      const data = await res.json();
      if (data && data.currencies) {
        const ratesMap = {};
        for (const [code, info] of Object.entries(data.currencies)) {
          ratesMap[code] = info.rate;
        }
        applyLiveRates(ratesMap);
        ratesLoaded = true;
        ratesLoadError = false;
        notifyListeners();
        return;
      }
    }
  } catch (err) {
    console.debug('Backend FX fetch error:', err.message);
  }

  // 4. If all live fetches fail and no cache exists, mark as unavailable
  if (!ratesLoaded) {
    ratesLoadError = true;
    notifyListeners();
  }
}

function applyLiveRates(ratesObj) {
  for (const [code, info] of Object.entries(CURRENCIES)) {
    if (ratesObj[code] && typeof ratesObj[code] === 'number' && ratesObj[code] > 0) {
      dynamicRates[code] = {
        ...info,
        rate: ratesObj[code]
      };
    }
  }
}

function notifyListeners() {
  listeners.forEach((fn) => {
    try {
      fn({ ratesLoaded, ratesLoadError, rates: dynamicRates });
    } catch (_) {}
  });
}

export function subscribeToExchangeRates(fn) {
  listeners.add(fn);
  return () => listeners.delete(fn);
}

export function isExchangeRateAvailable() {
  return !ratesLoadError;
}

/**
 * Automatically detects the user's country and default currency using client-side signals.
 * Prioritizes user manual override from localStorage if set.
 */
export function detectUserCountryAndCurrency() {
  // 1. Check if user has explicitly saved an override
  try {
    const isOverride = localStorage.getItem('azure_currency_manual_override') === 'true';
    const savedCountry = localStorage.getItem('azure_selected_country');
    const savedCurrency = localStorage.getItem('azure_selected_currency');
    if (isOverride && savedCountry && savedCurrency) {
      return {
        country: savedCountry,
        currency: savedCurrency,
        isManual: true
      };
    }
  } catch (_) {}

  // 2. Client-side Timezone Detection
  try {
    const timeZone = Intl.DateTimeFormat().resolvedOptions().timeZone || '';
    const tzLower = timeZone.toLowerCase();

    if (tzLower.includes('kolkata') || tzLower.includes('calcutta') || tzLower.includes('india')) {
      return { country: 'IN', currency: 'INR', isManual: false };
    }
    if (tzLower.includes('london') || tzLower.includes('gmt') || tzLower.includes('bst')) {
      return { country: 'GB', currency: 'GBP', isManual: false };
    }
    if (tzLower.includes('dubai') || tzLower.includes('uae')) {
      return { country: 'AE', currency: 'AED', isManual: false };
    }
    if (tzLower.includes('singapore')) {
      return { country: 'SG', currency: 'SGD', isManual: false };
    }
    if (tzLower.includes('sydney') || tzLower.includes('melbourne') || tzLower.includes('brisbane') || tzLower.includes('perth') || tzLower.includes('australia')) {
      return { country: 'AU', currency: 'AUD', isManual: false };
    }
    if (tzLower.includes('toronto') || tzLower.includes('vancouver') || tzLower.includes('montreal') || tzLower.includes('edmonton')) {
      return { country: 'CA', currency: 'CAD', isManual: false };
    }
    if (tzLower.includes('tokyo') || tzLower.includes('japan')) {
      return { country: 'JP', currency: 'JPY', isManual: false };
    }
    if (tzLower.includes('paris') || tzLower.includes('berlin') || tzLower.includes('rome') || tzLower.includes('madrid') || tzLower.includes('amsterdam') || tzLower.includes('brussels') || tzLower.includes('vienna') || tzLower.includes('dublin') || tzLower.includes('helsinki') || tzLower.includes('athens') || tzLower.includes('lisbon') || tzLower.includes('europe')) {
      return { country: 'EU', currency: 'EUR', isManual: false };
    }
    if (tzLower.includes('zurich')) {
      return { country: 'CH', currency: 'CHF', isManual: false };
    }
    if (tzLower.includes('auckland')) {
      return { country: 'NZ', currency: 'NZD', isManual: false };
    }
    if (tzLower.includes('seoul')) {
      return { country: 'KR', currency: 'KRW', isManual: false };
    }
    if (tzLower.includes('bangkok')) {
      return { country: 'TH', currency: 'THB', isManual: false };
    }
    if (tzLower.includes('shanghai') || tzLower.includes('beijing')) {
      return { country: 'CN', currency: 'CNY', isManual: false };
    }
    if (tzLower.includes('sao_paulo')) {
      return { country: 'BR', currency: 'BRL', isManual: false };
    }
    if (tzLower.includes('mexico')) {
      return { country: 'MX', currency: 'MXN', isManual: false };
    }
    if (tzLower.includes('johannesburg')) {
      return { country: 'ZA', currency: 'ZAR', isManual: false };
    }
  } catch (_) {}

  // 3. Client-side Language / Locale Detection
  try {
    const lang = (navigator.language || (navigator.languages && navigator.languages[0]) || '').toLowerCase();
    if (lang.includes('-in') || lang === 'hi' || lang === 'ta' || lang === 'te' || lang === 'mr' || lang === 'bn') {
      return { country: 'IN', currency: 'INR', isManual: false };
    }
    if (lang.includes('-gb')) {
      return { country: 'GB', currency: 'GBP', isManual: false };
    }
    if (lang.includes('-jp') || lang === 'ja') {
      return { country: 'JP', currency: 'JPY', isManual: false };
    }
    if (lang.includes('-au')) {
      return { country: 'AU', currency: 'AUD', isManual: false };
    }
    if (lang.includes('-ca')) {
      return { country: 'CA', currency: 'CAD', isManual: false };
    }
    if (lang.includes('-ae') || lang.startsWith('ar')) {
      return { country: 'AE', currency: 'AED', isManual: false };
    }
    if (lang.includes('-sg')) {
      return { country: 'SG', currency: 'SGD', isManual: false };
    }
    if (lang.includes('-de') || lang.includes('-fr') || lang.includes('-it') || lang.includes('-es')) {
      return { country: 'EU', currency: 'EUR', isManual: false };
    }
  } catch (_) {}

  // 4. Default fallback to US / USD
  return { country: 'US', currency: 'USD', isManual: false };
}

/**
 * Persists the user's manual country and currency selection to prevent overriding.
 */
export function saveUserCurrencyPreference(countryCode, currencyCode) {
  try {
    localStorage.setItem('azure_currency_manual_override', 'true');
    localStorage.setItem('azure_selected_country', countryCode);
    localStorage.setItem('azure_selected_currency', currencyCode);
  } catch (_) {}
}

/**
 * Returns country info object by country code.
 */
export function getCountryByCode(code) {
  if (!code) return COUNTRIES[0];
  const upper = code.toUpperCase();
  return COUNTRIES.find((c) => c.code === upper) || COUNTRIES.find((c) => c.code === 'US') || COUNTRIES[0];
}

/**
 * Returns currency info object by code.
 */
export function getCurrencyInfo(code) {
  const upper = (code || 'USD').toUpperCase();
  return dynamicRates[upper] || CURRENCIES[upper] || CURRENCIES.USD;
}

/**
 * Formats a number with proper international grouping.
 */
function formatNumberInternational(amount, decimals, currency = 'USD') {
  const locale = currency === 'INR' ? 'en-IN' : 'en-US';
  try {
    return new Intl.NumberFormat(locale, {
      minimumFractionDigits: decimals,
      maximumFractionDigits: decimals
    }).format(amount);
  } catch (_) {
    return amount.toLocaleString(undefined, {
      minimumFractionDigits: decimals,
      maximumFractionDigits: decimals
    });
  }
}

/**
 * Primary conversion & formatting function for resort prices.
 * The resort's canonical/base pricing remains USD.
 *
 * Example Output:
 * If selectedCurrency is 'INR':
 *   primary: '₹54,275 / night'
 *   secondary: '≈ USD 650'
 *   isConverted: true
 * If selectedCurrency is 'USD':
 *   primary: '$650 / night'
 *   secondary: null
 *   isConverted: false
 * If FX service failed:
 *   primary: '$650 / night'
 *   secondary: 'Local currency conversion temporarily unavailable.'
 *   isConversionUnavailable: true
 */
export function formatPriceDisplay(amountUsd, targetCurrency = 'USD', options = {}) {
  const numUsd = Number(amountUsd) || 0;
  const target = (targetCurrency || 'USD').toUpperCase().trim();
  const perNightSuffix = options.perNight ? ' / night' : '';

  // Base USD formatted string
  const formattedUsdNumber = formatNumberInternational(numUsd, numUsd % 1 === 0 ? 0 : 2, 'USD');
  const baseUsdDisplay = `$${formattedUsdNumber}${perNightSuffix}`;

  // If user selected USD, display cleanly without secondary text
  if (target === 'USD') {
    return {
      primary: baseUsdDisplay,
      secondary: null,
      symbolFormatted: `$${formattedUsdNumber}`,
      numericAmount: numUsd,
      currency: 'USD',
      symbol: '$',
      rate: 1.0,
      isConverted: false,
      isConversionUnavailable: false,
      baseUsd: numUsd
    };
  }

  // If live conversion service failed and not USD, fall back to USD with required error notice
  if (ratesLoadError) {
    return {
      primary: baseUsdDisplay,
      secondary: 'Local currency conversion temporarily unavailable.',
      symbolFormatted: `$${formattedUsdNumber}`,
      numericAmount: numUsd,
      currency: 'USD',
      symbol: '$',
      rate: 1.0,
      isConverted: false,
      isConversionUnavailable: true,
      baseUsd: numUsd
    };
  }

  // Valid target currency
  const currInfo = getCurrencyInfo(target);
  const rate = currInfo.rate || 1.0;
  const convertedNumeric = numUsd * rate;
  const decimals = currInfo.decimals !== undefined ? currInfo.decimals : 2;

  // Intl formatting
  const effectiveDecimals = decimals === 0 ? 0 : (convertedNumeric % 1 === 0 ? 0 : decimals);
  const formattedConvertedNumber = formatNumberInternational(convertedNumeric, effectiveDecimals, target);

  // Currency prefix symbol
  const symbolPrefix = ['AED', 'SGD', 'AUD', 'CAD'].includes(target)
    ? `${target} `
    : currInfo.symbol;

  return {
    primary: `${symbolPrefix}${formattedConvertedNumber}${perNightSuffix}`,
    secondary: `≈ USD ${formattedUsdNumber}`,
    symbolFormatted: `${symbolPrefix}${formattedConvertedNumber}`,
    numericAmount: convertedNumeric,
    currency: target,
    symbol: currInfo.symbol,
    rate,
    isConverted: true,
    isConversionUnavailable: false,
    baseUsd: numUsd
  };
}

/**
 * Replaces USD price amounts in text strings (like AI chat responses)
 * with the selected converted currency while preserving the canonical USD equivalent.
 *
 * Example:
 * Input: "Garden Tropical Bungalow is $290 per night."
 * Output (for INR): "Garden Tropical Bungalow is ₹24,215 per night (approximately USD 290)."
 */
export function convertTextCurrencies(text, targetCurrency = 'USD') {
  if (!text || typeof text !== 'string') return text;
  const target = (targetCurrency || 'USD').toUpperCase().trim();
  if (target === 'USD') return text;

  if (ratesLoadError) {
    return text.includes('Local currency conversion temporarily unavailable.')
      ? text
      : `${text} (Local currency conversion temporarily unavailable.)`;
  }

  const currInfo = getCurrencyInfo(target);
  const rate = currInfo.rate || 1.0;

  // Pattern matches: $650, $650.00, $290 / night, $290/night, $290 per night
  const priceRegex = /\$([0-9]{1,3}(?:,[0-9]{3})*(?:\.[0-9]{2})?|[0-9]+(?:\.[0-9]{2})?)(\s*(?:\/|per)?\s*(?:night)?)?/gi;

  return text.replace(priceRegex, (match, amountStr, perNightSuffix) => {
    const cleanNum = parseFloat(amountStr.replace(/,/g, ''));
    if (isNaN(cleanNum)) return match;
    const converted = cleanNum * rate;
    const decimals = currInfo.decimals !== undefined ? currInfo.decimals : 2;
    const effectiveDecimals = decimals === 0 ? 0 : (converted % 1 === 0 ? 0 : decimals);
    const formattedConverted = formatNumberInternational(converted, effectiveDecimals, target);
    const symbolPrefix = ['AED', 'SGD', 'AUD', 'CAD'].includes(target)
      ? `${target} `
      : currInfo.symbol;
    const suffix = perNightSuffix ? perNightSuffix : '';
    const approxUsd = cleanNum % 1 === 0 ? cleanNum : cleanNum.toFixed(2);
    return `${symbolPrefix}${formattedConverted}${suffix} (approximately USD ${approxUsd})`;
  });
}

/**
 * Legacy convertUsd function for backwards compatibility with existing components.
 */
export function convertUsd(amountUsd, currencyCode = 'USD') {
  const display = formatPriceDisplay(amountUsd, currencyCode);
  return {
    baseUsd: display.baseUsd,
    currencyCode: display.currency,
    currencyName: getCurrencyInfo(display.currency).name,
    symbol: display.symbol,
    rate: display.rate,
    amount: display.numericAmount,
    formatted: display.primary,
    formattedWithCode: display.primary,
    secondary: display.secondary,
    isConversionUnavailable: display.isConversionUnavailable,
    rateDisplay: `1 USD = ${display.rate.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 4 })} ${display.currency}`
  };
}

/**
 * Calculates a complete booking price breakdown preserving canonical USD values
 * and providing converted values for all itemized rows.
 */
export function calculateBookingBreakdown({
  nightlyRateUsd = 650,
  nights = 3,
  resortFeePerNightUsd = 45,
  taxRate = 0.12,
  addonsUsd = 0
}, targetCurrency = 'USD') {
  const effectiveNights = Math.max(1, Number(nights) || 1);
  const subtotalUsd = nightlyRateUsd * effectiveNights;
  const resortFeesUsd = resortFeePerNightUsd * effectiveNights;
  const taxesUsd = (subtotalUsd + resortFeesUsd) * taxRate;
  const totalUsd = subtotalUsd + resortFeesUsd + taxesUsd + (Number(addonsUsd) || 0);

  return {
    nights: effectiveNights,
    baseUsd: {
      nightly: nightlyRateUsd,
      subtotal: subtotalUsd,
      resortFees: resortFeesUsd,
      taxes: taxesUsd,
      addons: addonsUsd,
      total: totalUsd
    },
    display: {
      nightly: formatPriceDisplay(nightlyRateUsd, targetCurrency, { perNight: true }),
      subtotal: formatPriceDisplay(subtotalUsd, targetCurrency),
      resortFees: formatPriceDisplay(resortFeesUsd, targetCurrency),
      taxes: formatPriceDisplay(taxesUsd, targetCurrency),
      addons: formatPriceDisplay(addonsUsd, targetCurrency),
      total: formatPriceDisplay(totalUsd, targetCurrency)
    }
  };
}
