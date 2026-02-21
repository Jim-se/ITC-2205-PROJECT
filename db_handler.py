import json
import os
import uuid
from datetime import datetime

# Configuration: Folder where JSON files are stored
DB_FOLDER = 'database'
if not os.path.exists(DB_FOLDER):
    os.makedirs(DB_FOLDER)

class JSONDatabase:
    def __init__(self):
        # Define file paths based on your schema
        self.files = {
            'users': os.path.join(DB_FOLDER, 'users.json'),
            'tables': os.path.join(DB_FOLDER, 'tables.json'),
            'menu': os.path.join(DB_FOLDER, 'menu.json'),
            'reservations': os.path.join(DB_FOLDER, 'reservations.json'),
            'orders': os.path.join(DB_FOLDER, 'orders.json'),
            'transactions': os.path.join(DB_FOLDER, 'transactions.json')
        }
        self._initialize_files()

    def _initialize_files(self):
        """Creates empty JSON files if they don't exist."""
        for file_path in self.files.values():
            if not os.path.exists(file_path):
                with open(file_path, 'w') as f:
                    json.dump([], f)

    def _read_data(self, entity_name):
        """Generic helper to read data from a specific file."""
        try:
            with open(self.files[entity_name], 'r') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return []

    def _write_data(self, entity_name, data):
        """Generic helper to write data to a specific file."""
        with open(self.files[entity_name], 'w') as f:
            json.dump(data, f, indent=4) # Indent makes it human-readable as requested

# --- USERS ---
    def create_user(self, username, password, role, full_name, phone):
        users = self._read_data('users')
        
        # Simple check to prevent duplicate usernames
        if any(u['username'] == username for u in users):
            return {"error": "Username already exists"}

        new_user = {
            "user_id": str(uuid.uuid4()),
            "username": username,
            "password": password, # In a real app, hash this!
            "role": role, # 'customer', 'employee', 'owner'
            "full_name": full_name,
            "phone": phone
        }
        users.append(new_user)
        self._write_data('users', users)
        return new_user

    def authenticate_user(self, username, password):
        users = self._read_data('users')
        for user in users:
            if user['username'] == username and user['password'] == password:
                return user
        return None

# --- TABLES ---
    def add_table(self, capacity):
        tables = self._read_data('tables')
        new_table = {
            "table_id": str(uuid.uuid4()),
            "capacity": capacity,
            "status": "free" # Default status
        }
        tables.append(new_table)
        self._write_data('tables', tables)
        return new_table

    def update_table_status(self, table_id, new_status):
        """Updates status to 'free', 'reserved', or 'occupied'"""
        tables = self._read_data('tables')
        for table in tables:
            if table['table_id'] == table_id:
                table['status'] = new_status
                self._write_data('tables', tables)
                return True
        return False

    # --- MENU ---
    def add_menu_item(self, name, category, price):
        menu = self._read_data('menu')
        new_item = {
            "item_id": str(uuid.uuid4()),
            "name": name,
            "category": category,
            "price": price,
            "is_available": True
        }
        menu.append(new_item)
        self._write_data('menu', menu)
        return new_item

# --- RESERVATIONS ---
    def create_reservation(self, customer_id, table_id, date_str, time_str, party_size):
        reservations = self._read_data('reservations')
        
        # Validating table availability would happen in the Logic Layer, 
        # here we just write the data.
        new_res = {
            "reservation_id": str(uuid.uuid4()),
            "customer_id": customer_id,
            "table_id": table_id,
            "date": date_str,
            "time": time_str,
            "party_size": party_size,
            "status": "confirmed"
        }
        reservations.append(new_res)
        self._write_data('reservations', reservations)
        
        # Automatically mark table as reserved?
        # self.update_table_status(table_id, "reserved") 
        return new_res

# --- ORDERS ---
    def create_order(self, table_id, customer_id, items_list):
        """
        items_list should be a list of dicts: 
        [{'item_id': '...', 'quantity': 2, 'special_notes': 'no onions'}]
        """
        orders = self._read_data('orders')
        
        # Calculate total (Optional: Logic layer usually does this)
        total_amount = 0.0
        menu = self._read_data('menu')
        # Simple lookup to calculate price (O(n^2) but fine for mock DB)
        for order_item in items_list:
            for menu_item in menu:
                if order_item['item_id'] == menu_item['item_id']:
                    total_amount += menu_item['price'] * order_item['quantity']

        new_order = {
            "order_id": str(uuid.uuid4()),
            "table_id": table_id,
            "customer_id": customer_id,
            "order_status": "kitchen", # pending -> kitchen
            "items": items_list,
            "total_amount": round(total_amount, 2)
        }
        orders.append(new_order)
        self._write_data('orders', orders)
        return new_order

    def update_order_status(self, order_id, status):
        """Updates to 'ready', 'served', 'paid'"""
        orders = self._read_data('orders')
        for order in orders:
            if order['order_id'] == order_id:
                order['order_status'] = status
                self._write_data('orders', orders)
                return True
        return False

    # --- TRANSACTIONS ---
    def process_payment(self, order_id, amount, method):
        transactions = self._read_data('transactions')
        new_trans = {
            "transaction_id": str(uuid.uuid4()),
            "order_id": order_id,
            "amount_paid": amount,
            "payment_method": method,
            "timestamp": datetime.now().isoformat()
        }
        transactions.append(new_trans)
        self._write_data('transactions', transactions)
        
        # Update order status to paid
        self.update_order_status(order_id, "paid")
        return new_trans