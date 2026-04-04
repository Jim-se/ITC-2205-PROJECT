from db_handler import JSONDatabase


def _make_test_db(tmp_path):
    # Caption:
    # What: Build an isolated database for each test.
    # How: Redirect JSON file paths into pytest's temporary folder.
    # Why: Prevent tests from changing real project data.
    db = JSONDatabase()
    for key in db.files:
        db.files[key] = str(tmp_path / f"{key}.json")
    db._initialize_files()
    return db


def _create_test_user(
    db,
    username="test_anna",
    password="pass123",
    role="customer",
    full_name="Anna T.",
    phone="555-0000",
    email="",
    secret_question_number=1,
    secret_question_answer="Fluffy",
):
    return db.create_user(
        username=username,
        password=password,
        role=role,
        full_name=full_name,
        phone=phone,
        email=email,
        secret_question_number=secret_question_number,
        secret_question_answer=secret_question_answer,
    )


def test_user_creation_and_login(tmp_path):
    # Caption:
    # What: Verify user creation and authentication basics.
    # How: Create one user, then check valid and invalid login paths.
    # Why: Confirm account flow still works after input-validation changes.
    db = _make_test_db(tmp_path)

    new_user = _create_test_user(db)
    assert new_user["username"] == "test_anna"

    logged_in = db.authenticate_user("test_anna", "pass123")
    assert logged_in is not None

    bad_login = db.authenticate_user("test_anna", "wrong_password")
    assert bad_login is None


def test_tables_and_menu(tmp_path):
    # Caption:
    # What: Verify table and menu item creation.
    # How: Add a table and one menu item, then assert stored defaults.
    # Why: Ensure core setup data remains valid for reservations/orders.
    db = _make_test_db(tmp_path)

    table = db.add_table(capacity=4)
    assert table["status"] == "free"

    menu_item = db.add_menu_item("Test Burger", "Main", 10.00)
    assert menu_item["price"] == 10.00


def test_reservation(tmp_path):
    # Caption:
    # What: Verify a standard reservation is created successfully.
    # How: Create user/table, then reserve a valid date/time/party size.
    # Why: Confirm happy-path booking still works with stricter checks.
    db = _make_test_db(tmp_path)
    user = _create_test_user(db)
    table = db.add_table(capacity=4)

    reservation = db.create_reservation(
        user["user_id"], table["table_id"], "2026-02-20", "19:00", 2
    )
    assert reservation["status"] == "confirmed"


def test_input_validation(tmp_path):
    # Caption:
    # What: Verify invalid input is rejected across key operations.
    # How: Submit bad user/table/menu/reservation values and assert errors.
    # Why: Protect system integrity against malformed console input.
    db = _make_test_db(tmp_path)

    bad_user = db.create_user(
        "",
        "pass123",
        "customer",
        "Anna T.",
        "555-0000",
        secret_question_number=1,
        secret_question_answer="Fluffy",
    )
    assert "error" in bad_user

    bad_table = db.add_table(capacity=0)
    assert "error" in bad_table

    bad_menu_item = db.add_menu_item("Soup", "Starter", -1)
    assert "error" in bad_menu_item

    user = _create_test_user(
        db,
        username="valid_user",
        full_name="Valid User",
        phone="555-1111",
    )
    table = db.add_table(capacity=2)

    bad_date = db.create_reservation(
        user["user_id"], table["table_id"], "2026-02-30", "19:00", 2
    )
    assert "error" in bad_date

    too_large = db.create_reservation(
        user["user_id"], table["table_id"], "2026-03-01", "19:00", 5
    )
    assert "error" in too_large

    first = db.create_reservation(
        user["user_id"], table["table_id"], "2026-03-02", "19:00", 2
    )
    assert "error" not in first

    conflict = db.create_reservation(
        user["user_id"], table["table_id"], "2026-03-02", "19:00", 1
    )
    assert "error" in conflict


def test_modify_and_cancel_reservation(tmp_path):
    # Caption:
    # What: Verify reservation modify/cancel features.
    # How: Modify a booking, test conflict rejection, then cancel and re-check.
    # Why: Validate week-5 booking management requirements end-to-end.
    db = _make_test_db(tmp_path)
    user = _create_test_user(db)
    table_one = db.add_table(capacity=4)
    table_two = db.add_table(capacity=6)

    reservation = db.create_reservation(
        user["user_id"], table_one["table_id"], "2026-03-10", "19:00", 2
    )
    reservation_id = reservation["reservation_id"]

    modified = db.modify_reservation(
        reservation_id,
        date_str="2026-03-10",
        time_str="20:00",
        party_size=4,
        table_id=table_two["table_id"],
    )
    assert modified["status"] == "modified"
    assert modified["table_id"] == table_two["table_id"]
    assert modified["time"] == "20:00"
    assert modified["party_size"] == 4

    second = db.create_reservation(
        user["user_id"], table_one["table_id"], "2026-03-10", "18:00", 2
    )
    conflict = db.modify_reservation(
        second["reservation_id"],
        date_str="2026-03-10",
        time_str="20:00",
        table_id=table_two["table_id"],
    )
    assert "error" in conflict

    canceled = db.cancel_reservation(reservation_id)
    assert canceled["status"] == "canceled"
    assert "canceled_at" in canceled

    modify_canceled = db.modify_reservation(reservation_id, party_size=2)
    assert "error" in modify_canceled

    cancel_again = db.cancel_reservation(reservation_id)
    assert "error" in cancel_again


def test_orders_and_payments(tmp_path):
    # Caption:
    # What: Verify order total calculation and payment status update.
    # How: Create order from menu items, process payment, assert status=paid.
    # Why: Confirm order/payment flow remains correct after validations.
    db = _make_test_db(tmp_path)
    user = _create_test_user(db)
    table = db.add_table(capacity=4)
    menu_item = db.add_menu_item("Test Burger", "Main", 10.00)

    items = [{"item_id": menu_item["item_id"], "quantity": 2, "special_notes": "None"}]
    order = db.create_order(table["table_id"], user["user_id"], items)
    assert order["total_amount"] == 20.00
    assert order["order_status"] == "kitchen"

    payment = db.process_payment(order["order_id"], order["total_amount"], "card")
    assert payment["amount_paid"] == 20.00

    orders_data = db._read_data("orders")
    updated_order = next(o for o in orders_data if o["order_id"] == order["order_id"])
    assert updated_order["order_status"] == "paid"


if __name__ == "__main__":
    import pytest

    raise SystemExit(pytest.main([__file__]))
