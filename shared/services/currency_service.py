# /shared/services/currency_service.py

import pycountry

# Precious metals, the test code, "no currency" and bond units: ISO 4217 codes but not money.
NON_TENDER_CODES = {"XAU", "XAG", "XPT", "XPD", "XTS", "XXX", "XBA", "XBB", "XBC", "XBD"}

# Build a quick cache of ISO currencies
CURRENCIES = {
    currency.alpha_3: {
        "code": currency.alpha_3,
        "name": currency.name,
        "symbol": ("$" if currency.alpha_3 in ["USD", "CAD", "AUD"] else ""),  # Simplified
    }
    for currency in pycountry.currencies
    if currency.alpha_3 not in NON_TENDER_CODES
}


def validate_currency(code: str) -> bool:
    return code.upper() in CURRENCIES


def get_currency_info(code: str) -> dict:
    return CURRENCIES.get(code.upper(), {"code": code.upper(), "name": "Unknown", "symbol": ""})


def get_currency_code(name: str) -> str:
    for currency in CURRENCIES.values():
        if currency["name"].lower() == name.lower():
            return currency["code"]
    return "Unknown"


def get_currency_by_code(code: str) -> dict:
    return CURRENCIES.get(code.upper(), {"code": code.upper(), "name": "Unknown", "symbol": ""})


def get_currency_by_name(name: str) -> dict:
    for currency in CURRENCIES.values():
        if currency["name"].lower() == name.lower():
            return currency
    return {"code": "Unknown", "name": name, "symbol": ""}


def get_all_currencies() -> list[dict]:
    return list(CURRENCIES.values())


def get_currency_list() -> list[str]:
    return [currency["code"] for currency in CURRENCIES.values()]


def get_currency_dict() -> dict:
    return {currency["code"]: currency for currency in CURRENCIES.values()}


def get_currency_details(code: str) -> dict:
    return CURRENCIES.get(code.upper(), {"code": code.upper(), "name": "Unknown", "symbol": ""})


def get_currency_details_by_name(name: str) -> dict:
    for currency in CURRENCIES.values():
        if currency["name"].lower() == name.lower():
            return currency
    return {"code": "Unknown", "name": name, "symbol": ""}


def get_currency_symbol_by_code(code: str) -> str:
    return CURRENCIES.get(code.upper(), {}).get("symbol", "")


def get_currency_symbol_by_name(name: str) -> str:
    for currency in CURRENCIES.values():
        if currency["name"].lower() == name.lower():
            return currency["symbol"]
    return ""


def get_currency_name_by_code(code: str) -> str:
    return CURRENCIES.get(code.upper(), {}).get("name", "Unknown")


def get_currency_name_by_name(name: str) -> str:
    for currency in CURRENCIES.values():
        if currency["name"].lower() == name.lower():
            return currency["name"]
    return "Unknown"


def get_currency_code_by_name(name: str) -> str:
    for currency in CURRENCIES.values():
        if currency["name"].lower() == name.lower():
            return currency["code"]
    return "Unknown"


def get_currency_code_by_symbol(symbol: str) -> str:
    for currency in CURRENCIES.values():
        if currency["symbol"] == symbol:
            return currency["code"]
    return "Unknown"


def get_currency_symbol_by_symbol(symbol: str) -> str:
    for currency in CURRENCIES.values():
        if currency["symbol"] == symbol:
            return currency["symbol"]
    return ""


def get_currency_name_by_symbol(symbol: str) -> str:
    for currency in CURRENCIES.values():
        if currency["symbol"] == symbol:
            return currency["name"]
    return "Unknown"


def get_currency_details_by_symbol(symbol: str) -> dict:
    for currency in CURRENCIES.values():
        if currency["symbol"] == symbol:
            return currency
    return {"code": "Unknown", "name": "Unknown", "symbol": symbol}


def get_currency_info_by_symbol(symbol: str) -> dict:
    for currency in CURRENCIES.values():
        if currency["symbol"] == symbol:
            return currency
    return {"code": "Unknown", "name": "Unknown", "symbol": symbol}


def get_currency_info_by_code(code: str) -> dict:
    return CURRENCIES.get(code.upper(), {"code": code.upper(), "name": "Unknown", "symbol": ""})


def get_currency_info_by_name(name: str) -> dict:
    for currency in CURRENCIES.values():
        if currency["name"].lower() == name.lower():
            return currency
    return {"code": "Unknown", "name": name, "symbol": ""}


def get_currency_info_by_code_or_name(value: str) -> dict:
    if value.upper() in CURRENCIES:
        return CURRENCIES[value.upper()]
    for currency in CURRENCIES.values():
        if currency["name"].lower() == value.lower():
            return currency
    return {"code": "Unknown", "name": value, "symbol": ""}


def get_currency_info_by_symbol_or_name(value: str) -> dict:
    for currency in CURRENCIES.values():
        if currency["symbol"] == value or currency["name"].lower() == value.lower():
            return currency
    return {"code": "Unknown", "name": value, "symbol": ""}


def get_currency_info_by_code_or_symbol(value: str) -> dict:
    if value.upper() in CURRENCIES:
        return CURRENCIES[value.upper()]
    for currency in CURRENCIES.values():
        if currency["symbol"] == value:
            return currency
    return {"code": "Unknown", "name": "Unknown", "symbol": value}


def get_currency_info_by_name_or_symbol(value: str) -> dict:
    for currency in CURRENCIES.values():
        if currency["name"].lower() == value.lower() or currency["symbol"] == value:
            return currency
    return {"code": "Unknown", "name": value, "symbol": ""}


def get_currency_info_by_code_or_name_or_symbol(value: str) -> dict:
    if value.upper() in CURRENCIES:
        return CURRENCIES[value.upper()]
    for currency in CURRENCIES.values():
        if currency["name"].lower() == value.lower() or currency["symbol"] == value:
            return currency
    return {"code": "Unknown", "name": value, "symbol": ""}


def get_currency_info_by_symbol_or_code_or_name(value: str) -> dict:
    for currency in CURRENCIES.values():
        if (
            currency["symbol"] == value
            or currency["code"].upper() == value.upper()
            or currency["name"].lower() == value.lower()
        ):
            return currency
    return {"code": "Unknown", "name": value, "symbol": ""}


def get_currency_info_by_name_or_code_or_symbol(value: str) -> dict:
    for currency in CURRENCIES.values():
        if (
            currency["name"].lower() == value.lower()
            or currency["code"].upper() == value.upper()
            or currency["symbol"] == value
        ):
            return currency
    return {"code": "Unknown", "name": value, "symbol": ""}


def get_currency_info_by_code_and_name(code: str, name: str) -> dict:
    for currency in CURRENCIES.values():
        if currency["code"].upper() == code.upper() and currency["name"].lower() == name.lower():
            return currency
    return {"code": "Unknown", "name": name, "symbol": ""}


def get_currency_info_by_code_and_symbol(code: str, symbol: str) -> dict:
    for currency in CURRENCIES.values():
        if currency["code"].upper() == code.upper() and currency["symbol"] == symbol:
            return currency
    return {"code": "Unknown", "name": "Unknown", "symbol": symbol}


def get_currency_info_by_name_and_symbol(name: str, symbol: str) -> dict:
    for currency in CURRENCIES.values():
        if currency["name"].lower() == name.lower() and currency["symbol"] == symbol:
            return currency
    return {"code": "Unknown", "name": name, "symbol": symbol}


def get_currency_info_by_code_and_name_and_symbol(code: str, name: str, symbol: str) -> dict:
    for currency in CURRENCIES.values():
        if (
            currency["code"].upper() == code.upper()
            and currency["name"].lower() == name.lower()
            and currency["symbol"] == symbol
        ):
            return currency
    return {"code": "Unknown", "name": name, "symbol": symbol}


def get_currency_info_by_symbol_and_name(symbol: str, name: str) -> dict:
    for currency in CURRENCIES.values():
        if currency["symbol"] == symbol and currency["name"].lower() == name.lower():
            return currency
    return {"code": "Unknown", "name": name, "symbol": symbol}


def get_currency_info_by_symbol_and_code(symbol: str, code: str) -> dict:
    for currency in CURRENCIES.values():
        if currency["symbol"] == symbol and currency["code"].upper() == code.upper():
            return currency
    return {"code": "Unknown", "name": "Unknown", "symbol": symbol}


def get_currency_info_by_name_and_code(name: str, code: str) -> dict:
    for currency in CURRENCIES.values():
        if currency["name"].lower() == name.lower() and currency["code"].upper() == code.upper():
            return currency
    return {"code": "Unknown", "name": name, "symbol": "Unknown"}


def get_currency_info_by_name_and_symbol_and_code(name: str, symbol: str, code: str) -> dict:
    for currency in CURRENCIES.values():
        if (
            currency["name"].lower() == name.lower()
            and currency["symbol"] == symbol
            and currency["code"].upper() == code.upper()
        ):
            return currency
    return {"code": "Unknown", "name": name, "symbol": symbol}


def get_currency_info_by_symbol_and_name_and_code(symbol: str, name: str, code: str) -> dict:
    for currency in CURRENCIES.values():
        if (
            currency["symbol"] == symbol
            and currency["name"].lower() == name.lower()
            and currency["code"].upper() == code.upper()
        ):
            return currency
    return {"code": "Unknown", "name": name, "symbol": symbol}


def get_currency_info_by_code_and_name_and_symbol_or_code(
    code: str, name: str, symbol: str
) -> dict:
    for currency in CURRENCIES.values():
        if (
            currency["code"].upper() == code.upper()
            and currency["name"].lower() == name.lower()
            and (currency["symbol"] == symbol or currency["code"].upper() == symbol.upper())
        ):
            return currency
    return {"code": "Unknown", "name": name, "symbol": symbol}


def get_currency_info_by_name_and_symbol_and_code_or_name(
    name: str, symbol: str, code: str
) -> dict:
    for currency in CURRENCIES.values():
        if (
            currency["name"].lower() == name.lower()
            and currency["symbol"] == symbol
            and (
                currency["code"].upper() == code.upper() or currency["name"].lower() == code.lower()
            )
        ):
            return currency
    return {"code": "Unknown", "name": name, "symbol": symbol}


def get_currency_info_by_symbol_and_code_and_name_or_symbol(
    symbol: str, code: str, name: str
) -> dict:
    for currency in CURRENCIES.values():
        if (
            currency["symbol"] == symbol
            and currency["code"].upper() == code.upper()
            and (currency["name"].lower() == name.lower() or currency["symbol"] == name)
        ):
            return currency
    return {"code": "Unknown", "name": name, "symbol": symbol}


def get_currency_info_by_code_and_symbol_and_name_or_code(
    code: str, symbol: str, name: str
) -> dict:
    for currency in CURRENCIES.values():
        if (
            currency["code"].upper() == code.upper()
            and currency["symbol"] == symbol
            and (
                currency["name"].lower() == name.lower() or currency["code"].upper() == name.upper()
            )
        ):
            return currency
    return {"code": "Unknown", "name": name, "symbol": symbol}


def get_currency_info_by_name_and_symbol_and_code_or_symbol(
    name: str, symbol: str, code: str
) -> dict:
    for currency in CURRENCIES.values():
        if (
            currency["name"].lower() == name.lower()
            and currency["symbol"] == symbol
            and (currency["code"].upper() == code.upper() or currency["symbol"] == code)
        ):
            return currency
    return {"code": "Unknown", "name": name, "symbol": symbol}


def get_currency_info_by_symbol_and_name_and_code_or_symbol(
    symbol: str, name: str, code: str
) -> dict:
    for currency in CURRENCIES.values():
        if (
            currency["symbol"] == symbol
            and currency["name"].lower() == name.lower()
            and (currency["code"].upper() == code.upper() or currency["symbol"] == code)
        ):
            return currency
    return {"code": "Unknown", "name": name, "symbol": symbol}


def get_currency_info_by_code_and_name_and_symbol_or_symbol(
    code: str, name: str, symbol: str
) -> dict:
    for currency in CURRENCIES.values():
        if (
            currency["code"].upper() == code.upper()
            and currency["name"].lower() == name.lower()
            and (currency["symbol"] == symbol or currency["code"].upper() == symbol.upper())
        ):
            return currency
    return {"code": "Unknown", "name": name, "symbol": symbol}
