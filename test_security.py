"""
Test cases for password hashing and login attempt limiting.
"""
import pytest
import json
import os
import tempfile
import shutil
from db_handler import JSONDatabase
from datetime import datetime, timedelta


def create_secured_user(
    db,
    username="testuser",
    password="password123",
    role="customer",
    full_name="Test User",
    phone="5551234567",
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


@pytest.fixture
def temp_db_folder():
    """Create a temporary folder for database files during testing."""
    base_dir = os.path.join(os.getcwd(), ".pytest_tmp_security")
    os.makedirs(base_dir, exist_ok=True)
    temp_dir = tempfile.mkdtemp(dir=base_dir)
    yield temp_dir
    shutil.rmtree(temp_dir)


@pytest.fixture
def isolated_db(temp_db_folder, monkeypatch):
    """Create a database instance using a temporary folder."""
    # Monkeypatch the DB_FOLDER to use our temp directory
    import db_handler
    original_db_folder = db_handler.DB_FOLDER
    db_handler.DB_FOLDER = temp_db_folder
    
    db = JSONDatabase()
    
    yield db
    
    # Restore original DB_FOLDER
    db_handler.DB_FOLDER = original_db_folder


class TestPasswordHashing:
    """Test SHA256 password hashing with salt."""
    
    def test_hash_password_generates_salt(self, isolated_db):
        """Test that hash_password generates a random salt."""
        password = "test_password_123"
        hash1 = JSONDatabase.hash_password(password)
        hash2 = JSONDatabase.hash_password(password)
        
        # Hashes should be different (different salts)
        assert hash1 != hash2
        # But both should be in salt:hash format
        assert ":" in hash1
        assert ":" in hash2
    
    def test_hash_password_with_provided_salt(self):
        """Test that hash_password uses provided salt consistently."""
        password = "test_password_123"
        salt = "abcdef1234567890" * 4  # 64 hex chars
        hash1 = JSONDatabase.hash_password(password, salt)
        hash2 = JSONDatabase.hash_password(password, salt)
        
        # Same salt and password should produce same hash
        assert hash1 == hash2
    
    def test_verify_password_correct(self):
        """Test that verify_password accepts correct password."""
        password = "my_secure_password"
        stored_hash = JSONDatabase.hash_password(password)
        assert JSONDatabase.verify_password(stored_hash, password) is True
    
    def test_verify_password_incorrect(self):
        """Test that verify_password rejects incorrect password."""
        password = "my_secure_password"
        wrong_password = "wrong_password"
        stored_hash = JSONDatabase.hash_password(password)
        assert JSONDatabase.verify_password(stored_hash, wrong_password) is False
    
    def test_hash_contains_salt_and_hash(self):
        """Test that stored hash contains both salt and hash."""
        password = "test_password"
        stored_hash = JSONDatabase.hash_password(password)
        
        parts = stored_hash.split(":")
        assert len(parts) == 2
        salt, hashed = parts
        assert len(salt) == 64  # 32 bytes = 64 hex chars
        assert len(hashed) == 64  # SHA256 = 64 hex chars


class TestLoginLimits:
    """Test login attempt limiting and account lockout."""
    
    @pytest.fixture
    def db(self, isolated_db):
        """Create a fresh database for each test."""
        return isolated_db
    
    def test_max_login_attempts_constant(self, db):
        """Test that max login attempts is set correctly."""
        assert db.MAX_LOGIN_ATTEMPTS == 5
    
    def test_lockout_duration_constant(self, db):
        """Test that lockout duration is set correctly (15 minutes)."""
        assert db.LOGIN_LOCKOUT_DURATION == 900
    
    def test_record_failed_login_increments_counter(self, db):
        """Test that failed login attempts are recorded."""
        create_secured_user(db)
        
        # Record a failed attempt
        db.record_failed_login("testuser")
        users = db._read_data("users")
        user = users[0]
        assert user["login_attempts"] == 1
    
    def test_account_locks_after_max_attempts(self, db):
        """Test that account locks after max failed attempts."""
        create_secured_user(db)
        
        # Record max attempts
        for _ in range(db.MAX_LOGIN_ATTEMPTS):
            db.record_failed_login("testuser")
        
        # Account should now be locked
        assert db.is_account_locked("testuser") is True
    
    def test_lockout_until_field_set(self, db):
        """Test that lockout_until field is set when account locks."""
        create_secured_user(db)
        
        # Record max attempts
        for _ in range(db.MAX_LOGIN_ATTEMPTS):
            db.record_failed_login("testuser")
        
        users = db._read_data("users")
        user = users[0]
        
        # lockout_until should be set to a future time
        assert user["lockout_until"] is not None
        lockout_dt = datetime.fromisoformat(user["lockout_until"])
        assert lockout_dt > datetime.now()
    
    def test_reset_login_attempts_after_success(self, db):
        """Test that login attempts reset after successful login."""
        create_secured_user(db)
        
        # Record some failed attempts
        db.record_failed_login("testuser")
        db.record_failed_login("testuser")
        
        users = db._read_data("users")
        assert users[0]["login_attempts"] == 2
        
        # Reset attempts
        db.reset_login_attempts("testuser")
        
        users = db._read_data("users")
        user = users[0]
        assert user["login_attempts"] == 0
        assert user["lockout_until"] is None
    
    def test_authenticate_user_locked_account(self, db):
        """Test that authenticate_user returns None for locked account."""
        create_secured_user(db)
        
        # Lock the account
        for _ in range(db.MAX_LOGIN_ATTEMPTS):
            db.record_failed_login("testuser")
        
        # Try to authenticate
        result = db.authenticate_user("testuser", "password123")
        assert result is None
    
    def test_authenticate_user_resets_attempts_on_success(self, db):
        """Test that successful login resets attempt counter."""
        create_secured_user(db)
        
        # Record a couple failed attempts
        db.record_failed_login("testuser")
        db.record_failed_login("testuser")
        
        # Successful login
        result = db.authenticate_user("testuser", "password123")
        assert result is not None
        assert result["username"] == "testuser"
        
        # Attempts should be reset
        users = db._read_data("users")
        assert users[0]["login_attempts"] == 0


class TestAuthIntegration:
    """Integration tests for auth with hashing and limits."""
    
    @pytest.fixture
    def db(self, isolated_db):
        """Create a fresh database for each test."""
        return isolated_db
    
    def test_full_login_flow_with_hashing(self, db):
        """Test complete login flow with password hashing."""
        # Create user
        created = db.create_user(
            username="john_doe",
            password="SecurePass123!",
            role="customer",
            full_name="John Doe",
            phone="5559876543",
            email="john@example.com",
            secret_question_number=2,
            secret_question_answer="Athens",
        )
        
        assert created is not None
        # Password should be hashed (contain :)
        assert ":" in created["password"]
        
        # Login with correct password
        user = db.authenticate_user("john_doe", "SecurePass123!")
        assert user is not None
        assert user["username"] == "john_doe"
        
        # Login with wrong password fails
        user = db.authenticate_user("john_doe", "WrongPassword")
        assert user is None
    
    def test_multiple_users_independent_lockouts(self, db):
        """Test that multiple users have independent lockout states."""
        create_secured_user(
            db,
            username="user1",
            password="pass1",
            full_name="User One",
            phone="5551111111",
            secret_question_number=3,
            secret_question_answer="Pine",
        )
        create_secured_user(
            db,
            username="user2",
            password="pass2",
            full_name="User Two",
            phone="5552222222",
            secret_question_number=4,
            secret_question_answer="River",
        )
        
        # Lock user1
        for _ in range(db.MAX_LOGIN_ATTEMPTS):
            db.record_failed_login("user1")
        
        # user1 should be locked
        assert db.is_account_locked("user1") is True
        # user2 should not be locked
        assert db.is_account_locked("user2") is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
