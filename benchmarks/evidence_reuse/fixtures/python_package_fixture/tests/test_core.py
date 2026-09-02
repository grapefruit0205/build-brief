import unittest

from samplepkg import compute, message, mode_label


class PackageTests(unittest.TestCase):
    def test_compute(self) -> None:
        self.assertEqual(compute(4), 8)

    def test_message(self) -> None:
        self.assertEqual(message("  Ada "), "Welcome Ada")

    def test_mode_label(self) -> None:
        self.assertEqual(mode_label(), "test")


if __name__ == "__main__":
    unittest.main()
