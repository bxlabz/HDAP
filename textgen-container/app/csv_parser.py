import csv
import io
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Beneficiary:
    """Represents a single beneficiary record."""
    row_number: int
    name: str
    phone: str
    address: str
    household_size: str
    items_needed: str
    special_items: str = ''
    contact_preference: str = ''
    notes: str = ''

    # Validation flags
    errors: list = field(default_factory=list)
    warnings: list = field(default_factory=list)
    flagged: bool = False

    def is_valid(self) -> bool:
        return len(self.errors) == 0


@dataclass
class ParseResult:
    """Result of parsing a CSV file."""
    beneficiaries: list
    errors: list
    warnings: list

    @property
    def has_errors(self) -> bool:
        return len(self.errors) > 0

    @property
    def valid_count(self) -> int:
        return sum(1 for b in self.beneficiaries if b.is_valid())


# Expected column headers (case-insensitive matching)
REQUIRED_COLUMNS = ['name', 'phone', 'address', 'household_size', 'items_needed']
OPTIONAL_COLUMNS = ['special_items', 'contact_preference', 'notes']


def normalize_header(header: str) -> str:
    """Normalize column header for matching."""
    return header.lower().strip().replace(' ', '_').replace('-', '_')


def find_column_mapping(headers: list) -> tuple[dict, list]:
    """
    Map CSV headers to expected column names.

    Returns:
        tuple: (column_mapping dict, list of missing required columns)
    """
    mapping = {}
    normalized_headers = {normalize_header(h): i for i, h in enumerate(headers)}

    missing = []
    for col in REQUIRED_COLUMNS:
        if col in normalized_headers:
            mapping[col] = normalized_headers[col]
        else:
            # Try common variations
            variations = {
                'name': ['full_name', 'beneficiary_name', 'recipient'],
                'phone': ['phone_number', 'telephone', 'tel', 'mobile'],
                'address': ['street_address', 'full_address', 'location'],
                'household_size': ['family_size', 'num_people', 'people'],
                'items_needed': ['items', 'needs', 'requested_items']
            }
            found = False
            for var in variations.get(col, []):
                if var in normalized_headers:
                    mapping[col] = normalized_headers[var]
                    found = True
                    break
            if not found:
                missing.append(col)

    # Map optional columns
    for col in OPTIONAL_COLUMNS:
        if col in normalized_headers:
            mapping[col] = normalized_headers[col]
        else:
            variations = {
                'special_items': ['special_needs', 'extras', 'additional_items'],
                'contact_preference': ['contact_method', 'preferred_contact'],
                'notes': ['comments', 'remarks', 'additional_notes']
            }
            for var in variations.get(col, []):
                if var in normalized_headers:
                    mapping[col] = normalized_headers[var]
                    break

    return mapping, missing


def parse_csv(file_content: str) -> ParseResult:
    """
    Parse CSV content and extract beneficiary records.

    Args:
        file_content: Raw CSV file content as string

    Returns:
        ParseResult with beneficiaries and any errors/warnings
    """
    beneficiaries = []
    errors = []
    warnings = []

    try:
        reader = csv.reader(io.StringIO(file_content))
        rows = list(reader)
    except csv.Error as e:
        errors.append(f"CSV parsing error: {str(e)}")
        return ParseResult(beneficiaries, errors, warnings)

    if len(rows) < 2:
        errors.append("CSV file must contain a header row and at least one data row")
        return ParseResult(beneficiaries, errors, warnings)

    headers = rows[0]
    mapping, missing = find_column_mapping(headers)

    if missing:
        errors.append(f"Missing required columns: {', '.join(missing)}")
        return ParseResult(beneficiaries, errors, warnings)

    for row_num, row in enumerate(rows[1:], start=2):
        if not any(cell.strip() for cell in row):
            continue  # Skip empty rows

        row_errors = []
        row_warnings = []

        def get_value(col: str) -> str:
            if col in mapping and mapping[col] < len(row):
                return row[mapping[col]].strip()
            return ''

        name = get_value('name')
        phone = get_value('phone')
        address = get_value('address')
        household_size = get_value('household_size')
        items_needed = get_value('items_needed')
        special_items = get_value('special_items')
        contact_preference = get_value('contact_preference')
        notes = get_value('notes')

        # Validate required fields
        if not name:
            row_errors.append("Missing name")
        if not phone:
            row_warnings.append("Missing phone number")
        if not address:
            row_errors.append("Missing address")
        if not household_size:
            row_warnings.append("Missing household size")
        if not items_needed:
            row_warnings.append("Missing items needed")

        beneficiary = Beneficiary(
            row_number=row_num,
            name=name,
            phone=phone,
            address=address,
            household_size=household_size,
            items_needed=items_needed,
            special_items=special_items,
            contact_preference=contact_preference,
            notes=notes,
            errors=row_errors,
            warnings=row_warnings,
            flagged=len(row_errors) > 0 or len(row_warnings) > 0
        )

        beneficiaries.append(beneficiary)

    return ParseResult(beneficiaries, errors, warnings)
