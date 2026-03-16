from auth_system import login_account, register_account
from db_handler import JSONDatabase


def _make_test_db(tmp_path):
    # Caption:
    # What: Build an isolated database for auth tests.
    # How: Point every JSON file at pytest's temporary directory.
    # Why: Prevent auth tests from modifying the real project data.
    db = JSONDatabase()
    for key in db.files:
        db.files[key] = str(tmp_path / f"{key}.json")
    db._initialize_files()
    return db


def test_register_account_creates_customer_with_redirect(tmp_path):
    # Caption:
    # What: Verify a new customer account can be registered.
    # How: Call the auth registration wrapper and assert success plus redirect.
    # Why: Confirms the new separate auth layer works for normal signup flow.
    db = _make_test_db(tmp_path)

    result = register_account(
        db=db,
        username="anna_customer",
        password="pass123",
        confirm_password="pass123",
        full_name="Anna Customer",
        phone="555-1000",
        email="anna@example.com",
    )

    assert result["success"] is True
    assert result["user"]["email"] == "anna@example.com"
    assert result["redirect_to"] == "customer_menu"


def test_register_account_rejects_bad_confirmation_and_duplicates(tmp_path):
    # Caption:
    # What: Verify registration rejects invalid signup attempts.
    # How: Check mismatched passwords and duplicate email/phone values.
    # Why: Registration is only safe if it blocks obvious bad input and collisions.
    db = _make_test_db(tmp_path)

    mismatch = register_account(
        db=db,
        username="anna_customer",
        password="pass123",
        confirm_password="pass999",
        full_name="Anna Customer",
        phone="555-1000",
        email="anna@example.com",
    )
    assert mismatch["success"] is False

    first = register_account(
        db=db,
        username="anna_customer",
        password="pass123",
        confirm_password="pass123",
        full_name="Anna Customer",
        phone="555-1000",
        email="anna@example.com",
    )
    assert first["success"] is True

    duplicate = register_account(
        db=db,
        username="anna_customer_2",
        password="pass123",
        confirm_password="pass123",
        full_name="Anna Customer Two",
        phone="555-1000",
        email="anna@example.com",
    )
    assert duplicate["success"] is False


def test_login_account_accepts_email_and_phone_with_role_redirect(tmp_path):
    # Caption:
    # What: Verify login works with alternative identifiers and role routing.
    # How: Create an employee account, then log in by email and by phone.
    # Why: The feature list explicitly requires email/phone login and role redirects.
    db = _make_test_db(tmp_path)
    db.create_user(
        username="host_user",
        password="hostpass",
        role="employee",
        full_name="Host User",
        phone="555-2000",
        email="host@example.com",
    )

    email_login = login_account(db, "host@example.com", "hostpass")
    assert email_login["success"] is True
    assert email_login["redirect_to"] == "employee_dashboard"

    phone_login = login_account(db, "555-2000", "hostpass")
    assert phone_login["success"] is True
    assert phone_login["user"]["role"] == "employee"
