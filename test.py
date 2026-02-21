import os
import shutil
from db_handler import JSONDatabase

# --- 1. SETUP: Create a temporary test database ---
# We use a separate folder so we don't accidentally wipe your real mock data
TEST_FOLDER = 'test_db_files'
if not os.path.exists(TEST_FOLDER):
    os.makedirs(TEST_FOLDER)

# Initialize DB and temporarily point it to the test folder
db = JSONDatabase()
for key in db.files:
    db.files[key] = os.path.join(TEST_FOLDER, f"{key}.json")
db._initialize_files()

print("🚀 Starting Database Tests...\n")

try:
    # --- 2. TEST USERS ---
    print("Testing User Creation & Login...")
    new_user = db.create_user("test_anna", "pass123", "customer", "Anna T.", "555-0000")
    assert new_user['username'] == "test_anna", "Failed to create user!"
    
    # Test valid login
    logged_in = db.authenticate_user("test_anna", "pass123")
    assert logged_in is not None, "Valid login failed!"
    
    # Test invalid login
    bad_login = db.authenticate_user("test_anna", "wrong_password")
    assert bad_login is None, "Invalid login should have failed!"
    print("✅ Users OK")

    # --- 3. TEST TABLES & MENU ---
    print("Testing Tables and Menu...")
    table = db.add_table(capacity=4)
    assert table['status'] == "free", "New table should be free!"
    
    menu_item = db.add_menu_item("Test Burger", "Main", 10.00)
    assert menu_item['price'] == 10.00, "Menu item price is wrong!"
    print("✅ Tables & Menu OK")

    # --- 4. TEST RESERVATIONS ---
    print("Testing Reservations...")
    reservation = db.create_reservation(
        new_user['user_id'], table['table_id'], "2026-02-20", "19:00", 2
    )
    assert reservation['status'] == "confirmed", "Reservation not confirmed!"
    print("✅ Reservations OK")

    # --- 5. TEST ORDERS & TRANSACTIONS ---
    print("Testing Orders & Payments...")
    items = [{"item_id": menu_item['item_id'], "quantity": 2, "special_notes": "None"}]
    order = db.create_order(table['table_id'], new_user['user_id'], items)
    
    assert order['total_amount'] == 20.00, "Order total math is wrong!"
    assert order['order_status'] == "kitchen", "Order didn't go to kitchen!"

    # Pay for it
    payment = db.process_payment(order['order_id'], order['total_amount'], "card")
    assert payment['amount_paid'] == 20.00, "Payment amount is wrong!"
    
    # Check if order status updated to 'paid'
    orders_data = db._read_data('orders')
    updated_order = next(o for o in orders_data if o['order_id'] == order['order_id'])
    assert updated_order['order_status'] == "paid", "Order status didn't update to paid!"
    print("✅ Orders & Transactions OK")

    print("\n🎉 ALL TESTS PASSED! Your DB logic works.")

except AssertionError as e:
    print(f"\n❌ TEST FAILED: {e}")

finally:
    # --- 6. TEARDOWN: Clean up the mess ---
    # This deletes the test folder so you have a clean slate for the next run
    shutil.rmtree(TEST_FOLDER)
    print("🧹 Test cleanup complete.")