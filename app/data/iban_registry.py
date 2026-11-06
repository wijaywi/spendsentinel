"""
IBAN (International Bank Account Number) registry and validation.

Implements ISO 13616 and ISO 7064 (MOD 97-10) checksum validation
for international bank accounts.
"""

from typing import Dict, Tuple

# Mapping of ISO country code to expected IBAN length.
# Covering 76 recognized IBAN jurisdictions.
IBAN_COUNTRY_LENGTHS: Dict[str, int] = {
    "AL": 28,  # Albania
    "AD": 24,  # Andorra
    "AT": 20,  # Austria
    "AZ": 28,  # Azerbaijan
    "BH": 22,  # Bahrain
    "BY": 28,  # Belarus
    "BE": 16,  # Belgium
    "BA": 20,  # Bosnia and Herzegovina
    "BR": 29,  # Brazil
    "BG": 22,  # Bulgaria
    "CR": 22,  # Costa Rica
    "HR": 21,  # Croatia
    "CY": 28,  # Cyprus
    "CZ": 24,  # Czech Republic
    "DK": 18,  # Denmark
    "DO": 28,  # Dominican Republic
    "EE": 20,  # Estonia
    "EG": 29,  # Egypt
    "FO": 18,  # Faroe Islands
    "FI": 18,  # Finland
    "FR": 27,  # France
    "GE": 22,  # Georgia
    "DE": 22,  # Germany
    "GI": 23,  # Gibraltar
    "GR": 27,  # Greece
    "GL": 18,  # Greenland
    "GT": 28,  # Guatemala
    "HU": 28,  # Hungary
    "IS": 26,  # Iceland
    "IQ": 23,  # Iraq
    "IE": 22,  # Ireland
    "IL": 23,  # Israel
    "IT": 27,  # Italy
    "JO": 30,  # Jordan
    "KZ": 20,  # Kazakhstan
    "XK": 20,  # Kosovo
    "KW": 30,  # Kuwait
    "LV": 21,  # Latvia
    "LB": 28,  # Lebanon
    "LI": 21,  # Liechtenstein
    "LT": 20,  # Lithuania
    "LU": 20,  # Luxembourg
    "MK": 19,  # North Macedonia
    "MT": 31,  # Malta
    "MR": 27,  # Mauritania
    "MU": 30,  # Mauritius
    "MD": 24,  # Moldova
    "MC": 27,  # Monaco
    "ME": 22,  # Montenegro
    "NL": 18,  # Netherlands
    "NI": 28,  # Nicaragua
    "NO": 15,  # Norway
    "PK": 24,  # Pakistan
    "PS": 29,  # Palestinian Territories
    "PL": 28,  # Poland
    "PT": 25,  # Portugal
    "QA": 29,  # Qatar
    "RO": 24,  # Romania
    "LC": 32,  # Saint Lucia
    "SM": 27,  # San Marino
    "ST": 25,  # Sao Tome and Principe
    "SA": 24,  # Saudi Arabia
    "RS": 22,  # Serbia
    "SC": 31,  # Seychelles
    "SK": 24,  # Slovakia
    "SI": 19,  # Slovenia
    "SO": 23,  # Somalia
    "ES": 24,  # Spain
    "SE": 24,  # Sweden
    "CH": 21,  # Switzerland
    "TN": 24,  # Tunisia
    "TR": 26,  # Turkey
    "UA": 29,  # Ukraine
    "AE": 23,  # United Arab Emirates
    "GB": 22,  # United Kingdom
    "VA": 22,  # Vatican City
    "VG": 24,  # British Virgin Islands
}


def format_iban(iban: str) -> str:
    """
    Format an IBAN by stripping whitespace and converting to uppercase.

    Args:
        iban: Raw IBAN string which may include spaces, tabs, or lowercase characters.

    Returns:
        Cleaned, uppercase alphanumeric IBAN string.
    """
    if not iban:
        return ""
    return "".join(iban.split()).upper()


def is_iban_country(country_code: str) -> bool:
    """
    Check if a given ISO 2-letter country code is in the IBAN registry.

    Args:
        country_code: ISO 3166-1 alpha-2 country code.

    Returns:
        True if the country issues standard IBANs, False otherwise.
    """
    if not country_code:
        return False
    return country_code.strip().upper() in IBAN_COUNTRY_LENGTHS


def validate_iban(iban: str) -> Tuple[bool, str]:
    """
    Validate an IBAN structure, country code support, length, and ISO 7064 MOD-97-10 checksum.

    Args:
        iban: The IBAN string to validate.

    Returns:
        A tuple of (is_valid: bool, message: str).
        If invalid, the message details why it failed and how to remediate.
    """
    if not iban or not isinstance(iban, str):
        return False, "IBAN is empty or not provided. Please supply a valid account identifier."

    cleaned = format_iban(iban)

    if len(cleaned) < 4:
        return (
            False,
            f"IBAN '{cleaned}' is too short ({len(cleaned)} chars). Minimum length is 4 characters.",
        )

    if not cleaned.isalnum():
        return (
            False,
            "IBAN contains invalid characters. Only alphanumeric ASCII characters (A-Z, 0-9) are allowed.",
        )

    country_code = cleaned[:2]
    check_digits = cleaned[2:4]

    if not country_code.isalpha():
        return (
            False,
            f"Invalid IBAN prefix '{country_code}'. The first 2 characters must be an ISO 3166-1 country code.",
        )

    if not check_digits.isdigit():
        return (
            False,
            f"Invalid IBAN check digits '{check_digits}'. Characters 3 and 4 must be numeric digits.",
        )

    if country_code not in IBAN_COUNTRY_LENGTHS:
        return (
            False,
            f"Country code '{country_code}' is not recognized as an IBAN jurisdiction. "
            f"Verify if the recipient country supports IBAN or requires standard account/routing format.",
        )

    expected_len = IBAN_COUNTRY_LENGTHS[country_code]
    actual_len = len(cleaned)
    if actual_len != expected_len:
        return (
            False,
            f"Invalid IBAN length for {country_code}: expected {expected_len} characters, but received {actual_len}. "
            f"Please verify account number completeness.",
        )

    # MOD-97-10 Checksum Algorithm (ISO 7064)
    # 1. Move first 4 characters (Country code + Check digits) to end.
    rearranged = cleaned[4:] + cleaned[:4]

    # 2. Convert letters A-Z to digits (A=10, B=11, ..., Z=35).
    numeric_str = "".join(str(ord(c) - 55) if c.isalpha() else c for c in rearranged)

    # 3. Compute modulus 97. Valid IBAN produces remainder of 1.
    remainder = int(numeric_str) % 97
    if remainder != 1:
        return (
            False,
            f"IBAN checksum validation failed (MOD-97 remainder was {remainder}, expected 1). "
            f"Check digits '{check_digits}' do not match the account number. Please verify for transposition typos.",
        )

    return True, f"IBAN format, length ({actual_len} chars), and checksum are valid for {country_code}."
