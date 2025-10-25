import re


def normalize_phone_e164(phone: str, default_country_code: str = "+963") -> str:
    """Normalize phone numbers to a basic E.164 form.

    Supports Syria as the default country; falls back to the raw value if we cannot infer.
    """
    if not phone:
        return ""
    raw = re.sub(r"[^\d+]", "", phone)
    if raw.startswith("+"):
        return raw
    if raw.startswith("00"):
        return "+" + raw[2:]
    if raw.startswith("0") and len(raw) >= 9 and default_country_code.startswith("+"):
        # Convert local leading-zero numbers (e.g., 09xxxx -> +9639xxxx)
        return default_country_code + raw[1:]
    return raw


def mask_phone(phone: str, visible_digits: int = 2) -> str:
    if not phone:
        return ""
    normalized = normalize_phone_e164(phone)
    if len(normalized) <= visible_digits:
        return normalized
    masked_portion = "*" * max(len(normalized) - visible_digits, 0)
    return masked_portion + normalized[-visible_digits:]
