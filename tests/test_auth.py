import tempfile
from pathlib import Path
import unittest

from src.auth import authenticate_user, ensure_default_admin_user, register_user, user_exists


class TestAuthStore(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "users.json"

    def tearDown(self):
        self.tmp.cleanup()

    def test_register_and_login_user(self):
        user = register_user("Alice_01", "secret123", self.path)

        self.assertEqual(user.username, "alice_01")
        self.assertTrue(user_exists("ALICE_01", self.path))

        logged_in = authenticate_user("alice_01", "secret123", self.path)
        self.assertEqual(logged_in.username, "alice_01")

    def test_rejects_duplicate_username(self):
        register_user("bob", "secret123", self.path)

        with self.assertRaisesRegex(ValueError, "用户名已存在"):
            register_user("BOB", "another123", self.path)

    def test_rejects_bad_password(self):
        register_user("carol", "secret123", self.path)

        with self.assertRaisesRegex(ValueError, "用户名或密码错误"):
            authenticate_user("carol", "wrong-password", self.path)

    def test_validates_username_and_password(self):
        with self.assertRaisesRegex(ValueError, "用户名需为"):
            register_user("a b", "secret123", self.path)

        with self.assertRaisesRegex(ValueError, "密码至少"):
            register_user("david", "123", self.path)

    def test_bad_json_behaves_like_empty_store(self):
        self.path.write_text("{bad", encoding="utf-8")

        self.assertFalse(user_exists("alice", self.path))

    def test_ensure_default_admin_user(self):
        user = ensure_default_admin_user(self.path)

        self.assertEqual(user.username, "admin")
        logged_in = authenticate_user("admin", "926926", self.path)
        self.assertEqual(logged_in.username, "admin")

        again = ensure_default_admin_user(self.path)
        self.assertEqual(again.username, "admin")


if __name__ == "__main__":
    unittest.main()
