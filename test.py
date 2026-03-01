from db_handler import JSONDatabase


def _make_test_db(tmp_path):
    db = JSONDatabase()
    for key in db.files:
        db.files[key] = str(tmp_path / f"{key}.json")
    db._initialize_files()
    return db


def test_user_creation_and_login(tmp_path):
    db = _make_test_db(tmp_path)

    new_user = db.create_user("test_anna", "pass123", "customer", "Anna T.", "555-0000")
    assert new_user["username"] == "test_anna"

    logged_in = db.authenticate_user("test_anna", "pass123")
    assert logged_in is not None

    bad_login = db.authenticate_user("test_anna", "wrong_password")
    assert bad_login is None


def test_tables_and_menu(tmp_path):
    db = _make_test_db(tmp_path)

    table = db.add_table(capacity=4)
    assert table["status"] == "free"

    menu_item = db.add_menu_item("Test Burger", "Main", 10.00)
    assert menu_item["price"] == 10.00


def test_reservation(tmp_path):
    db = _make_test_db(tmp_path)
    user = db.create_user("test_anna", "pass123", "customer", "Anna T.", "555-0000")
    table = db.add_table(capacity=4)

    reservation = db.create_reservation(
        user["user_id"], table["table_id"], "2026-02-20", "19:00", 2
    )
    assert reservation["status"] == "confirmed"


def test_orders_and_payments(tmp_path):
    db = _make_test_db(tmp_path)
    user = db.create_user("test_anna", "pass123", "customer", "Anna T.", "555-0000")
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
