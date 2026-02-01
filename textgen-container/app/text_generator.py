from app.csv_parser import Beneficiary
from app.phone_formatter import format_phone, extract_last_4_digits


def generate_filename(route_num: int, sequence: int, name: str, phone: str) -> str:
    """
    Generate unique filename for packing slip.
    Format: Route_{route_num}_{sequence:02d}_{initials}_{last4}.txt
    """
    # Extract initials from name
    parts = name.strip().split()
    initials = ''.join(p[0].upper() for p in parts if p)[:2]
    if not initials:
        initials = 'XX'

    # Last 4 digits of phone
    last4 = extract_last_4_digits(phone)

    return f"Route_{route_num}_{sequence:02d}_{initials}_{last4}.txt"


def generate_packing_slip(beneficiary: Beneficiary, route_num: int, sequence: int) -> str:
    """
    Generate bilingual packing slip text for a beneficiary.
    """
    formatted_phone, _ = format_phone(beneficiary.phone)
    phone_display = formatted_phone if formatted_phone else 'N/A'

    # Generate ID
    parts = beneficiary.name.strip().split()
    initials = ''.join(p[0].upper() for p in parts if p)[:2] or 'XX'
    last4 = extract_last_4_digits(beneficiary.phone)
    slip_id = f"Route_{route_num}_{sequence:02d}_{initials}_{last4}"

    # Format special items section
    special_section = ""
    if beneficiary.special_items and beneficiary.special_items.strip():
        special_section = f"""
****************************************************************
*                 SPECIAL ITEMS / ARTICULOS ESPECIALES         *
****************************************************************
* {beneficiary.special_items:<60} *
****************************************************************
"""
    else:
        special_section = """
****************************************************************
*                 SPECIAL ITEMS / ARTICULOS ESPECIALES         *
****************************************************************
* None / Ninguno                                               *
****************************************************************
"""

    # Format items list
    items_list = beneficiary.items_needed if beneficiary.items_needed else 'N/A'

    # Format household size
    household = beneficiary.household_size if beneficiary.household_size else 'N/A'

    # Format contact preference
    contact = beneficiary.contact_preference if beneficiary.contact_preference else 'N/A'

    # Format notes
    notes_section = ""
    if beneficiary.notes and beneficiary.notes.strip():
        notes_section = f"""
----------------------------------------------------------------
NOTAS / NOTES
----------------------------------------------------------------
{beneficiary.notes}
"""

    # Format address
    address = beneficiary.address if beneficiary.address else 'N/A'

    template = f"""================================================================
                    DELIVERY / ENTREGA
================================================================
ID: {slip_id}
================================================================

DIRECCION / ADDRESS:
{address}

TELEFONO / PHONE: {phone_display}

----------------------------------------------------------------
HOGAR / HOUSEHOLD
----------------------------------------------------------------
Numero de personas / Number of people: {household}

----------------------------------------------------------------
ARTICULOS NECESARIOS / ITEMS NEEDED
----------------------------------------------------------------
{items_list}
{special_section}{notes_section}
----------------------------------------------------------------
CONTACTO / CONTACT PREFERENCE
----------------------------------------------------------------
{contact}

================================================================
"""

    return template


def generate_all_slips(beneficiaries: list, route_num: int = 1) -> list:
    """
    Generate packing slips for all valid beneficiaries (sequential numbering).

    Returns:
        list of tuples: (filename, content)
    """
    results = []
    sequence = 1

    for beneficiary in beneficiaries:
        if not beneficiary.is_valid():
            continue

        filename = generate_filename(route_num, sequence, beneficiary.name, beneficiary.phone)
        content = generate_packing_slip(beneficiary, route_num, sequence)
        results.append((filename, content))
        sequence += 1

    return results


def generate_all_slips_with_routes(beneficiaries_with_routes: list) -> list:
    """
    Generate packing slips using route assignments from routing app.
    Creates ONE file per route with all packing slips concatenated.

    Args:
        beneficiaries_with_routes: list of dicts with beneficiary data and route_number/route_sequence

    Returns:
        list of tuples: (filename, content) - one file per route
    """
    # Group by route
    by_route = {}
    unassigned = []

    for b in beneficiaries_with_routes:
        if b.get('route_number') is not None and b.get('route_sequence') is not None:
            route_num = b['route_number']
            if route_num not in by_route:
                by_route[route_num] = []
            by_route[route_num].append(b)
        else:
            unassigned.append(b)

    results = []

    # Helper class for beneficiary data
    class BeneficiaryData:
        def __init__(self, data):
            self.name = data['name']
            self.phone = data['phone']
            self.address = data['address']
            self.household_size = data.get('household_size', '')
            self.items_needed = data.get('items_needed', '')
            self.special_items = data.get('special_items', '')
            self.contact_preference = data.get('contact_preference', '')
            self.notes = data.get('notes', '')

    # Process assigned beneficiaries by route order - ONE FILE PER ROUTE
    for route_num in sorted(by_route.keys()):
        route_beneficiaries = sorted(by_route[route_num], key=lambda x: x['route_sequence'])

        # Build combined content for this route
        route_slips = []
        route_slips.append(f"{'='*64}")
        route_slips.append(f"                    ROUTE {route_num} - {len(route_beneficiaries)} STOPS")
        route_slips.append(f"{'='*64}")
        route_slips.append("")

        for b in route_beneficiaries:
            ben = BeneficiaryData(b)
            sequence = b['route_sequence']
            slip_content = generate_packing_slip(ben, route_num, sequence)
            route_slips.append(slip_content)
            route_slips.append("\n" + "-"*64 + "\n")  # Page break between slips

        filename = f"Route_{route_num:02d}_packing_slips.txt"
        combined_content = "\n".join(route_slips)
        results.append((filename, combined_content))

    # Process unassigned beneficiaries (route 99)
    if unassigned:
        route_slips = []
        route_slips.append(f"{'='*64}")
        route_slips.append(f"              ROUTE 99 - UNASSIGNED ({len(unassigned)} STOPS)")
        route_slips.append(f"{'='*64}")
        route_slips.append("NOTE: These addresses could not be matched to the route manifest.")
        route_slips.append("")

        for seq, b in enumerate(unassigned, start=1):
            ben = BeneficiaryData(b)
            slip_content = generate_packing_slip(ben, 99, seq)
            route_slips.append(slip_content)
            route_slips.append("\n" + "-"*64 + "\n")

        filename = "Route_99_unassigned_packing_slips.txt"
        combined_content = "\n".join(route_slips)
        results.append((filename, combined_content))

    return results
