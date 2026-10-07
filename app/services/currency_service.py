"""
International Currency & Country Service for Azure Paradise Resort.
Maintains base prices in USD and dynamically converts displayed rates to international currencies.
"""
from typing import Dict, List, Optional
from pydantic import BaseModel


class CurrencyInfo(BaseModel):
    code: str
    name: str
    symbol: str
    rate: float  # Units per 1 USD
    decimals: int = 2
    flag: str = ""


class CountryInfo(BaseModel):
    code: str
    name: str
    currency: str
    flag: str


# Authoritative Exchange Rates relative to 1.00 USD base
EXCHANGE_RATES: Dict[str, dict] = {
    "USD": {"name": "US Dollar", "symbol": "$", "rate": 1.0, "decimals": 2, "flag": "🇺🇸"},
    "EUR": {"name": "Euro", "symbol": "€", "rate": 0.92, "decimals": 2, "flag": "🇪🇺"},
    "GBP": {"name": "British Pound", "symbol": "£", "rate": 0.79, "decimals": 2, "flag": "🇬🇧"},
    "JPY": {"name": "Japanese Yen", "symbol": "¥", "rate": 155.20, "decimals": 0, "flag": "🇯🇵"},
    "CAD": {"name": "Canadian Dollar", "symbol": "CA$", "rate": 1.36, "decimals": 2, "flag": "🇨🇦"},
    "AUD": {"name": "Australian Dollar", "symbol": "A$", "rate": 1.52, "decimals": 2, "flag": "🇦🇺"},
    "CHF": {"name": "Swiss Franc", "symbol": "CHF", "rate": 0.90, "decimals": 2, "flag": "🇨🇭"},
    "CNY": {"name": "Chinese Yuan", "symbol": "¥", "rate": 7.25, "decimals": 2, "flag": "🇨🇳"},
    "INR": {"name": "Indian Rupee", "symbol": "₹", "rate": 83.50, "decimals": 2, "flag": "🇮🇳"},
    "AED": {"name": "UAE Dirham", "symbol": "AED", "rate": 3.67, "decimals": 2, "flag": "🇦🇪"},
    "SGD": {"name": "Singapore Dollar", "symbol": "S$", "rate": 1.35, "decimals": 2, "flag": "🇸🇬"},
    "SAR": {"name": "Saudi Riyal", "symbol": "SAR", "rate": 3.75, "decimals": 2, "flag": "🇸🇦"},
    "KRW": {"name": "South Korean Won", "symbol": "₩", "rate": 1380.0, "decimals": 0, "flag": "🇰🇷"},
    "NZD": {"name": "New Zealand Dollar", "symbol": "NZ$", "rate": 1.64, "decimals": 2, "flag": "🇳🇿"},
    "BRL": {"name": "Brazilian Real", "symbol": "R$", "rate": 5.45, "decimals": 2, "flag": "🇧🇷"},
    "MXN": {"name": "Mexican Peso", "symbol": "Mex$", "rate": 18.20, "decimals": 2, "flag": "🇲🇽"},
    "ZAR": {"name": "South African Rand", "symbol": "R", "rate": 18.40, "decimals": 2, "flag": "🇿🇦"},
    "THB": {"name": "Thai Baht", "symbol": "฿", "rate": 36.80, "decimals": 2, "flag": "🇹🇭"},
    "SEK": {"name": "Swedish Krona", "symbol": "kr", "rate": 10.60, "decimals": 2, "flag": "🇸🇪"},
    "NOK": {"name": "Norwegian Krone", "symbol": "kr", "rate": 10.75, "decimals": 2, "flag": "🇳🇴"},
    "TRY": {"name": "Turkish Lira", "symbol": "₺", "rate": 32.80, "decimals": 2, "flag": "🇹🇷"},
    "IDR": {"name": "Indonesian Rupiah", "symbol": "Rp", "rate": 16250.0, "decimals": 0, "flag": "🇮🇩"},
    "HKD": {"name": "Hong Kong Dollar", "symbol": "HK$", "rate": 7.81, "decimals": 2, "flag": "🇭🇰"},
    "TWD": {"name": "New Taiwan Dollar", "symbol": "NT$", "rate": 32.40, "decimals": 2, "flag": "🇹🇼"},
    "PLN": {"name": "Polish Zloty", "symbol": "zł", "rate": 3.98, "decimals": 2, "flag": "🇵🇱"},
    "DKK": {"name": "Danish Krone", "symbol": "kr", "rate": 6.88, "decimals": 2, "flag": "🇩🇰"},
    "MYR": {"name": "Malaysian Ringgit", "symbol": "RM", "rate": 4.71, "decimals": 2, "flag": "🇲🇾"},
    "PHP": {"name": "Philippine Peso", "symbol": "₱", "rate": 58.60, "decimals": 2, "flag": "🇵🇭"},
    "CZK": {"name": "Czech Koruna", "symbol": "Kč", "rate": 23.20, "decimals": 2, "flag": "🇨🇿"},
    "ILS": {"name": "Israeli Shekel", "symbol": "₪", "rate": 3.72, "decimals": 2, "flag": "🇮🇱"},
    "CLP": {"name": "Chilean Peso", "symbol": "CLP$", "rate": 930.0, "decimals": 0, "flag": "🇨🇱"},
    "COP": {"name": "Colombian Peso", "symbol": "COL$", "rate": 4120.0, "decimals": 0, "flag": "🇨🇴"},
    "EGP": {"name": "Egyptian Pound", "symbol": "E£", "rate": 48.30, "decimals": 2, "flag": "🇪🇬"},
    "VND": {"name": "Vietnamese Dong", "symbol": "₫", "rate": 25450.0, "decimals": 0, "flag": "🇻🇳"},
    "QAR": {"name": "Qatari Riyal", "symbol": "QR", "rate": 3.64, "decimals": 2, "flag": "🇶🇦"},
    "KWD": {"name": "Kuwaiti Dinar", "symbol": "KD", "rate": 0.31, "decimals": 3, "flag": "🇰🇼"},
    "BHD": {"name": "Bahraini Dinar", "symbol": "BD", "rate": 0.38, "decimals": 3, "flag": "🇧🇭"},
    "OMR": {"name": "Omani Rial", "symbol": "OMR", "rate": 0.385, "decimals": 3, "flag": "🇴🇲"},
    "ARS": {"name": "Argentine Peso", "symbol": "$", "rate": 920.0, "decimals": 2, "flag": "🇦🇷"},
    "PKR": {"name": "Pakistani Rupee", "symbol": "Rs", "rate": 278.5, "decimals": 2, "flag": "🇵🇰"},
    "BDT": {"name": "Bangladeshi Taka", "symbol": "৳", "rate": 117.5, "decimals": 2, "flag": "🇧🇩"},
    "NGN": {"name": "Nigerian Naira", "symbol": "₦", "rate": 1510.0, "decimals": 2, "flag": "🇳🇬"},
    "KES": {"name": "Kenyan Shilling", "symbol": "KSh", "rate": 130.0, "decimals": 2, "flag": "🇰🇪"},
    "GHS": {"name": "Ghanaian Cedi", "symbol": "GH₵", "rate": 15.2, "decimals": 2, "flag": "🇬🇭"},
    "MAD": {"name": "Moroccan Dirham", "symbol": "MAD", "rate": 9.95, "decimals": 2, "flag": "🇲🇦"},
    "HUF": {"name": "Hungarian Forint", "symbol": "Ft", "rate": 365.0, "decimals": 0, "flag": "🇭🇺"},
    "RON": {"name": "Romanian Leu", "symbol": "lei", "rate": 4.58, "decimals": 2, "flag": "🇷🇴"},
    "BGN": {"name": "Bulgarian Lev", "symbol": "лв", "rate": 1.80, "decimals": 2, "flag": "🇧🇬"},
    "ISK": {"name": "Icelandic Krona", "symbol": "kr", "rate": 139.0, "decimals": 0, "flag": "🇮🇸"},
    "RSD": {"name": "Serbian Dinar", "symbol": "дин.", "rate": 108.0, "decimals": 2, "flag": "🇷🇸"},
    "UAH": {"name": "Ukrainian Hryvnia", "symbol": "₴", "rate": 40.8, "decimals": 2, "flag": "🇺🇦"},
    "KZT": {"name": "Kazakhstani Tenge", "symbol": "₸", "rate": 465.0, "decimals": 2, "flag": "🇰🇿"},
    "PEN": {"name": "Peruvian Sol", "symbol": "S/", "rate": 3.78, "decimals": 2, "flag": "🇵🇪"},
    "UYU": {"name": "Uruguayan Peso", "symbol": "$U", "rate": 39.5, "decimals": 2, "flag": "🇺🇾"},
    "CRC": {"name": "Costa Rican Colon", "symbol": "₡", "rate": 525.0, "decimals": 0, "flag": "🇨🇷"},
    "DOP": {"name": "Dominican Peso", "symbol": "RD$", "rate": 59.2, "decimals": 2, "flag": "🇩🇴"},
    "JMD": {"name": "Jamaican Dollar", "symbol": "J$", "rate": 156.0, "decimals": 2, "flag": "🇯🇲"},
    "LKR": {"name": "Sri Lankan Rupee", "symbol": "Rs", "rate": 302.0, "decimals": 2, "flag": "🇱🇰"},
    "NPR": {"name": "Nepalese Rupee", "symbol": "Rs", "rate": 133.5, "decimals": 2, "flag": "🇳🇵"},
    "MVR": {"name": "Maldivian Rufiyaa", "symbol": "Rf", "rate": 15.4, "decimals": 2, "flag": "🇲🇻"},
    "FJD": {"name": "Fijian Dollar", "symbol": "FJ$", "rate": 2.26, "decimals": 2, "flag": "🇫🇯"},
    "MUR": {"name": "Mauritian Rupee", "symbol": "₨", "rate": 46.5, "decimals": 2, "flag": "🇲🇺"},
    "BWP": {"name": "Botswana Pula", "symbol": "P", "rate": 13.6, "decimals": 2, "flag": "🇧🇼"},
}

# Comprehensive list of countries with official ISO code, flag emoji, and primary currency
COUNTRIES: List[dict] = [
    {"code": "US", "name": "United States", "currency": "USD", "flag": "🇺🇸"},
    {"code": "GB", "name": "United Kingdom", "currency": "GBP", "flag": "🇬🇧"},
    {"code": "CA", "name": "Canada", "currency": "CAD", "flag": "🇨🇦"},
    {"code": "AU", "name": "Australia", "currency": "AUD", "flag": "🇦🇺"},
    {"code": "DE", "name": "Germany", "currency": "EUR", "flag": "🇩🇪"},
    {"code": "FR", "name": "France", "currency": "EUR", "flag": "🇫🇷"},
    {"code": "IT", "name": "Italy", "currency": "EUR", "flag": "🇮🇹"},
    {"code": "ES", "name": "Spain", "currency": "EUR", "flag": "🇪🇸"},
    {"code": "NL", "name": "Netherlands", "currency": "EUR", "flag": "🇳🇱"},
    {"code": "CH", "name": "Switzerland", "currency": "CHF", "flag": "🇨🇭"},
    {"code": "JP", "name": "Japan", "currency": "JPY", "flag": "🇯🇵"},
    {"code": "IN", "name": "India", "currency": "INR", "flag": "🇮🇳"},
    {"code": "CN", "name": "China", "currency": "CNY", "flag": "🇨🇳"},
    {"code": "AE", "name": "United Arab Emirates", "currency": "AED", "flag": "🇦🇪"},
    {"code": "SA", "name": "Saudi Arabia", "currency": "SAR", "flag": "🇸🇦"},
    {"code": "SG", "name": "Singapore", "currency": "SGD", "flag": "🇸🇬"},
    {"code": "KR", "name": "South Korea", "currency": "KRW", "flag": "🇰🇷"},
    {"code": "NZ", "name": "New Zealand", "currency": "NZD", "flag": "🇳🇿"},
    {"code": "BR", "name": "Brazil", "currency": "BRL", "flag": "🇧🇷"},
    {"code": "MX", "name": "Mexico", "currency": "MXN", "flag": "🇲🇽"},
    {"code": "ZA", "name": "South Africa", "currency": "ZAR", "flag": "🇿🇦"},
    {"code": "TH", "name": "Thailand", "currency": "THB", "flag": "🇹🇭"},
    {"code": "SE", "name": "Sweden", "currency": "SEK", "flag": "🇸🇪"},
    {"code": "NO", "name": "Norway", "currency": "NOK", "flag": "🇳🇴"},
    {"code": "TR", "name": "Turkey", "currency": "TRY", "flag": "🇹🇷"},
    {"code": "ID", "name": "Indonesia", "currency": "IDR", "flag": "🇮🇩"},
    {"code": "HK", "name": "Hong Kong", "currency": "HKD", "flag": "🇭🇰"},
    {"code": "TW", "name": "Taiwan", "currency": "TWD", "flag": "🇹🇼"},
    {"code": "PL", "name": "Poland", "currency": "PLN", "flag": "🇵🇱"},
    {"code": "DK", "name": "Denmark", "currency": "DKK", "flag": "🇩🇰"},
    {"code": "MY", "name": "Malaysia", "currency": "MYR", "flag": "🇲🇾"},
    {"code": "PH", "name": "Philippines", "currency": "PHP", "flag": "🇵🇭"},
    {"code": "CZ", "name": "Czech Republic", "currency": "CZK", "flag": "🇨🇿"},
    {"code": "IL", "name": "Israel", "currency": "ILS", "flag": "🇮🇱"},
    {"code": "CL", "name": "Chile", "currency": "CLP", "flag": "🇨🇱"},
    {"code": "CO", "name": "Colombia", "currency": "COP", "flag": "🇨🇴"},
    {"code": "EG", "name": "Egypt", "currency": "EGP", "flag": "🇪🇬"},
    {"code": "VN", "name": "Vietnam", "currency": "VND", "flag": "🇻🇳"},
    {"code": "QA", "name": "Qatar", "currency": "QAR", "flag": "🇶🇦"},
    {"code": "KW", "name": "Kuwait", "currency": "KWD", "flag": "🇰🇼"},
    {"code": "BH", "name": "Bahrain", "currency": "BHD", "flag": "🇧🇭"},
    {"code": "OM", "name": "Oman", "currency": "OMR", "flag": "🇴🇲"},
    {"code": "AR", "name": "Argentina", "currency": "ARS", "flag": "🇦🇷"},
    {"code": "PK", "name": "Pakistan", "currency": "PKR", "flag": "🇵🇰"},
    {"code": "BD", "name": "Bangladesh", "currency": "BDT", "flag": "🇧🇩"},
    {"code": "NG", "name": "Nigeria", "currency": "NGN", "flag": "🇳🇬"},
    {"code": "KE", "name": "Kenya", "currency": "KES", "flag": "🇰🇪"},
    {"code": "GH", "name": "Ghana", "currency": "GHS", "flag": "🇬🇭"},
    {"code": "MA", "name": "Morocco", "currency": "MAD", "flag": "🇲🇦"},
    {"code": "HU", "name": "Hungary", "currency": "HUF", "flag": "🇭🇺"},
    {"code": "RO", "name": "Romania", "currency": "RON", "flag": "🇷🇴"},
    {"code": "BG", "name": "Bulgaria", "currency": "BGN", "flag": "🇧🇬"},
    {"code": "IS", "name": "Iceland", "currency": "ISK", "flag": "🇮🇸"},
    {"code": "RS", "name": "Serbia", "currency": "RSD", "flag": "🇷🇸"},
    {"code": "UA", "name": "Ukraine", "currency": "UAH", "flag": "🇺🇦"},
    {"code": "KZ", "name": "Kazakhstan", "currency": "KZT", "flag": "🇰🇿"},
    {"code": "PE", "name": "Peru", "currency": "PEN", "flag": "🇵🇪"},
    {"code": "UY", "name": "Uruguay", "currency": "UYU", "flag": "🇺🇾"},
    {"code": "CR", "name": "Costa Rica", "currency": "CRC", "flag": "🇨🇷"},
    {"code": "DO", "name": "Dominican Republic", "currency": "DOP", "flag": "🇩🇴"},
    {"code": "JM", "name": "Jamaica", "currency": "JMD", "flag": "🇯🇲"},
    {"code": "LK", "name": "Sri Lanka", "currency": "LKR", "flag": "🇱🇰"},
    {"code": "NP", "name": "Nepal", "currency": "NPR", "flag": "🇳🇵"},
    {"code": "MV", "name": "Maldives", "currency": "MVR", "flag": "🇲🇻"},
    {"code": "FJ", "name": "Fiji", "currency": "FJD", "flag": "🇫🇯"},
    {"code": "MU", "name": "Mauritius", "currency": "MUR", "flag": "🇲🇺"},
    {"code": "BW", "name": "Botswana", "currency": "BWP", "flag": "🇧🇼"},
    {"code": "AT", "name": "Austria", "currency": "EUR", "flag": "🇦🇹"},
    {"code": "BE", "name": "Belgium", "currency": "EUR", "flag": "🇧🇪"},
    {"code": "PT", "name": "Portugal", "currency": "EUR", "flag": "🇵🇹"},
    {"code": "GR", "name": "Greece", "currency": "EUR", "flag": "🇬🇷"},
    {"code": "IE", "name": "Ireland", "currency": "EUR", "flag": "🇮🇪"},
    {"code": "FI", "name": "Finland", "currency": "EUR", "flag": "🇫🇮"},
]


class CurrencyService:
    @staticmethod
    def get_supported_currencies() -> Dict[str, dict]:
        return EXCHANGE_RATES

    @staticmethod
    def get_supported_countries() -> List[dict]:
        return COUNTRIES

    @staticmethod
    def convert_usd(amount_usd: float, target_currency: str) -> dict:
        """
        Converts an amount from base USD into target_currency.
        Returns precise converted amount, formatted representation, rate, and base amount.
        """
        target_curr = target_currency.upper().strip()
        info = EXCHANGE_RATES.get(target_curr, EXCHANGE_RATES["USD"])
        rate = info["rate"]
        decimals = info.get("decimals", 2)
        converted_amount = round(amount_usd * rate, decimals)

        symbol = info["symbol"]
        if decimals == 0:
            formatted = f"{symbol}{int(round(converted_amount)):,}"
        else:
            formatted = f"{symbol}{converted_amount:,.{decimals}f}"

        return {
            "base_usd": round(amount_usd, 2),
            "target_currency": target_curr,
            "currency_name": info["name"],
            "currency_symbol": symbol,
            "exchange_rate": rate,
            "converted_amount": converted_amount,
            "formatted": formatted,
            "conversion_display": f"1 USD = {rate:,.2f} {target_curr}"
        }


currency_service = CurrencyService()
