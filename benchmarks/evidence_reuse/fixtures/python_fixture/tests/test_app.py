import unittest

from app import fixture_label, greeting, mode_label, total_with_tax


class AppTests(unittest.TestCase):
    def test_total_with_tax(self) -> None:
        self.assertEqual(total_with_tax(10), 11.5)

    def test_greeting(self) -> None:
        self.assertEqual(greeting("  Ada "), "Hello, Ada!")

    def test_fixture_label(self) -> None:
        self.assertEqual(fixture_label(), "control")

    def test_mode_label(self) -> None:
        self.assertEqual(mode_label(), "test")


if __name__ == "__main__":
    unittest.main()
