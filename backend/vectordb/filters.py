import re


def sanitize_metadata_value(value: str) -> str:
    """Sanitize metadata values by keeping only alphanumeric, dot, underscore, hyphen, and spaces.

    Trims leading and trailing whitespace. Returns an empty string if the value is empty or invalid.
    """
    if not value:
        return ""
    # Remove any characters that are NOT alphanumeric, dot, underscore, hyphen, or whitespace
    return re.sub(r"[^A-Za-z0-9._\s-]", "", value).strip()


def build_scalar_filter(manufacturer: str | None, equipment: str | None) -> str | None:
    """Build a Milvus-safe query expression string for manufacturer and/or equipment.

    Discards 'unknown' (case-insensitive) values, sanitizes input strings, lowercases the values,
    and returns a conjunction (and) string, or None if no valid filters are provided.
    """
    filters = []

    if manufacturer:
        mfr_cleaned = sanitize_metadata_value(manufacturer)
        if mfr_cleaned and mfr_cleaned.lower() != "unknown":
            filters.append(f'manufacturer == "{mfr_cleaned.lower()}"')

    if equipment:
        equip_cleaned = sanitize_metadata_value(equipment)
        if equip_cleaned and equip_cleaned.lower() != "unknown":
            filters.append(f'equipment == "{equip_cleaned.lower()}"')

    if filters:
        return " and ".join(filters)

    return None
