"""Unit tests cho parse_names, parse_command, parse_count trong drinkbot.py."""

import unittest
import sys
from pathlib import Path

# Thêm thư mục gốc vào path để import drinkbot
sys.path.insert(0, str(Path(__file__).parent.parent))

from drinkbot import parse_names, parse_command, parse_count


class TestParseNames(unittest.TestCase):
    """Test cho hàm parse_names."""

    # --- Ca hợp lệ ---
    def test_single_name(self):
        """Một tên đơn giản."""
        self.assertEqual(parse_names("Nam"), ["Nam"])

    def test_multiple_names_comma_separated(self):
        """Nhiều tên ngăn cách bằng dấu phẩy."""
        self.assertEqual(parse_names("Nam, Lan, Hùng"), ["Nam", "Lan", "Hùng"])

    def test_names_with_extra_spaces(self):
        """Tên có khoảng trắng thừa."""
        self.assertEqual(parse_names("  Nam  ,  Lan  ,  Hùng  "), ["Nam", "Lan", "Hùng"])

    def test_names_with_newlines(self):
        """Tên ngăn cách bằng dấu xuống dòng (được chuyển thành phẩy)."""
        self.assertEqual(parse_names("Nam\nLan\nHùng"), ["Nam", "Lan", "Hùng"])

    # --- Ca biên ---
    def test_empty_string(self):
        """Chuỗi rỗng trả về danh sách rỗng."""
        self.assertEqual(parse_names(""), [])

    def test_only_spaces_and_commas(self):
        """Chỉ có khoảng trắng và dấu phẩy."""
        self.assertEqual(parse_names("  ,  ,  "), [])

    def test_duplicate_names_case_insensitive(self):
        """Tên trùng (không phân biệt hoa thường) bị loại."""
        self.assertEqual(parse_names("Nam, nam, NAM, Lan"), ["Nam", "Lan"])

    def test_name_truncated_to_max_length(self):
        """Tên quá dài bị cắt ngắn."""
        long_name = "A" * 100
        result = parse_names(long_name)
        self.assertEqual(len(result[0]), 64)  # MAX_NAME_LEN = 64

    # --- Ca sai định dạng ---
    def test_mixed_empty_and_valid_names(self):
        """Trộn tên rỗng và tên hợp lệ."""
        self.assertEqual(parse_names(", Nam, , Lan, "), ["Nam", "Lan"])

    def test_names_with_internal_spaces(self):
        """Tên có khoảng trắng bên trong được giữ lại."""
        self.assertEqual(parse_names("Nguyễn Văn Nam, Trần Lan"), ["Nguyễn Văn Nam", "Trần Lan"])


class TestParseCommand(unittest.TestCase):
    """Test cho hàm parse_command."""

    # --- Ca hợp lệ ---
    def test_simple_command(self):
        """Lệnh đơn giản không có tham số."""
        self.assertEqual(parse_command("/random", "mybot"), ("random", ""))

    def test_command_with_args(self):
        """Lệnh có tham số."""
        self.assertEqual(parse_command("/random 3", "mybot"), ("random", "3"))

    def test_command_with_bot_username(self):
        """Lệnh có @bot_username khớp."""
        self.assertEqual(parse_command("/random@mybot 3", "mybot"), ("random", "3"))

    def test_command_with_different_case_bot_username(self):
        """Lệnh có @bot_username khác hoa thường nhưng vẫn khớp."""
        self.assertEqual(parse_command("/random@MyBot 3", "mybot"), ("random", "3"))

    # --- Ca biên ---
    def test_non_command_text(self):
        """Văn bản không phải lệnh (không bắt đầu bằng /)."""
        self.assertEqual(parse_command("random 3", "mybot"), ("", ""))

    def test_command_with_wrong_bot_username(self):
        """Lệnh có @bot_username không khớp."""
        self.assertEqual(parse_command("/random@otherbot 3", "mybot"), ("", ""))

    def test_empty_bot_username_accepts_any_target(self):
        """bot_username rỗng chấp nhận mọi target."""
        self.assertEqual(parse_command("/random@anybot 3", ""), ("random", "3"))

    def test_command_only_slash(self):
        """Lệnh chỉ có dấu /."""
        self.assertEqual(parse_command("/", "mybot"), ("", ""))

    def test_command_with_multiple_spaces(self):
        """Lệnh có nhiều khoảng trắng giữa lệnh và tham số."""
        self.assertEqual(parse_command("/random    3", "mybot"), ("random", "3"))

    # --- Ca sai định dạng ---
    def test_command_with_leading_spaces(self):
        """Lệnh có khoảng trắng ở đầu (không phải lệnh)."""
        self.assertEqual(parse_command(" /random 3", "mybot"), ("", ""))

    def test_command_case_insensitive(self):
        """Lệnh không phân biệt hoa thường."""
        self.assertEqual(parse_command("/RANDOM 3", "mybot"), ("random", "3"))


class TestParseCount(unittest.TestCase):
    """Test cho hàm parse_count."""

    # --- Ca hợp lệ ---
    def test_valid_number(self):
        """Số hợp lệ."""
        self.assertEqual(parse_count("3", 10), (3, ""))

    def test_empty_args_defaults_to_one(self):
        """Tham số rỗng mặc định là 1."""
        self.assertEqual(parse_count("", 10), (1, ""))

    def test_number_with_extra_text(self):
        """Số đi kèm văn bản thừa (chỉ lấy số đầu)."""
        self.assertEqual(parse_count("3 abc", 10), (3, ""))

    # --- Ca biên ---
    def test_number_at_limit(self):
        """Số bằng đúng giới hạn."""
        self.assertEqual(parse_count("10", 10), (10, ""))

    def test_number_exceeds_limit(self):
        """Số vượt giới hạn bị cắt."""
        self.assertEqual(parse_count("100", 10), (10, ""))

    def test_number_exceeds_max_pick(self):
        """Số vượt MAX_PICK bị cắt."""
        self.assertEqual(parse_count("100", 100), (10, ""))  # MAX_PICK = 10

    def test_number_one(self):
        """Số nhỏ nhất hợp lệ."""
        self.assertEqual(parse_count("1", 10), (1, ""))

    # --- Ca sai định dạng ---
    def test_zero_returns_error(self):
        """Số 0 trả về lỗi."""
        n, err = parse_count("0", 10)
        self.assertEqual(n, 0)
        self.assertIn("Ít nhất", err)

    def test_negative_returns_error(self):
        """Số âm trả về lỗi."""
        n, err = parse_count("-5", 10)
        self.assertEqual(n, 0)
        self.assertIn("Ít nhất", err)

    def test_non_numeric_returns_error(self):
        """Không phải số trả về lỗi."""
        n, err = parse_count("abc", 10)
        self.assertEqual(n, 0)
        self.assertIn("không hợp lệ", err)


if __name__ == "__main__":
    unittest.main()
