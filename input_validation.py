from datetime import datetime

DATE_FORMAT = "%Y-%m-%d"
TIME_FORMAT = "%H:%M"


def is_valid_date(date_str):
    """Return True if *date_str* follows YYYY-MM-DD and is a real date."""
    if not isinstance(date_str, str):
        return False
    try:
        datetime.strptime(date_str, DATE_FORMAT)
        return True
    except (ValueError, TypeError):
        return False


def is_valid_time(time_str):
    """Return True if *time_str* follows HH:MM 24‑hour format."""
    if not isinstance(time_str, str):
        return False
    try:
        datetime.strptime(time_str, TIME_FORMAT)
        return True
    except (ValueError, TypeError):
        return False


def is_valid_party_size(size):
    """Return True for positive integers (or string representation thereof)."""
    try:
        i = int(size)
        return i > 0
    except (ValueError, TypeError):
        return False


def validate_reservation_input(customer_id, date_str, time_str, party_size):
    """Perform a basic sanity check on reservation parameters.

    Returns a list of error messages.  An empty list means the inputs look ok.
    """
    errors = []

    if not customer_id or not isinstance(customer_id, str):
        errors.append("customer_id must be a non-empty string")

    if not is_valid_date(date_str):
        errors.append("date must be in YYYY-MM-DD format")

    if not is_valid_time(time_str):
        errors.append("time must be in HH:MM 24h format")

    if not is_valid_party_size(party_size):
        errors.append("party_size must be a positive integer")

    return errors


if __name__ == "__main__":
    # quick CLI for manual testing
    try:
        print("Reservation input validation demo\n")
        cust = input("Customer ID: ").strip()
        dat = input("Date (YYYY-MM-DD): ").strip()
        tim = input("Time (HH:MM): ").strip()
        size = input("Party size: ").strip()
        errs = validate_reservation_input(cust, dat, tim, size)
        if errs:
            print("\nErrors detected:")
            for e in errs:
                print(" -", e)
        else:
            print("\nAll inputs look good!")
    except KeyboardInterrupt:
        print("\nValidation interrupted by user")
    except Exception as e:
        print(f"Validation error: {str(e)}")
