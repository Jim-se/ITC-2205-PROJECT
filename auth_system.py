from getpass import getpass

from db_handler import JSONDatabase


# Caption:
# What: Map each role to the console area it should open after login.
# How: Store the redirect target in a small dictionary keyed by role.
# Why: The feature list explicitly requires redirect behavior based on role.
ROLE_REDIRECTS = {
    "customer": "customer_menu",
    "employee": "employee_dashboard",
    "owner": "owner_admin_panel",
}


def get_role_redirect(role):
    # Caption:
    # What: Resolve where a logged-in user should be sent next.
    # How: Look up the role in ROLE_REDIRECTS and fall back to a safe default.
    # Why: Keeps role-routing logic in one place instead of scattering strings.
    return ROLE_REDIRECTS.get(role, "main_menu")


def register_account(
    db,
    username,
    password,
    confirm_password,
    full_name,
    phone,
    email="",
    role="customer",
):
    # Caption:
    # What: Register a new account from console-provided input.
    # How: Validate password rules, delegate persistence to JSONDatabase,
    # then return a structured result for the UI layer.
    # Why: The project needed a dedicated registration flow separate from storage.
    if password != confirm_password:
        return {"success": False, "message": "Passwords do not match"}
    if len(password) < 6:
        return {
            "success": False,
            "message": "Password must be at least 6 characters long",
        }

    user = db.create_user(
        username=username,
        password=password,
        role=role,
        full_name=full_name,
        phone=phone,
        email=email,
    )
    if "error" in user:
        return {"success": False, "message": user["error"]}

    return {
        "success": True,
        "message": "Registration successful",
        "user": user,
        "redirect_to": get_role_redirect(user["role"]),
    }


def login_account(db, identifier, password):
    # Caption:
    # What: Log a user in using username, email, or phone with security feedback.
    # How: Call the database authentication helper and return a UI-friendly result
    #      with specific error messages for lockouts.
    # Why: Console screens need a simple function that combines auth, routing, and security.
    user = db.authenticate_user(identifier, password)
    if user is None:
        # Check if account is locked
        identifier_lower = identifier.strip().lower()
        users_data = db._read_data("users")
        for user_record in users_data:
            matches = (
                user_record.get("username", "").lower() == identifier_lower
                or user_record.get("email", "").lower() == identifier_lower
                or user_record.get("phone", "").strip() == identifier.strip()
            )
            if matches and db.is_account_locked(user_record.get("username", "")):
                return {
                    "success": False,
                    "message": f"Account locked due to too many failed attempts. Try again in 15 minutes.",
                }
        
        return {"success": False, "message": "Invalid login credentials"}

    return {
        "success": True,
        "message": "Login successful",
        "user": user,
        "redirect_to": get_role_redirect(user["role"]),
    }


def prompt_registration(db, role="customer"):
    # Caption:
    # What: Run an interactive console registration prompt.
    # How: Collect fields from input/getpass and pass them into register_account.
    # Why: The project uses a console UI, so the auth module needs prompt helpers.
    try:
        print("\nRegistration")
        username = input("Username: ").strip()
        full_name = input("Full name: ").strip()
        phone = input("Phone: ").strip()
        email = input("Email (optional): ").strip()
        password = getpass("Password: ")
        confirm_password = getpass("Confirm password: ")

        result = register_account(
            db=db,
            username=username,
            password=password,
            confirm_password=confirm_password,
            full_name=full_name,
            phone=phone,
            email=email,
            role=role,
        )
        print(result["message"])
        return result
    except Exception as e:
        print(f"Registration error: {str(e)}")
        return {"success": False, "message": f"Registration failed: {str(e)}"}


def prompt_login(db):
    # Caption:
    # What: Run an interactive console login prompt.
    # How: Collect identifier/password and pass them into login_account.
    # Why: Gives the console application a ready-to-use login entry point.
    try:
        print("\nLogin")
        identifier = input("Username, email, or phone: ").strip()
        password = getpass("Password: ")

        result = login_account(db, identifier, password)
        print(result["message"])
        if result["success"]:
            print(f"Redirect to: {result['redirect_to']}")
        return result
    except Exception as e:
        print(f"Login error: {str(e)}")
        return {"success": False, "message": f"Login failed: {str(e)}"}


def run_auth_menu(db=None):
    # Caption:
    # What: Provide a minimal console menu for registration and login.
    # How: Loop over simple numeric choices and call the prompt helpers.
    # Why: The repo did not have a UI entry point, so this gives auth an immediate
    # standalone console interface for testing and integration.
    try:
        if db is None:
            db = JSONDatabase()

        while True:
            try:
                print("\nAuthentication Menu")
                print("1. Register customer account")
                print("2. Login")
                print("3. Exit")
                choice = input("Select an option: ").strip()

                if choice == "1":
                    prompt_registration(db)
                elif choice == "2":
                    prompt_login(db)
                elif choice == "3":
                    return None
                else:
                    print("Invalid option")
            except KeyboardInterrupt:
                print("\nMenu interrupted by user")
                return None
            except Exception as e:
                print(f"Menu error: {str(e)}")
    except Exception as e:
        print(f"Failed to initialize authentication menu: {str(e)}")


if __name__ == "__main__":
    run_auth_menu()
