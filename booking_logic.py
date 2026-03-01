import json
import uuid
import random
import string
from datetime import datetime
from typing import Optional, List, Dict, Any


DB_DIR = "database"


def _load_json(path: str) -> List[Dict[str, Any]]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return []


def _save_json(path: str, data: List[Dict[str, Any]]):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def _generate_reservation_code(length: int = 6) -> str:
    return "RES-" + "".join(random.choices(string.ascii_uppercase + string.digits, k=length))


def _now_iso() -> str:
    return datetime.now().isoformat()


def find_available_tables(date: str, time: str, party_size: int,
                          tables_file: str = f"{DB_DIR}/tables.json",
                          reservations_file: str = f"{DB_DIR}/reservations.json") -> List[Dict[str, Any]]:
    """Return a list of tables that can seat `party_size` and are not reserved
    for the exact `date` and `time` specified. Date format: YYYY-MM-DD, time: HH:MM
    """
    tables = _load_json(tables_file)
    reservations = _load_json(reservations_file)

    # build set of table_ids already booked at that date/time
    booked_table_ids = set()
    for r in reservations:
        if r.get("date") == date and r.get("time") == time and r.get("status") == "confirmed":
            booked_table_ids.add(r.get("table_id"))

    available = [t for t in tables if t.get("capacity", 0) >= party_size and t.get("table_id") not in booked_table_ids]
    return available


def create_reservation(customer_id: Optional[str],
                       date: str,
                       time: str,
                       party_size: int,
                       table_id: Optional[str] = None,
                       contact: Optional[Dict[str, str]] = None,
                       special_requests: Optional[str] = None,
                       reservations_file: str = f"{DB_DIR}/reservations.json",
                       tables_file: str = f"{DB_DIR}/tables.json") -> Dict[str, Any]:
    """Create and persist a reservation. If `customer_id` is None, treats as guest booking
    Returns the reservation record including `reservation_code`.
    """
    # basic validation
    if party_size <= 0:
        raise ValueError("party_size must be positive")

    tables = _load_json(tables_file)
    reservations = _load_json(reservations_file)

    # If table_id provided, verify it's available
    if table_id:
        matching = [t for t in tables if t.get("table_id") == table_id]
        if not matching:
            raise ValueError("table_id not found")
        # check if already booked for that slot
        for r in reservations:
            if r.get("table_id") == table_id and r.get("date") == date and r.get("time") == time and r.get("status") == "confirmed":
                raise ValueError("table already reserved for that time")
    else:
        # choose first available table meeting capacity
        available = find_available_tables(date, time, party_size, tables_file=tables_file, reservations_file=reservations_file)
        if not available:
            raise ValueError("no available tables for the requested time/party size")
        table_id = available[0].get("table_id")

    reservation = {
        "reservation_id": str(uuid.uuid4()),
        "reservation_code": _generate_reservation_code(),
        "customer_id": customer_id,
        "table_id": table_id,
        "date": date,
        "time": time,
        "party_size": party_size,
        "contact": contact or {},
        "special_requests": special_requests or "",
        "status": "confirmed",
        "created_at": _now_iso(),
    }

    reservations.append(reservation)
    _save_json(reservations_file, reservations)

    return reservation


def find_reservation_by_code(reservation_code: str, reservations_file: str = f"{DB_DIR}/reservations.json") -> Optional[Dict[str, Any]]:
    reservations = _load_json(reservations_file)
    for r in reservations:
        if r.get("reservation_code") == reservation_code:
            return r
    return None


def modify_reservation(reservation_code: str,
                       new_date: Optional[str] = None,
                       new_time: Optional[str] = None,
                       new_party_size: Optional[int] = None,
                       new_table_id: Optional[str] = None,
                       reservations_file: str = f"{DB_DIR}/reservations.json",
                       tables_file: str = f"{DB_DIR}/tables.json") -> Dict[str, Any]:
    reservations = _load_json(reservations_file)
    tables = _load_json(tables_file)

    for idx, r in enumerate(reservations):
        if r.get("reservation_code") == reservation_code:
            # modify fields
            date = new_date or r.get("date")
            time = new_time or r.get("time")
            party_size = new_party_size or r.get("party_size")
            table_id = new_table_id or r.get("table_id")

            # validate table exists
            if table_id and not any(t.get("table_id") == table_id for t in tables):
                raise ValueError("table_id not found")

            # check conflicts
            for other in reservations:
                if other is r:
                    continue
                if other.get("table_id") == table_id and other.get("date") == date and other.get("time") == time and other.get("status") == "confirmed":
                    raise ValueError("requested table/date/time conflicts with another reservation")

            # apply
            r["date"] = date
            r["time"] = time
            r["party_size"] = party_size
            r["table_id"] = table_id
            r["modified_at"] = _now_iso()

            reservations[idx] = r
            _save_json(reservations_file, reservations)
            return r

    raise ValueError("reservation not found")


def cancel_reservation(reservation_code: str, reservations_file: str = f"{DB_DIR}/reservations.json") -> Dict[str, Any]:
    reservations = _load_json(reservations_file)
    for idx, r in enumerate(reservations):
        if r.get("reservation_code") == reservation_code:
            r["status"] = "cancelled"
            r["cancelled_at"] = _now_iso()
            reservations[idx] = r
            _save_json(reservations_file, reservations)
            return r
    raise ValueError("reservation not found")


def checkin_reservation(reservation_code: str, reservations_file: str = f"{DB_DIR}/reservations.json", tables_file: str = f"{DB_DIR}/tables.json") -> Dict[str, Any]:
    """Mark reservation as arrived/occupied and update table status to 'occupied'"""
    reservations = _load_json(reservations_file)
    tables = _load_json(tables_file)

    for ridx, r in enumerate(reservations):
        if r.get("reservation_code") == reservation_code:
            r["status"] = "occupied"
            r["checked_in_at"] = _now_iso()
            reservations[ridx] = r

            # update table status
            for tidx, t in enumerate(tables):
                if t.get("table_id") == r.get("table_id"):
                    t["status"] = "occupied"
                    t["last_updated"] = _now_iso()
                    tables[tidx] = t
                    break

            _save_json(reservations_file, reservations)
            _save_json(tables_file, tables)
            return r

    raise ValueError("reservation not found")


def complete_reservation(reservation_code: str, reservations_file: str = f"{DB_DIR}/reservations.json", tables_file: str = f"{DB_DIR}/tables.json") -> Dict[str, Any]:
    """Mark reservation as completed and free the table"""
    reservations = _load_json(reservations_file)
    tables = _load_json(tables_file)

    for ridx, r in enumerate(reservations):
        if r.get("reservation_code") == reservation_code:
            r["status"] = "completed"
            r["completed_at"] = _now_iso()
            reservations[ridx] = r

            # free table
            for tidx, t in enumerate(tables):
                if t.get("table_id") == r.get("table_id"):
                    t["status"] = "free"
                    t["last_updated"] = _now_iso()
                    tables[tidx] = t
                    break

            _save_json(reservations_file, reservations)
            _save_json(tables_file, tables)
            return r

    raise ValueError("reservation not found")


if __name__ == "__main__":
    # quick demo when run directly
    print("Booking logic demo")
    try:
        res = create_reservation(None, "2026-03-15", "19:00", 2, contact={"name": "Anna", "phone": "555-0100"}, special_requests="Vegetarian")
        print("Created:", res.get("reservation_code"))
    except Exception as e:
        print("Error creating reservation:", e)
