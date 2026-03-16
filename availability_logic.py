import uuid
from datetime import datetime, timedelta
import importlib.util
from pathlib import Path

# Dynamically load JSONDatabase from ITC-2205-PROJECT/db_handler.py (folder name contains hyphens)
_db_path = Path(__file__).parent / 'ITC-2205-PROJECT' / 'db_handler.py'
spec = importlib.util.spec_from_file_location('db_handler', str(_db_path))
db_mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(db_mod)
JSONDatabase = db_mod.JSONDatabase


DEFAULT_RESERVATION_DURATION_MIN = 120


def parse_datetime(date_str, time_str):
	"""Parse date and time strings into a datetime object.
	Expects date_str in YYYY-MM-DD and time_str in HH:MM (24h).
	"""
	return datetime.fromisoformat(f"{date_str}T{time_str}")


def _overlaps(start1, end1, start2, end2):
	return start1 < end2 and start2 < end1


def get_available_tables(db: JSONDatabase, date_str, time_str, duration_minutes=DEFAULT_RESERVATION_DURATION_MIN):
	start = parse_datetime(date_str, time_str)
	end = start + timedelta(minutes=duration_minutes)

	tables = db._read_data('tables')
	reservations = db._read_data('reservations')

	free_tables = []
	for table in tables:
		table_id = table['table_id']

		# If the table is occupied right now, skip it
		if table.get('status') == 'occupied':
			continue

		# Check any confirmed reservation that overlaps
		conflict = False
		for res in reservations:
			if res.get('table_id') != table_id:
				continue
			if res.get('status') in ('cancelled', 'completed'):
				continue

			try:
				res_start = parse_datetime(res['date'], res['time'])
			except Exception:
				# Skip malformed reservation
				continue
			res_end = res_start + timedelta(minutes=duration_minutes)
			if _overlaps(start, end, res_start, res_end):
				conflict = True
				break

		if not conflict:
			free_tables.append(table)

	return free_tables


def allocate_tables_for_party(available_tables, party_size):
	"""Return a list of table dicts whose combined capacity fits party_size.
	Strategy:
	- Prefer a single table with smallest sufficient capacity.
	- Otherwise greedily pick largest tables until enough seats.
	"""
	# Try single-table fit (choose smallest sufficient)
	sufficient = [t for t in available_tables if t['capacity'] >= party_size]
	if sufficient:
		chosen = min(sufficient, key=lambda t: t['capacity'])
		return [chosen]

	# Greedy: pick largest tables until sum >= party_size
	sorted_tables = sorted(available_tables, key=lambda t: t['capacity'], reverse=True)
	chosen = []
	total = 0
	for t in sorted_tables:
		chosen.append(t)
		total += t['capacity']
		if total >= party_size:
			return chosen

	# Not enough seats
	return []


from input_validation import validate_reservation_input

def reserve_tables(db: JSONDatabase, customer_id, date_str, time_str, party_size, duration_minutes=DEFAULT_RESERVATION_DURATION_MIN):
	# validate the input parameters first
	errors = validate_reservation_input(customer_id, date_str, time_str, party_size)
	if errors:
		# join multiple errors into a single message
		return {"error": "; ".join(errors)}

	# ensure party_size is an integer for internal computations
	try:
		party_size = int(party_size)
	except Exception:
		# this should not happen if validation passed, but be safe
		return {"error": "party_size must be an integer"}

	available = get_available_tables(db, date_str, time_str, duration_minutes)
	allocation = allocate_tables_for_party(available, party_size)
	if not allocation:
		return {"error": "No available table(s) for requested time and party size"}

	reservations = db._read_data('reservations')
	group_id = str(uuid.uuid4())
	created = []
	for table in allocation:
		new_res = {
			"reservation_id": str(uuid.uuid4()),
			"customer_id": customer_id,
			"table_id": table['table_id'],
			"date": date_str,
			"time": time_str,
			"party_size": party_size,
			"status": "confirmed",
			"group_id": group_id
		}
		reservations.append(new_res)
		created.append(new_res)
		# Mark table reserved in tables.json
		db.update_table_status(table['table_id'], 'reserved')

	db._write_data('reservations', reservations)
	return {"group_id": group_id, "reservations": created}


if __name__ == '__main__':
	# Simple demo when run directly
	db = JSONDatabase()

	# Create sample tables if none exist
	if not db._read_data('tables'):
		db.add_table(2)
		db.add_table(4)
		db.add_table(4)
		db.add_table(6)

	# Show available tables for a demo reservation
	today = datetime.now().date().isoformat()
	demo_time = (datetime.now() + timedelta(hours=2)).strftime('%H:%M')
	print('Checking availability for', today, demo_time)
	free = get_available_tables(db, today, demo_time)
	print('Free tables:', [(t['table_id'], t['capacity']) for t in free])

	# Try to reserve for party of 5
	result = reserve_tables(db, customer_id='guest', date_str=today, time_str=demo_time, party_size=5)
	print('Reserve result:', result)

