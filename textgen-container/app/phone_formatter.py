import phonenumbers
from phonenumbers import NumberParseException


def format_phone(phone_str: str) -> tuple[str, bool]:
    """
    Normalize phone number to US format: (XXX) XXX-XXXX

    Returns:
        tuple: (formatted_phone, success)
    """
    if not phone_str or not phone_str.strip():
        return '', False

    cleaned = phone_str.strip()

    try:
        # Try parsing as US number
        parsed = phonenumbers.parse(cleaned, 'US')

        if phonenumbers.is_valid_number(parsed):
            # Format as (XXX) XXX-XXXX
            formatted = phonenumbers.format_number(
                parsed,
                phonenumbers.PhoneNumberFormat.NATIONAL
            )
            return formatted, True
        else:
            # Invalid number - return cleaned digits
            digits = ''.join(c for c in cleaned if c.isdigit())
            if len(digits) >= 10:
                return f"({digits[:3]}) {digits[3:6]}-{digits[6:10]}", False
            return cleaned, False

    except NumberParseException:
        # Fallback: try to format raw digits
        digits = ''.join(c for c in cleaned if c.isdigit())
        if len(digits) >= 10:
            return f"({digits[:3]}) {digits[3:6]}-{digits[6:10]}", True
        elif len(digits) > 0:
            return cleaned, False
        return '', False


def extract_last_4_digits(phone_str: str) -> str:
    """Extract last 4 digits from phone number for filename generation."""
    digits = ''.join(c for c in phone_str if c.isdigit())
    if len(digits) >= 4:
        return digits[-4:]
    return digits.zfill(4)
