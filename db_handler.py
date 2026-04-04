import json
import os
import re
import uuid
from datetime import datetime, timedelta
import hashlib
import secrets


DB_FOLDER = "database"
if not os.path.exists(DB_FOLDER):
    os.makedirs(DB_FOLDER)


class JSONDatabase:
    # Caption:
    # What: Centralize allowed enum-like values for roles and statuses.
    # How: Store each allowed set as a class-level constant.
    # Why: Prevent typos and keep validation rules consistent across methods.
    VALID_ROLES = {"customer", "employee", "owner"}
    VALID_TABLE_STATUSES = {"free", "reserved", "occupied"}
    VALID_ORDER_STATUSES = {"kitchen", "ready", "served", "paid"}
    INACTIVE_RESERVATION_STATUSES = {"canceled", "cancelled", "completed"}
    
    # Login security constants
    MAX_LOGIN_ATTEMPTS = 5
    LOGIN_LOCKOUT_DURATION = 900  # 15 minutes in seconds

    def __init__(self):
        # Caption:
        # What: Map each entity to its JSON storage file.
        # How: Build absolute paths from the shared database folder.
        # Why: Keep persistence paths centralized and easy to maintain.
        self.files = {
            "users": os.path.join(DB_FOLDER, "users.json"),
            "tables": os.path.join(DB_FOLDER, "tables.json"),
            "menu": os.path.join(DB_FOLDER, "menu.json"),
            "reservations": os.path.join(DB_FOLDER, "reservations.json"),
            "orders": os.path.join(DB_FOLDER, "orders.json"),
            "transactions": os.path.join(DB_FOLDER, "transactions.json"),
        }
        self._initialize_files()
        self._migrate_users_schema()

    def _initialize_files(self):
        # Caption:
        # What: Ensure all required JSON files exist.
        # How: Create missing files with an empty list.
        # Why: Avoid file-not-found crashes on first run.
        for file_path in self.files.values():
            if not os.path.exists(file_path):
                with open(file_path, "w", encoding="utf-8") as file:
                    json.dump([], file)

    def _migrate_users_schema(self):
        # Caption:
        # What: Backfill newly added user fields into older records.
        # How: Add missing secret-question keys and normalize legacy types.
        # Why: Keep existing accounts compatible after schema changes.
        users = self._read_data("users")
        changed = False
        for user in users:
            if "secret_question_number" not in user:
                user["secret_question_number"] = None
                changed = True
            elif isinstance(user.get("secret_question_number"), str):
                number = user["secret_question_number"].strip()
                if number.isdigit():
                    user["secret_question_number"] = int(number)
                    changed = True

            if "secret_question_answer" not in user:
                user["secret_question_answer"] = None
                changed = True

        if changed:
            self._write_data("users", users)

    def _read_data(self, entity_name):
        # Caption:
        # What: Read one entity list from its JSON file.
        # How: Parse JSON and return [] if file is missing/corrupted.
        # Why: Keep consumers resilient to empty or broken storage state.
        try:
            with open(self.files[entity_name], "r", encoding="utf-8") as file:
                return json.load(file)
        except (FileNotFoundError, json.JSONDecodeError):
            return []

    def _write_data(self, entity_name, data):
        # Caption:
        # What: Persist one entity list to disk.
        # How: Serialize with indentation for readability.
        # Why: Provide a single write path and predictable file format.
        with open(self.files[entity_name], "w", encoding="utf-8") as file:
            json.dump(data, file, indent=4)

    def _find_by_id(self, entity_name, id_field, entity_id):
        # Caption:
        # What: Locate a single record by ID.
        # How: Iterate through loaded data and compare the ID field.
        # Why: Reuse lookup logic across validation-heavy workflows.
        data = self._read_data(entity_name)
        for row in data:
            if row.get(id_field) == entity_id:
                return row
        return None

    def _find_user_by_identifier(self, identifier, users=None):
        # Caption:
        # What: Resolve a user by username, email, or phone.
        # How: Normalize the identifier and compare it against each login field.
        # Why: Multiple auth features need one shared lookup path.
        if not self._is_non_empty_text(identifier):
            return None

        identifier = identifier.strip()
        lowered_identifier = identifier.lower()
        users = users if users is not None else self._read_data("users")

        for user in users:
            matches_identifier = (
                user.get("username", "").lower() == lowered_identifier
                or user.get("email", "").lower() == lowered_identifier
                or user.get("phone", "").strip() == identifier
            )
            if matches_identifier:
                return user
        return None

    @staticmethod
    def _is_non_empty_text(value):
        # Caption:
        # What: Validate that input is non-empty text.
        # How: Check type string and trim whitespace.
        # Why: Block blank textual fields early.
        return isinstance(value, str) and value.strip() != ""

    @staticmethod
    def _is_positive_int(value):
        # Caption:
        # What: Validate positive integer values from multiple input types.
        # How: Accept int/float-int/string-int and reject bool/zero/negative.
        # Why: Console input often arrives as strings and needs normalization.
        if isinstance(value, bool):
            return False
        if isinstance(value, int):
            return value > 0
        if isinstance(value, float):
            return value.is_integer() and value > 0
        if isinstance(value, str):
            return bool(re.fullmatch(r"[1-9]\d*", value.strip()))
        return False

    @staticmethod
    def _is_positive_number(value):
        # Caption:
        # What: Validate positive numeric values.
        # How: Convert to float safely and check greater than zero.
        # Why: Pricing and payments require strict positive amounts.
        if isinstance(value, bool):
            return False
        try:
            return float(value) > 0
        except (TypeError, ValueError):
            return False

    @staticmethod
    def _is_valid_date(date_str):
        # Caption:
        # What: Validate reservation date format.
        # How: Parse with YYYY-MM-DD via datetime.strptime.
        # Why: Keep dates consistent for comparisons and conflict checks.
        if not isinstance(date_str, str):
            return False
        try:
            datetime.strptime(date_str, "%Y-%m-%d")
            return True
        except ValueError:
            return False

    @staticmethod
    def _is_valid_time(time_str):
        # Caption:
        # What: Validate reservation time format.
        # How: Parse with HH:MM 24-hour format.
        # Why: Prevent malformed times from breaking slot logic.
        if not isinstance(time_str, str):
            return False
        try:
            datetime.strptime(time_str, "%H:%M")
            return True
        except ValueError:
            return False

    @staticmethod
    def _is_valid_phone(phone):
        # Caption:
        # What: Validate user phone syntax.
        # How: Use regex with allowed characters and length range.
        # Why: Prevent unusable or invalid contact values.
        if not isinstance(phone, str):
            return False
        return bool(re.fullmatch(r"[0-9+()\- ]{7,20}", phone.strip()))

    @staticmethod
    def _normalize_secret_answer(answer):
        # Caption:
        # What: Canonicalize secret-question answers before hashing/comparing.
        # How: Trim, lowercase, and collapse repeated internal whitespace.
        # Why: Minor typing differences should not lock users out of recovery.
        if not isinstance(answer, str):
            return ""
        return " ".join(answer.strip().lower().split())

    @staticmethod
    def hash_password(password, salt=None):
        # Caption:
        # What: Hash a password using SHA256 with a random salt.
        # How: Generate a random salt if not provided, concatenate with password,
        #      then hash with SHA256 and return salt:hash format.
        # Why: Store passwords securely and prevent rainbow table attacks.
        if salt is None:
            salt = secrets.token_hex(32)  # 64-character hex string
        salted_password = salt + password
        hashed = hashlib.sha256(salted_password.encode()).hexdigest()
        return f"{salt}:{hashed}"
    
    @staticmethod
    def verify_password(stored_hash, password):
        # Caption:
        # What: Verify a plaintext password against a stored hash.
        # How: Extract salt from stored_hash, hash the provided password with it,
        #      and compare the result.
        # Why: Allow users to log in by comparing their input to stored credentials.
        try:
            salt, stored_hashed = stored_hash.split(":")
            new_hash = JSONDatabase.hash_password(password, salt)
            return new_hash == stored_hash
        except (ValueError, AttributeError):
            return False
    
    def is_account_locked(self, username):
        # Caption:
        # What: Check if an account is locked due to failed login attempts.
        # How: Retrieve login_attempts record and check if timeout has expired.
        # Why: Prevent brute force attacks by temporarily locking accounts.
        users = self._read_data("users")
        for user in users:
            if user.get("username", "").lower() == username.lower():
                if user.get("login_attempts", 0) >= self.MAX_LOGIN_ATTEMPTS:
                    lockout_time = user.get("lockout_until")
                    if lockout_time:
                        lockout_dt = datetime.fromisoformat(lockout_time)
                        if datetime.now() < lockout_dt:
                            return True
                        else:
                            # Unlock the account
                            user["login_attempts"] = 0
                            user["lockout_until"] = None
                            self._write_data("users", users)
                            return False
                return False
        return False
    
    def record_failed_login(self, username):
        # Caption:
        # What: Increment failed login counter and lock account if necessary.
        # How: Find user, increment attempts, set lockout time when max reached.
        # Why: Track failed attempts for security monitoring and account protection.
        users = self._read_data("users")
        for user in users:
            if user.get("username", "").lower() == username.lower():
                user["login_attempts"] = user.get("login_attempts", 0) + 1
                if user["login_attempts"] >= self.MAX_LOGIN_ATTEMPTS:
                    lockout_until = datetime.now() + timedelta(seconds=self.LOGIN_LOCKOUT_DURATION)
                    user["lockout_until"] = lockout_until.isoformat()
                self._write_data("users", users)
                return
    
    def reset_login_attempts(self, username):
        # Caption:
        # What: Clear failed login counters after successful login.
        # How: Find user, reset attempts and lockout_until fields.
        # Why: Allow users to retry after successful authentication.
        users = self._read_data("users")
        for user in users:
            if user.get("username", "").lower() == username.lower():
                user["login_attempts"] = 0
                user["lockout_until"] = None
                self._write_data("users", users)
                return

    @staticmethod
    def _is_valid_email(email):
        # Caption:
        # What: Validate email syntax for account-based login.
        # How: Use a simple regex that enforces local-part@domain format.
        # Why: Email login only works reliably if stored values are structured.
        if not isinstance(email, str):
            return False
        return bool(re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email.strip()))

    def _has_reservation_conflict(self, table_id, date_str, time_str, exclude_id=None):
        # Caption:
        # What: Detect table collisions for a date/time slot.
        # How: Compare active reservations and optionally ignore one ID.
        # Why: Required for create and modify reservation safety.
        reservations = self._read_data("reservations")
        for reservation in reservations:
            if reservation.get("status") in self.INACTIVE_RESERVATION_STATUSES:
                continue
            if exclude_id is not None and reservation.get("reservation_id") == exclude_id:
                continue
            same_slot = (
                reservation.get("table_id") == table_id
                and reservation.get("date") == date_str
                and reservation.get("time") == time_str
            )
            if same_slot:
                return True
        return False

    def create_user(
        self,
        username,
        password,
        role,
        full_name,
        phone,
        email="",
        secret_question_number=None,
        secret_question_answer=None,
    ):
        # Caption:
        # What: Create a user with validated account/contact data.
        # How: Validate fields, normalize values, enforce unique login identifiers.
        # Why: Registration must reject duplicate usernames, phones, and emails.
        if not self._is_non_empty_text(username):
            return {"error": "Username must be a non-empty string"}
        if not self._is_non_empty_text(password):
            return {"error": "Password must be a non-empty string"}
        if role not in self.VALID_ROLES:
            return {"error": "Role must be customer, employee, or owner"}
        if not self._is_non_empty_text(full_name):
            return {"error": "Full name must be a non-empty string"}
        if not self._is_valid_phone(phone):
            return {"error": "Phone must be 7-20 chars and contain only digits/+()-"}
        if email and not self._is_valid_email(email):
            return {"error": "Email must be in a valid format"}
        if not self._is_positive_int(secret_question_number):
            return {"error": "Secret question selection is required"}
        if not self._is_non_empty_text(secret_question_answer):
            return {"error": "Secret question answer must be a non-empty string"}

        username = username.strip()
        full_name = full_name.strip()
        phone = phone.strip()
        email = email.strip().lower()
        secret_question_number = int(secret_question_number)
        normalized_secret_answer = self._normalize_secret_answer(secret_question_answer)

        users = self._read_data("users")
        if any(user.get("username", "").lower() == username.lower() for user in users):
            return {"error": "Username already exists"}
        if any(user.get("phone", "").strip() == phone for user in users):
            return {"error": "Phone already exists"}
        if email and any(user.get("email", "").lower() == email for user in users):
            return {"error": "Email already exists"}

        new_user = {
            "user_id": str(uuid.uuid4()),
            "username": username,
            "password": self.hash_password(password),
            "role": role,
            "full_name": full_name,
            "phone": phone,
            "email": email,
            "secret_question_number": secret_question_number,
            "secret_question_answer": self.hash_password(normalized_secret_answer),
            "login_attempts": 0,
            "lockout_until": None,
        }
        users.append(new_user)
        self._write_data("users", users)
        return new_user

    def get_user_by_identifier(self, identifier):
        # Caption:
        # What: Expose flexible account lookup to higher-level auth flows.
        # How: Reuse the shared identifier matcher.
        # Why: Recovery and login screens need the same account resolution logic.
        return self._find_user_by_identifier(identifier)

    def authenticate_user(self, identifier, password):
        # Caption:
        # What: Authenticate a user by username, email, or phone with login attempt limits.
        # How: Check if account is locked, verify password hash, update attempt counters.
        # Why: The feature list requires flexible login with security against brute force.
        if not self._is_non_empty_text(identifier):
            return None

        users = self._read_data("users")
        user = self._find_user_by_identifier(identifier, users)
        if user is None:
            return None

        username = user.get("username", "")

        # Check if account is locked
        if self.is_account_locked(username):
            return None

        # Verify hashed password
        if self.verify_password(user.get("password", ""), password):
            self.reset_login_attempts(username)
            return user

        # Record failed attempt
        self.record_failed_login(username)
        return None

    def verify_secret_question_answer(self, identifier, secret_answer):
        # Caption:
        # What: Verify a recovery answer against the stored hashed value.
        # How: Find the account, normalize the answer, then compare via hash helper.
        # Why: Password recovery must validate answers without storing them in plain text.
        if not self._is_non_empty_text(secret_answer):
            return {"error": "Secret question answer must be a non-empty string"}

        users = self._read_data("users")
        user = self._find_user_by_identifier(identifier, users)
        if user is None:
            return {"error": "Account not found"}

        if not user.get("secret_question_answer") or not user.get("secret_question_number"):
            return {"error": "This account does not have password recovery set up"}

        normalized_secret_answer = self._normalize_secret_answer(secret_answer)
        if not self.verify_password(user.get("secret_question_answer", ""), normalized_secret_answer):
            return {"error": "Incorrect answer to the secret question"}

        return user

    def update_user_password(self, identifier, new_password):
        # Caption:
        # What: Replace a user's password after a verified reset flow.
        # How: Resolve the account, hash the new password, and clear lockout state.
        # Why: Password resets should restore normal login access immediately.
        if not self._is_non_empty_text(new_password):
            return {"error": "Password must be a non-empty string"}

        users = self._read_data("users")
        user = self._find_user_by_identifier(identifier, users)
        if user is None:
            return {"error": "Account not found"}

        user["password"] = self.hash_password(new_password)
        user["login_attempts"] = 0
        user["lockout_until"] = None
        self._write_data("users", users)
        return user

    def add_table(self, capacity):
        # Caption:
        # What: Create a new table record.
        # How: Validate capacity as positive integer before storing.
        # Why: Prevent impossible or broken capacity values in seating logic.
        if not self._is_positive_int(capacity):
            return {"error": "Capacity must be a positive integer"}

        new_table = {
            "table_id": str(uuid.uuid4()),
            "capacity": int(capacity),
            "status": "free",
        }
        tables = self._read_data("tables")
        tables.append(new_table)
        self._write_data("tables", tables)
        return new_table

    def update_table_status(self, table_id, new_status):
        # Caption:
        # What: Update table availability state.
        # How: Allow only predefined status values and persist update.
        # Why: Keep table state machine constrained and predictable.
        if new_status not in self.VALID_TABLE_STATUSES:
            return False

        tables = self._read_data("tables")
        for table in tables:
            if table.get("table_id") == table_id:
                table["status"] = new_status
                self._write_data("tables", tables)
                return True
        return False

    def add_menu_item(self, name, category, price):
        # Caption:
        # What: Add a menu item with validation.
        # How: Validate text fields and positive price, then round amount.
        # Why: Ensure order pricing uses clean, valid menu data.
        if not self._is_non_empty_text(name):
            return {"error": "Menu item name must be a non-empty string"}
        if not self._is_non_empty_text(category):
            return {"error": "Menu item category must be a non-empty string"}
        if not self._is_positive_number(price):
            return {"error": "Price must be a positive number"}

        new_item = {
            "item_id": str(uuid.uuid4()),
            "name": name.strip(),
            "category": category.strip(),
            "price": round(float(price), 2),
            "is_available": True,
        }
        menu = self._read_data("menu")
        menu.append(new_item)
        self._write_data("menu", menu)
        return new_item

    def create_reservation(self, customer_id, table_id, date_str, time_str, party_size):
        # Caption:
        # What: Create a reservation with strict booking checks.
        # How: Verify user/table existence, date/time format, size, and conflicts.
        # Why: Prevent overbooking and invalid reservations at creation time.
        if self._find_by_id("users", "user_id", customer_id) is None:
            return {"error": "Customer does not exist"}
        table = self._find_by_id("tables", "table_id", table_id)
        if table is None:
            return {"error": "Table does not exist"}
        if not self._is_valid_date(date_str):
            return {"error": "Date must be in YYYY-MM-DD format"}
        if not self._is_valid_time(time_str):
            return {"error": "Time must be in HH:MM (24h) format"}
        if not self._is_positive_int(party_size):
            return {"error": "Party size must be a positive integer"}

        party_size = int(party_size)
        if party_size > int(table.get("capacity", 0)):
            return {"error": "Party size exceeds table capacity"}
        if self._has_reservation_conflict(table_id, date_str, time_str):
            return {"error": "Table is already reserved for this date and time"}

        new_reservation = {
            "reservation_id": str(uuid.uuid4()),
            "customer_id": customer_id,
            "table_id": table_id,
            "date": date_str,
            "time": time_str,
            "party_size": party_size,
            "status": "confirmed",
        }
        reservations = self._read_data("reservations")
        reservations.append(new_reservation)
        self._write_data("reservations", reservations)
        return new_reservation

    def modify_reservation(
        self,
        reservation_id,
        date_str=None,
        time_str=None,
        party_size=None,
        table_id=None,
    ):
        # Caption:
        # What: Modify reservation fields (date/time/party size/table).
        # How: Merge new inputs with current values, revalidate, recheck conflicts.
        # Why: Support week-5 change requests without corrupting booking integrity.
        reservations = self._read_data("reservations")
        target = None
        for reservation in reservations:
            if reservation.get("reservation_id") == reservation_id:
                target = reservation
                break

        if target is None:
            return {"error": "Reservation not found"}
        if target.get("status") in self.INACTIVE_RESERVATION_STATUSES:
            return {"error": "Canceled reservations cannot be modified"}

        new_table_id = table_id if table_id is not None else target["table_id"]
        new_date = date_str if date_str is not None else target["date"]
        new_time = time_str if time_str is not None else target["time"]
        new_party_size = party_size if party_size is not None else target["party_size"]

        table = self._find_by_id("tables", "table_id", new_table_id)
        if table is None:
            return {"error": "Table does not exist"}
        if not self._is_valid_date(new_date):
            return {"error": "Date must be in YYYY-MM-DD format"}
        if not self._is_valid_time(new_time):
            return {"error": "Time must be in HH:MM (24h) format"}
        if not self._is_positive_int(new_party_size):
            return {"error": "Party size must be a positive integer"}

        new_party_size = int(new_party_size)
        if new_party_size > int(table.get("capacity", 0)):
            return {"error": "Party size exceeds table capacity"}
        if self._has_reservation_conflict(
            new_table_id,
            new_date,
            new_time,
            exclude_id=reservation_id,
        ):
            return {"error": "Table is already reserved for this date and time"}

        target["table_id"] = new_table_id
        target["date"] = new_date
        target["time"] = new_time
        target["party_size"] = new_party_size
        target["status"] = "modified"

        self._write_data("reservations", reservations)
        return target

    def cancel_reservation(self, reservation_id):
        # Caption:
        # What: Cancel an existing reservation.
        # How: Mark status as canceled and store cancellation timestamp.
        # Why: Preserve booking history while removing it from active scheduling.
        reservations = self._read_data("reservations")
        for reservation in reservations:
            if reservation.get("reservation_id") == reservation_id:
                if reservation.get("status") in self.INACTIVE_RESERVATION_STATUSES:
                    return {"error": "Reservation is already canceled"}
                reservation["status"] = "canceled"
                reservation["canceled_at"] = datetime.now().isoformat()
                self._write_data("reservations", reservations)
                return reservation
        return {"error": "Reservation not found"}

    def create_order(self, table_id, customer_id, items_list):
        # Caption:
        # What: Create an order tied to an existing customer and table.
        # How: Validate references/items and compute total via menu lookup.
        # Why: Block orphan orders and incorrect totals from invalid item input.
        if self._find_by_id("tables", "table_id", table_id) is None:
            return {"error": "Table does not exist"}
        if self._find_by_id("users", "user_id", customer_id) is None:
            return {"error": "Customer does not exist"}
        if not isinstance(items_list, list) or len(items_list) == 0:
            return {"error": "Items list must be a non-empty list"}

        menu = self._read_data("menu")
        menu_map = {item["item_id"]: item for item in menu}

        total_amount = 0.0
        for order_item in items_list:
            item_id = order_item.get("item_id")
            quantity = order_item.get("quantity")

            if item_id not in menu_map:
                return {"error": f"Menu item {item_id} does not exist"}
            if not self._is_positive_int(quantity):
                return {"error": "Item quantity must be a positive integer"}
            total_amount += menu_map[item_id]["price"] * int(quantity)

        new_order = {
            "order_id": str(uuid.uuid4()),
            "table_id": table_id,
            "customer_id": customer_id,
            "order_status": "kitchen",
            "items": items_list,
            "total_amount": round(total_amount, 2),
        }
        orders = self._read_data("orders")
        orders.append(new_order)
        self._write_data("orders", orders)
        return new_order

    def update_order_status(self, order_id, status):
        # Caption:
        # What: Update the lifecycle state of an order.
        # How: Enforce allowed statuses and persist when order exists.
        # Why: Keep order workflow transitions valid.
        if status not in self.VALID_ORDER_STATUSES:
            return False

        orders = self._read_data("orders")
        for order in orders:
            if order.get("order_id") == order_id:
                order["order_status"] = status
                self._write_data("orders", orders)
                return True
        return False

    def process_payment(self, order_id, amount, method):
        # Caption:
        # What: Record a payment transaction for an order.
        # How: Validate order and payment data, save transaction, set order to paid.
        # Why: Ensure financial records are valid and synchronized with order state.
        if self._find_by_id("orders", "order_id", order_id) is None:
            return {"error": "Order does not exist"}
        if not self._is_positive_number(amount):
            return {"error": "Payment amount must be a positive number"}
        if not self._is_non_empty_text(method):
            return {"error": "Payment method must be a non-empty string"}

        new_transaction = {
            "transaction_id": str(uuid.uuid4()),
            "order_id": order_id,
            "amount_paid": round(float(amount), 2),
            "payment_method": method.strip(),
            "timestamp": datetime.now().isoformat(),
        }
        transactions = self._read_data("transactions")
        transactions.append(new_transaction)
        self._write_data("transactions", transactions)

        self.update_order_status(order_id, "paid")
        return new_transaction
