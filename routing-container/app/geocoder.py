import time
import re
from typing import Optional, Tuple
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderServiceError, GeocoderUnavailable


# Rate limiting for Nominatim (1 request per second)
_last_request_time = 0
_MIN_REQUEST_INTERVAL = 1.1  # seconds


def normalize_address(address: str) -> str:
    """
    Normalize address for better geocoding success.
    Expands abbreviations, removes problematic elements.
    """
    if not address:
        return address

    addr = address.strip()

    # Common street type abbreviations
    abbreviations = {
        r'\bSt\b\.?': 'Street',
        r'\bAve\b\.?': 'Avenue',
        r'\bBlvd\b\.?': 'Boulevard',
        r'\bDr\b\.?': 'Drive',
        r'\bLn\b\.?': 'Lane',
        r'\bRd\b\.?': 'Road',
        r'\bCt\b\.?': 'Court',
        r'\bPl\b\.?': 'Place',
        r'\bPkwy\b\.?': 'Parkway',
        r'\bHwy\b\.?': 'Highway',
        r'\bCir\b\.?': 'Circle',
        r'\bTrl\b\.?': 'Trail',
        r'\bTer\b\.?': 'Terrace',
        r'\bWay\b\.?': 'Way',
    }

    # Direction abbreviations
    directions = {
        r'\bN\b\.?': 'North',
        r'\bS\b\.?': 'South',
        r'\bE\b\.?': 'East',
        r'\bW\b\.?': 'West',
        r'\bNE\b\.?': 'Northeast',
        r'\bNW\b\.?': 'Northwest',
        r'\bSE\b\.?': 'Southeast',
        r'\bSW\b\.?': 'Southwest',
    }

    # Apply abbreviation expansions
    for pattern, replacement in abbreviations.items():
        addr = re.sub(pattern, replacement, addr, flags=re.IGNORECASE)

    for pattern, replacement in directions.items():
        addr = re.sub(pattern, replacement, addr, flags=re.IGNORECASE)

    # Remove extra whitespace
    addr = ' '.join(addr.split())

    return addr


def create_address_variations(address: str) -> list:
    """
    Create variations of an address to try if the original fails.
    """
    variations = []

    if not address:
        return [address]

    # Variation 1: Original address
    variations.append(address)

    # Variation 2: Remove suite/unit/apt numbers
    no_suite = re.sub(r',?\s*(Suite|Ste|Unit|Apt|#)\s*[\w-]+', '', address, flags=re.IGNORECASE)
    no_suite = ' '.join(no_suite.split())  # Clean up whitespace
    if no_suite != address and no_suite not in variations:
        variations.append(no_suite)

    # Variation 3: Normalized version (expand abbreviations)
    normalized = normalize_address(address)
    if normalized not in variations:
        variations.append(normalized)

    # Variation 4: Normalized without suite
    normalized_no_suite = normalize_address(no_suite)
    if normalized_no_suite not in variations:
        variations.append(normalized_no_suite)

    # Variation 5: Add USA suffix
    with_usa = address + ", USA"
    if with_usa not in variations:
        variations.append(with_usa)

    # Variation 6: No suite with USA
    no_suite_usa = no_suite + ", USA"
    if no_suite_usa not in variations:
        variations.append(no_suite_usa)

    # Variation 7: Just city and state with street number and name
    # Try to extract core address without zip
    no_zip = re.sub(r'\b\d{5}(-\d{4})?\b', '', no_suite)
    no_zip = no_zip.strip().rstrip(',').strip()
    if no_zip not in variations:
        variations.append(no_zip)

    return variations


def _rate_limit():
    """Ensure we don't exceed Nominatim rate limits."""
    global _last_request_time
    now = time.time()
    elapsed = now - _last_request_time
    if elapsed < _MIN_REQUEST_INTERVAL:
        time.sleep(_MIN_REQUEST_INTERVAL - elapsed)
    _last_request_time = time.time()


# Initialize geocoder with proper user agent
_geocoder = None


def get_geocoder() -> Nominatim:
    """Get or create the geocoder instance."""
    global _geocoder
    if _geocoder is None:
        _geocoder = Nominatim(
            user_agent="humanitarian-aid-delivery-router/1.0",
            timeout=10
        )
    return _geocoder


def geocode_address(address: str, max_retries: int = 3) -> Tuple[Optional[float], Optional[float], str]:
    """
    Geocode an address to latitude/longitude coordinates.
    Tries multiple address variations if the original fails.

    Args:
        address: The street address to geocode
        max_retries: Number of retry attempts for transient failures

    Returns:
        Tuple of (latitude, longitude, error_message)
        If successful, error_message will be empty string
        If failed, lat/lon will be None and error_message will describe the issue
    """
    if not address or not address.strip():
        return None, None, "Empty address"

    geocoder = get_geocoder()

    # Generate address variations to try
    variations = create_address_variations(address.strip())
    last_error = "Address not found"

    for addr_variation in variations:
        if not addr_variation.strip():
            continue

        for attempt in range(max_retries):
            try:
                _rate_limit()
                location = geocoder.geocode(addr_variation, exactly_one=True, addressdetails=True)

                if location:
                    return location.latitude, location.longitude, ""
                else:
                    # This variation didn't work, try next
                    break

            except GeocoderTimedOut:
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)  # Exponential backoff
                    continue
                last_error = "Geocoding timed out"
                break

            except GeocoderUnavailable:
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
                    continue
                last_error = "Geocoding service unavailable"
                break

            except GeocoderServiceError as e:
                last_error = f"Geocoding service error: {str(e)}"
                break

            except Exception as e:
                last_error = f"Unexpected error: {str(e)}"
                break

    return None, None, last_error


def geocode_beneficiaries(beneficiaries: list, progress_callback=None) -> list:
    """
    Geocode all beneficiaries in the list.

    Args:
        beneficiaries: List of Beneficiary objects
        progress_callback: Optional callback(current, total) for progress updates

    Returns:
        Updated list of beneficiaries with geocoding results
    """
    total = len(beneficiaries)

    for i, beneficiary in enumerate(beneficiaries):
        if beneficiary.excluded or not beneficiary.is_valid():
            continue

        lat, lon, error = geocode_address(beneficiary.address)

        beneficiary.latitude = lat
        beneficiary.longitude = lon
        beneficiary.geocode_error = error

        if error:
            beneficiary.warnings.append(f"Geocoding: {error}")
            beneficiary.flagged = True

        if progress_callback:
            progress_callback(i + 1, total)

    return beneficiaries


def export_failed_geocodes(beneficiaries: list) -> str:
    """
    Export failed geocodes to CSV format.

    Args:
        beneficiaries: List of beneficiary dicts with geocoding results

    Returns:
        CSV content as string
    """
    import csv
    import io

    output = io.StringIO()
    writer = csv.writer(output)

    # Header
    writer.writerow([
        'row_number', 'name', 'phone', 'address', 'household_size',
        'items_needed', 'special_items', 'contact_preference', 'notes', 'geocode_error'
    ])

    # Write failed records
    for b in beneficiaries:
        if b.get('latitude') is None and not b.get('excluded') and len(b.get('errors', [])) == 0:
            writer.writerow([
                b.get('row_number', ''),
                b.get('name', ''),
                b.get('phone', ''),
                b.get('address', ''),
                b.get('household_size', ''),
                b.get('items_needed', ''),
                b.get('special_items', ''),
                b.get('contact_preference', ''),
                b.get('notes', ''),
                b.get('geocode_error', 'Unknown error')
            ])

    return output.getvalue()


def calculate_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculate approximate distance between two points in kilometers.
    Uses Haversine formula.
    """
    from math import radians, sin, cos, sqrt, atan2

    R = 6371  # Earth's radius in kilometers

    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])

    dlat = lat2 - lat1
    dlon = lon2 - lon1

    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * atan2(sqrt(a), sqrt(1-a))

    return R * c
