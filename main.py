import os
from getpass import getpass

from auth_system import login_account, register_account
from availability_logic import get_available_tables
from booking_logic import checkin_reservation, complete_reservation, create_reservation
from db_handler import JSONDatabase
from input_validation import is_valid_date, is_valid_time, validate_reservation_input


SAMPLE_TABLES = (2, 2, 4, 4, 6, 8)
SAMPLE_MENU = (
    ("Greek Salad", "Starter", 7.50),
    ("Bruschetta", "Starter", 6.00),
    ("Margherita Pizza", "Main", 11.50),
    ("Chicken Pasta", "Main", 13.00),
    ("Cheeseburger", "Main", 12.00),
    ("Lemonade", "Drink", 3.50),
)
INACTIVE_RESERVATION_STATUSES = {"canceled", "cancelled", "completed"}


def short_id(value):
    return value[:8] if isinstance(value, str) else "-"


def print_heading(title):
    print(f"\n{title}")
    print("-" * len(title))


def clear_screen():
    os.system("cls" if os.name == "nt" else "clear")


def pause_screen(message="Press Enter to continue: "):
    input(message)


def input_with_default(label, default=""):
    suffix = f" [{default}]" if default else ""
    value = input(f"{label}{suffix}: ").strip()
    return value or default


def input_number_part(label, default="", minimum=None, maximum=None):
    while True:
        suffix = f" [{default}]" if default else ""
        print(label)
        value = input(f"Value{suffix}: ").strip()
        value = value or default
        if not value:
            print(f"{label} is required.")
            continue
        if not value.isdigit():
            print(f"{label} must be a number.")
            continue

        number = int(value)
        if minimum is not None and number < minimum:
            print(f"{label} must be at least {minimum}.")
            continue
        if maximum is not None and number > maximum:
            print(f"{label} must be at most {maximum}.")
            continue
        return number


def split_date_parts(date_str):
    parts = {"month": "", "day": "", "year": ""}
    if not isinstance(date_str, str):
        return parts

    pieces = date_str.split("-")
    if len(pieces) != 3:
        return parts

    year, month, day = pieces
    parts["month"] = str(int(month)) if month.isdigit() else ""
    parts["day"] = str(int(day)) if day.isdigit() else ""
    parts["year"] = str(int(year)) if year.isdigit() else ""
    return parts


def split_time_parts(time_str):
    parts = {"hour": "", "minute": ""}
    if not isinstance(time_str, str):
        return parts

    pieces = time_str.split(":")
    if len(pieces) != 2:
        return parts

    hour, minute = pieces
    parts["hour"] = str(int(hour)) if hour.isdigit() else ""
    parts["minute"] = str(int(minute)) if minute.isdigit() else ""
    return parts


def prompt_date_value(default=""):
    parts = split_date_parts(default)

    while True:
        print("Date")
        print("Enter the reservation date one part at a time.")
        month = input_number_part("Month (1-12)", parts["month"], 1, 12)
        day = input_number_part("Day (1-31)", parts["day"], 1, 31)
        year = input_number_part("Year (YYYY)", parts["year"], 1, 9999)
        date_value = f"{year:04d}-{month:02d}-{day:02d}"
        if is_valid_date(date_value):
            return date_value

        print("That date does not exist. Try again.")
        parts = {"month": str(month), "day": str(day), "year": str(year)}


def prompt_time_value(default=""):
    parts = split_time_parts(default)

    while True:
        print("Time")
        print("Enter the reservation time one part at a time.")
        hour = input_number_part("Hour (0-23)", parts["hour"], 0, 23)
        minute = input_number_part("Minute (0-59)", parts["minute"], 0, 59)
        time_value = f"{hour:02d}:{minute:02d}"
        if is_valid_time(time_value):
            return time_value

        print("That time is invalid. Try again.")
        parts = {"hour": str(hour), "minute": str(minute)}
        

def prompt_new_date_value(default=""):
    print("Press Enter to keep the current date part.")
    return prompt_date_value(default)


def prompt_new_time_value(default=""):
    print("Press Enter to keep the current time part.")
    return prompt_time_value(default)


def input_role(default="customer"):
    while True:
        role_value = input_with_default("Role [customer/employee/owner]", default).lower()
        if role_value in JSONDatabase.VALID_ROLES:
            return role_value
        print("Invalid role. Choose customer, employee, or owner.")


def seed_demo_data(db):
    seeded = []

    if not db._read_data("tables"):
        for capacity in SAMPLE_TABLES:
            db.add_table(capacity)
        seeded.append("tables")

    if not db._read_data("menu"):
        for name, category, price in SAMPLE_MENU:
            db.add_menu_item(name, category, price)
        seeded.append("menu")

    return seeded


def choose_from_list(items, title, formatter):
    if not items:
        print(f"No {title.lower()} available.")
        pause_screen()
        return None

    while True:
        clear_screen()
        print_heading(title)
        for index, item in enumerate(items, start=1):
            print(f"{index}. {formatter(item)}")

        choice = input("Choose an option (Enter to cancel): ").strip()
        if not choice:
            return None
        if not choice.isdigit():
            print("Invalid selection. Try again.")
            continue

        choice_index = int(choice) - 1
        if choice_index < 0 or choice_index >= len(items):
            print("Invalid selection. Try again.")
            continue

        return items[choice_index]


def show_menu_items(db):
    clear_screen()
    menu = db._read_data("menu")
    if not menu:
        print("No menu items available.")
        return []

    print_heading("Menu")
    for index, item in enumerate(menu, start=1):
        print(
            f"{index}. {item['name']} | {item['category']} | "
            f"EUR {float(item['price']):.2f}"
        )
    return menu


def prompt_menu_and_order(db, user=None):
    menu = show_menu_items(db)
    if not menu:
        return

    if user is None:
        input("Press Enter to go back: ")
        return

    while True:
        choice = input("Type 1 to order from this menu or press Enter to go back: ").strip()
        if not choice:
            return
        if choice == "1":
            prompt_place_order(db, user, menu=menu)
            return
        print("Invalid option. Try again.")


def get_user_reservations(db, user_id):
    reservations = [
        reservation
        for reservation in db._read_data("reservations")
        if reservation.get("customer_id") == user_id
    ]
    reservations.sort(key=lambda row: (row.get("date", ""), row.get("time", "")))
    return reservations


def get_active_user_reservations(db, user_id):
    return [
        reservation
        for reservation in get_user_reservations(db, user_id)
        if reservation.get("status") not in INACTIVE_RESERVATION_STATUSES
    ]


def format_reservation(reservation):
    code = reservation.get("reservation_code", short_id(reservation.get("reservation_id")))
    return (
        f"{code} | {reservation.get('date')} {reservation.get('time')} | "
        f"party {reservation.get('party_size')} | "
        f"table {short_id(reservation.get('table_id'))} | "
        f"status {reservation.get('status')}"
    )


def show_user_reservations(db, user):
    clear_screen()
    reservations = get_user_reservations(db, user["user_id"])
    if not reservations:
        print("You do not have any reservations.")
        return []

    print_heading("My Reservations")
    for reservation in reservations:
        print(format_reservation(reservation))
    return reservations


def show_all_reservations(db):
    clear_screen()
    reservations = db._read_data("reservations")
    if not reservations:
        print("No reservations found.")
        return []

    reservations.sort(key=lambda row: (row.get("date", ""), row.get("time", "")))
    print_heading("All Reservations")
    for reservation in reservations:
        customer = reservation.get("customer_id") or "guest"
        print(f"{format_reservation(reservation)} | customer {short_id(customer)}")
    return reservations


def parse_order_request(raw_value, menu):
    items = []
    chunks = [chunk.strip() for chunk in raw_value.split(",") if chunk.strip()]
    if not chunks:
        raise ValueError("Enter at least one menu item.")

    for chunk in chunks:
        if ":" in chunk:
            item_part, quantity_part = chunk.split(":", 1)
        else:
            item_part, quantity_part = chunk, "1"

        if not item_part.strip().isdigit() or not quantity_part.strip().isdigit():
            raise ValueError("Use item_number[:quantity], for example 1:2,3.")

        item_index = int(item_part.strip()) - 1
        quantity = int(quantity_part.strip())

        if item_index < 0 or item_index >= len(menu) or quantity <= 0:
            raise ValueError("Order selection is out of range.")

        items.append(
            {
                "item_id": menu[item_index]["item_id"],
                "quantity": quantity,
                "special_notes": "",
            }
        )

    return items


def prompt_registration(db):
    clear_screen()
    print_heading("Register")
    state = {
        "username": "",
        "full_name": "",
        "phone": "",
        "email": "",
        "role": "customer",
        "password": "",
        "confirm_password": "",
    }

    def collect_registration_fields(field_names):
        for field_name in field_names:
            if field_name == "username":
                state["username"] = input_with_default("Username", state["username"])
            elif field_name == "full_name":
                state["full_name"] = input_with_default("Full name", state["full_name"])
            elif field_name == "phone":
                state["phone"] = input_with_default("Phone", state["phone"])
            elif field_name == "email":
                state["email"] = input_with_default("Email (optional)", state["email"])
            elif field_name == "role":
                state["role"] = input_role(state["role"])
            elif field_name == "password":
                state["password"] = getpass("Password: ")
            elif field_name == "confirm_password":
                state["confirm_password"] = getpass("Confirm password: ")

    def fields_from_registration_error(message):
        if message == "Passwords do not match":
            return ["password", "confirm_password"]
        if message == "Password must be at least 6 characters long":
            return ["password", "confirm_password"]
        if "Username" in message:
            return ["username"]
        if "Full name" in message:
            return ["full_name"]
        if "Phone" in message:
            return ["phone"]
        if "Email" in message:
            return ["email"]
        if "Role" in message:
            return ["role"]
        return ["username", "full_name", "phone", "email", "role", "password", "confirm_password"]

    collect_registration_fields(
        ["username", "full_name", "phone", "email", "role", "password", "confirm_password"]
    )

    while True:
        result = register_account(
            db=db,
            username=state["username"],
            password=state["password"],
            confirm_password=state["confirm_password"],
            full_name=state["full_name"],
            phone=state["phone"],
            email=state["email"],
            role=state["role"],
        )
        print(result["message"])
        if result["success"]:
            pause_screen()
            return result
        collect_registration_fields(fields_from_registration_error(result["message"]))


def prompt_login(db):
    clear_screen()
    print_heading("Login")
    identifier = input("Username, email, or phone: ").strip()
    if not identifier:
        print("Login canceled.")
        return None

    while True:
        password = getpass("Password: ")
        if not password:
            print("Password is required. Try again.")
            continue

        result = login_account(db, identifier, password)
        print(result["message"])
        if result["success"]:
            return result.get("user")

        retry = input(
            "Press Enter to retry the password, type 1 to change account, or 0 to cancel: "
        ).strip()
        if retry == "0":
            return None
        if retry == "1":
            identifier = input("Username, email, or phone: ").strip()
            if not identifier:
                print("Login canceled.")
                return None


def prompt_reservation(db, customer_id=None):
    clear_screen()
    print_heading("Create Reservation")
    state = {
        "date": "",
        "time": "",
        "party_size": "",
        "guest_name": "",
        "guest_phone": "",
        "special_requests": "",
    }

    while True:
        state["date"] = prompt_date_value(state["date"])
        state["time"] = prompt_time_value(state["time"])
        state["party_size"] = input_with_default("Party size", state["party_size"])

        validation_id = customer_id or "guest"
        errors = validate_reservation_input(
            validation_id,
            state["date"],
            state["time"],
            state["party_size"],
        )
        if errors:
            print("Reservation failed:")
            for error in errors:
                print(f"- {error}")
            continue

        party_size = int(state["party_size"])
        tables = [
            table
            for table in get_available_tables(db, state["date"], state["time"])
            if table.get("capacity", 0) >= party_size
        ]
        selected_table = choose_from_list(
            tables,
            "Available Tables",
            lambda table: (
                f"Table {short_id(table.get('table_id'))} | "
                f"capacity {table.get('capacity')} | status {table.get('status')}"
            ),
        )
        if selected_table is None:
            return

        contact = {}
        if customer_id is None:
            state["guest_name"] = input_with_default("Guest name", state["guest_name"])
            state["guest_phone"] = input_with_default("Guest phone", state["guest_phone"])
            if not state["guest_name"] or not state["guest_phone"]:
                print("Guest name and phone are required.")
                continue
            contact = {"name": state["guest_name"], "phone": state["guest_phone"]}

        state["special_requests"] = input_with_default(
            "Special requests (optional)",
            state["special_requests"],
        )

        try:
            reservation = create_reservation(
                customer_id=customer_id,
                date=state["date"],
                time=state["time"],
                party_size=party_size,
                table_id=selected_table["table_id"],
                contact=contact,
                special_requests=state["special_requests"],
            )
        except Exception as exc:
            print(f"Reservation failed: {exc}")
            continue

        print("Reservation created successfully.")
        print(
            f"Reservation confirmed for {state['date']} at {state['time']} "
            f"for {party_size} guest(s)."
        )
        print(f"Reservation code: {reservation.get('reservation_code', '-')}")
        print(f"Reservation id: {short_id(reservation.get('reservation_id'))}")
        print(f"Table: {short_id(reservation.get('table_id'))}")
        pause_screen()
        return reservation


def prompt_modify_reservation(db, user):
    clear_screen()
    reservations = get_active_user_reservations(db, user["user_id"])
    selected = choose_from_list(reservations, "Active Reservations", format_reservation)
    if selected is None:
        return

    state = {
        "date": selected.get("date"),
        "time": selected.get("time"),
        "party_size": str(selected.get("party_size")),
    }

    while True:
        print("Press Enter to keep the previous value.")
        state["date"] = prompt_new_date_value(state["date"])
        state["time"] = prompt_new_time_value(state["time"])
        state["party_size"] = input_with_default("New party size", state["party_size"])

        errors = validate_reservation_input(
            selected.get("customer_id") or "guest",
            state["date"],
            state["time"],
            state["party_size"],
        )
        if errors:
            print("Reservation update failed:")
            for error in errors:
                print(f"- {error}")
            continue

        result = db.modify_reservation(
            reservation_id=selected["reservation_id"],
            date_str=state["date"],
            time_str=state["time"],
            party_size=int(state["party_size"]),
        )
        if "error" in result:
            print(result["error"])
            continue

        print("Reservation updated successfully.")
        print(format_reservation(result))
        pause_screen()
        return


def prompt_cancel_reservation(db, user):
    clear_screen()
    reservations = get_active_user_reservations(db, user["user_id"])
    selected = choose_from_list(reservations, "Active Reservations", format_reservation)
    if selected is None:
        return

    result = db.cancel_reservation(selected["reservation_id"])
    if "error" in result:
        print(result["error"])
        pause_screen()
        return

    print("Reservation canceled successfully.")
    pause_screen()


def prompt_place_order(db, user, menu=None):
    clear_screen()
    reservations = get_active_user_reservations(db, user["user_id"])
    selected_reservation = choose_from_list(
        reservations,
        "Reservations For Ordering",
        format_reservation,
    )
    if selected_reservation is None:
        return

    if menu is None:
        menu = show_menu_items(db)
    if not menu:
        return

    raw_items = ""
    while True:
        raw_items = input_with_default(
            "Enter items as item_number[:quantity], comma-separated (example 1:2,3)",
            raw_items,
        )

        try:
            items = parse_order_request(raw_items, menu)
        except ValueError as exc:
            print(exc)
            continue

        order = db.create_order(
            table_id=selected_reservation["table_id"],
            customer_id=user["user_id"],
            items_list=items,
        )
        if "error" in order:
            print(order["error"])
            continue

        print("Order created successfully.")
        print(f"Order id: {short_id(order.get('order_id'))}")
        print(f"Total amount: EUR {float(order.get('total_amount', 0)):.2f}")
        pause_screen()
        return


def prompt_pay_order(db, user):
    clear_screen()
    orders = [
        order
        for order in db._read_data("orders")
        if order.get("customer_id") == user["user_id"]
        and order.get("order_status") != "paid"
    ]
    selected_order = choose_from_list(
        orders,
        "Unpaid Orders",
        lambda order: (
            f"Order {short_id(order.get('order_id'))} | "
            f"table {short_id(order.get('table_id'))} | "
            f"total EUR {float(order.get('total_amount', 0)):.2f} | "
            f"status {order.get('order_status')}"
        ),
    )
    if selected_order is None:
        return

    method = "card"
    while True:
        method = input_with_default("Payment method [cash/card]", method) or "card"
        payment = db.process_payment(
            selected_order["order_id"],
            selected_order["total_amount"],
            method,
        )
        if "error" in payment:
            print(payment["error"])
            continue

        print("Payment processed successfully.")
        print(
            f"Payment confirmed for EUR {float(selected_order.get('total_amount', 0)):.2f} "
            f"via {method}."
        )
        print(f"Transaction id: {short_id(payment.get('transaction_id'))}")
        pause_screen()
        return


def prompt_check_in():
    clear_screen()
    print_heading("Check In Reservation")
    reservation_code = ""
    while True:
        reservation_code = input_with_default("Reservation code", reservation_code)
        if not reservation_code:
            print("Check-in canceled.")
            return

        try:
            reservation = checkin_reservation(reservation_code)
        except Exception as exc:
            print(f"Check-in failed: {exc}")
            continue

        print("Check-in completed successfully.")
        print(format_reservation(reservation))
        pause_screen()
        return


def prompt_complete_reservation():
    clear_screen()
    print_heading("Complete Reservation")
    reservation_code = ""
    while True:
        reservation_code = input_with_default("Reservation code", reservation_code)
        if not reservation_code:
            print("Completion canceled.")
            return

        try:
            reservation = complete_reservation(reservation_code)
        except Exception as exc:
            print(f"Completion failed: {exc}")
            continue

        print("Reservation completed successfully.")
        print(format_reservation(reservation))
        pause_screen()
        return


def prompt_add_table(db):
    clear_screen()
    capacity = ""
    while True:
        capacity = input_with_default("Table capacity", capacity)
        result = db.add_table(capacity)
        if "error" in result:
            print(result["error"])
            continue
        print(f"Table created: {short_id(result.get('table_id'))}")
        pause_screen()
        return


def prompt_add_menu_item(db):
    clear_screen()
    state = {"name": "", "category": "", "price": ""}

    while True:
        state["name"] = input_with_default("Item name", state["name"])
        state["category"] = input_with_default("Category", state["category"])
        state["price"] = input_with_default("Price", state["price"])

        result = db.add_menu_item(state["name"], state["category"], state["price"])
        if "error" in result:
            print(result["error"])
            continue
        print(f"Menu item created: {result.get('name')}")
        pause_screen()
        return


def customer_menu(db, user):
    while True:
        clear_screen()
        print_heading(f"Customer Menu ({user['username']})")
        print("1. View menu / place order")
        print("2. Create reservation")
        print("3. View my reservations")
        print("4. Modify reservation")
        print("5. Cancel reservation")
        print("6. Pay order")
        print("7. Logout")

        choice = input("Select an option: ").strip()
        if choice == "1":
            prompt_menu_and_order(db, user)
        elif choice == "2":
            prompt_reservation(db, customer_id=user["user_id"])
        elif choice == "3":
            show_user_reservations(db, user)
            pause_screen("Press Enter to go back: ")
        elif choice == "4":
            prompt_modify_reservation(db, user)
        elif choice == "5":
            prompt_cancel_reservation(db, user)
        elif choice == "6":
            prompt_pay_order(db, user)
        elif choice == "7":
            return
        else:
            pause_screen("Invalid option. Press Enter to try again: ")


def staff_menu(db, user):
    while True:
        clear_screen()
        print_heading(f"Staff Menu ({user['username']})")
        print("1. View menu")
        print("2. View all reservations")
        print("3. Check in reservation")
        print("4. Complete reservation")
        print("5. Add table")
        print("6. Add menu item")
        print("7. Logout")

        choice = input("Select an option: ").strip()
        if choice == "1":
            show_menu_items(db)
            pause_screen("Press Enter to go back: ")
        elif choice == "2":
            show_all_reservations(db)
            pause_screen("Press Enter to go back: ")
        elif choice == "3":
            prompt_check_in()
        elif choice == "4":
            prompt_complete_reservation()
        elif choice == "5":
            prompt_add_table(db)
        elif choice == "6":
            prompt_add_menu_item(db)
        elif choice == "7":
            return
        else:
            pause_screen("Invalid option. Press Enter to try again: ")


def run():
    db = JSONDatabase()
    seeded = seed_demo_data(db)
    startup_message = ""
    if seeded:
        startup_message = f"Sample {' and '.join(seeded)} added to make the app usable."

    while True:
        clear_screen()
        print_heading("Restaurant App")
        if startup_message:
            print(startup_message)
            print()
            startup_message = ""
        print("1. Register")
        print("2. Login")
        print("3. Book as guest")
        print("4. View menu")
        print("5. Exit")

        choice = input("Select an option: ").strip()
        if choice == "1":
            prompt_registration(db)
        elif choice == "2":
            user = prompt_login(db)
            if user is None:
                continue
            if user.get("role") == "customer":
                customer_menu(db, user)
            else:
                staff_menu(db, user)
        elif choice == "3":
            prompt_reservation(db)
        elif choice == "4":
            prompt_menu_and_order(db)
        elif choice == "5":
            print("Goodbye.")
            return
        else:
            pause_screen("Invalid option. Press Enter to try again: ")


if __name__ == "__main__":
    run()
