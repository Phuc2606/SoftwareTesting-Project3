"""Shared Selenium support for Moodle Add a new user tests (BTL3)."""
from __future__ import annotations

import csv
import re
import sys
import unittest
from pathlib import Path

from selenium import webdriver

from selenium.common.exceptions import (
    ElementClickInterceptedException,
    TimeoutException,
    WebDriverException,
)

from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait, Select

SELECT_FIELDS = ("auth", "maildisplay", "country", "timezone", "lang")
CHECKBOX_FIELDS = ("suspended", "generatepassword", "forcepasswordchange")
INPUT_FIELDS = (
    "username", "password", "firstname", "lastname", "email",
    "moodlenetprofile", "city", "description", "picturedescription",
    "firstnamephonetic", "lastnamephonetic", "middlename", "alternatename",
    "interests", "idnumber", "institution", "department", "phone1", "phone2",
    "address",
)


def normalize(value: str | None) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def parse_pairs(value: str | None, delimiter: str = "="):
    pairs = []
    for item in (value or "").split(";"):
        if not item.strip():
            continue
        key, sep, expected = item.partition(delimiter)
        if not sep or not key.strip():
            raise ValueError(f"Invalid test data value: {item}")
        pairs.append((key.strip(), expected.strip()))
    return pairs


def make_driver(browser_name: str, headed: bool, width: int = 1440, height: int = 1000):
    options = webdriver.ChromeOptions() if browser_name == "chrome" else webdriver.EdgeOptions()
    if not headed:
        options.add_argument("--headless=new")
    options.add_argument(f"--window-size={width},{height}")
    options.add_argument("--disable-notifications")
    options.add_argument("--disable-popup-blocking")
    browser = webdriver.Chrome if browser_name == "chrome" else webdriver.Edge
    driver = browser(options=options)
    driver.set_page_load_timeout(45)
    return driver


def login(driver, wait, login_url: str, add_user_url: str, username: str, password: str, locators=None):
    locators = locators or {
        "login_username": (By.ID, "username"),
        "login_password": (By.ID, "password"),
        "login_button": (By.ID, "loginbtn"),
        "username": (By.ID, "id_username"),
    }
    driver.get(login_url)
    user_fields = driver.find_elements(*locators["login_username"])
    if user_fields and user_fields[0].is_displayed():
        wait.until(EC.visibility_of_element_located(locators["login_username"])).send_keys(username)
        wait.until(EC.visibility_of_element_located(locators["login_password"])).send_keys(password)
        wait.until(EC.element_to_be_clickable(locators["login_button"])).click()
        # Do not rely only on a particular Moodle redirect URL.
        wait.until(lambda d: not d.find_elements(*locators["login_button"]))
    driver.get(add_user_url)
    wait.until(EC.visibility_of_element_located(locators["username"]))
    if "/login/" in driver.current_url:
        raise RuntimeError("Login failed: Moodle redirected back to the login page.")


def run_data_driven_suite(
    rows, locators, base_url, login_path, add_user_path, admin_user,
    admin_password, browser_name, headed, timeout, root: Path, result_file: Path,
):
    login_url = base_url.rstrip("/") + "/" + login_path.lstrip("/")
    add_user_url = base_url.rstrip("/") + "/" + add_user_path.lstrip("/")

    class AddNewUserTests(unittest.TestCase):
        @classmethod
        def setUpClass(cls):
            cls.driver = make_driver(browser_name, headed)
            cls.addClassCleanup(cls.driver.quit)
            cls.wait = WebDriverWait(cls.driver, timeout)
            cls.results = []
            login(cls.driver, cls.wait, login_url, add_user_url, admin_user, admin_password, locators)

        
        def visible(self, key):
            if key not in locators:
                raise KeyError(f"Locator '{key}' is not configured.")

            locator = locators[key]
            element = self.wait.until(
                EC.presence_of_element_located(locator)
            )

            # Mở các section đang thu gọn của Moodle.
            self.driver.execute_script("""
                let node = arguments[0];

                while (node && node !== document.body) {
                    if (node.classList?.contains('collapse') &&
                        !node.classList.contains('show')) {
                        const toggle = document.querySelector(
                            '[aria-controls="' + node.id + '"], a[href="#' + node.id + '"]'
                        );

                        if (toggle) toggle.click();
                    }

                    node = node.parentElement;
                }
            """, element)

            return self.wait.until(
                EC.visibility_of_element_located(locator)
            )

        def safe_click(self, element):
            self.driver.execute_script("arguments[0].scrollIntoView({block:'center'});", element)
            try:
                element.click()
            except ElementClickInterceptedException:
                self.driver.execute_script("arguments[0].click();", element)
        def open_form(self):
            self.driver.get(add_user_url)
            self.visible("username")

        def select_value(self, key, expected):
            element = self.visible(key)
            select = Select(element)
            options = [(normalize(o.text), o.get_attribute("value")) for o in select.options]
            wanted = normalize(expected).casefold()
            exact = next((o for o in select.options if normalize(o.text).casefold() == wanted), None)
            if exact is None:
                # Moodle wording can vary slightly by version/language. Match a unique semantic label.
                aliases = {
                    "allow everyone to see my email address": ("everyone", "email"),
                    "everyone can see my email address": ("everyone", "email"),
                    "vietnam": ("vietnam", "viet nam"),
                    "english (en)": ("english",),
                    "no login": ("no login",),
                }
                terms = aliases.get(wanted, (wanted,))
                candidates = [o for o in select.options
                              if all(term in normalize(o.text).casefold() for term in terms)]
                if len(candidates) == 1:
                    exact = candidates[0]
                else:
                    by_value = next((o for o in select.options
                                     if normalize(o.get_attribute("value")).casefold() == wanted), None)
                    if by_value is not None:
                        exact = by_value
            if exact is None:
                available = [f"{text!r} (value={value!r})" for text, value in options]
                raise AssertionError(
                    f"Cannot select '{expected}' in '{key}'. Available options: " + ", ".join(available[:30])
                )
            select.select_by_value(exact.get_attribute("value"))

        def fill_password(self, value):
            password_locator = locators["password"]

            edit_locator = locators.get(
                "password_edit",
                (By.CSS_SELECTOR, 'a[data-passwordunmask="edit"]')
            )

            # Mở vùng nhập mật khẩu của Moodle.
            edit_button = self.wait.until(
                EC.element_to_be_clickable(edit_locator)
            )
            self.safe_click(edit_button)

            # Chờ ô nhập mật khẩu thực sự hiển thị.
            password_input = self.wait.until(
                EC.visibility_of_element_located(password_locator)
            )

            password_input.clear()
            password_input.send_keys(value)

            # Moodle lưu giá trị mật khẩu khi nhấn Enter.
            password_input.send_keys(Keys.ENTER)

        def fill_text_field(self, key, value):
            if key == "password":
                self.fill_password(value)
                return

            if key == "description":
                field = self.wait.until(
                    EC.presence_of_element_located(locators[key])
                )

                self.driver.execute_script("""
                    const field = arguments[0];
                    const value = arguments[1];
                    const tiny = window.tinymce || window.tinyMCE;
                    const editor = tiny && tiny.get ? tiny.get(field.id) : null;

                    if (editor) {
                        editor.setContent(value);
                        editor.save();
                    } else {
                        const editable =
                            document.getElementById(field.id + '_editoreditable')
                            || field.parentElement.querySelector('[contenteditable="true"]');

                        if (editable) {
                            editable.innerText = value;
                        }

                        field.value = value;
                        field.dispatchEvent(new Event('input', {bubbles: true}));
                        field.dispatchEvent(new Event('change', {bubbles: true}));
                    }
                """, field, str(value))

                return

            element = self.visible(key)
            element.clear()

            if value:
                element.send_keys(value)

        def fill_data(self, row, omitted_fields=()):
            omitted = set(omitted_fields)
            for key in SELECT_FIELDS:
                value = (row.get(key) or "").strip()
                if value and key not in omitted:
                    self.select_value(key, value)
            for key in CHECKBOX_FIELDS:
                value = (row.get(key) or "").strip().lower()
                if value and key not in omitted:
                    element = self.visible(key)
                    checked = value in ("true", "1", "yes")
                    if element.is_selected() != checked:
                        self.safe_click(element)
            for key in INPUT_FIELDS:
                value = row.get(key) or ""
                if key in omitted or not value:
                    continue
                if key == "password" and (
                    (row.get("auth") or "").strip().lower() == "no login"
                    or (row.get("generatepassword") or "").strip().lower() == "true"
                ):
                    continue
                if key == "interests":
                    element = self.visible("interests")

                    for interest in value.split("|"):
                        interest = interest.strip()

                        if interest:
                            element.send_keys(interest)
                            element.send_keys(Keys.ENTER)
                else:
                    self.fill_text_field(key, value)
            picture = (row.get("newpicture") or "").strip()
            if picture and "newpicture" not in omitted:
                self.upload_picture(picture)

        
        def upload_picture(self, relative_path):
            file_path = (root / relative_path).resolve()

            if not file_path.is_file():
                raise FileNotFoundError(
                    f"Picture fixture not found: {file_path}"
                )

            # Tìm input file hiện có.
            file_locator = locators.get(
                "newpicture",
                (By.CSS_SELECTOR, 'input[type="file"]')
            )

            inputs = self.driver.find_elements(*file_locator)

            # Nếu chưa có input file, thử mở File picker.
            if not inputs:
                add_locator = locators.get(
                    "newpicture_add",
                    (
                        By.CSS_SELECTOR,
                        ".fp-btn-add, "
                        "[data-action='add-file'], "
                        "button[title*='Add'], "
                        "a[title*='Add']"
                    )
                )

                buttons = self.driver.find_elements(*add_locator)

                if buttons:
                    self.safe_click(buttons[0])

                # Chờ input file xuất hiện.
                self.wait.until(
                    lambda d: any(
                        element.is_displayed()
                        or element.get_attribute("type") == "file"
                        for element in d.find_elements(*file_locator)
                    )
                )

                inputs = self.driver.find_elements(*file_locator)

            if not inputs:
                raise AssertionError(
                    "Moodle File picker không hiển thị input[type='file']."
                )

            # Input file có thể ẩn nhưng Selenium vẫn gửi được đường dẫn.
            inputs[-1].send_keys(str(file_path))

            filename = file_path.name

            if file_path.suffix.lower() == ".txt":
                # Chờ Moodle xử lý tệp không hợp lệ.
                try:
                    WebDriverWait(self.driver, 5).until(
                        lambda d: (
                            filename in d.page_source
                            or d.find_elements(
                                By.CSS_SELECTOR,
                                ".alert-danger, [role='alert']"
                            )
                        )
                    )
                except TimeoutException:
                    pass

                # Không cho phép file .txt được gắn làm ảnh đại diện.
                self.assertNotIn(
                    filename,
                    self.driver.find_element(
                        *locators["body"]
                    ).text,
                    "Invalid file was attached to the profile picture."
                )
            else:
                self.wait.until(
                    lambda d: filename in d.page_source
                )

        def assert_expected_lengths(self, row):
            for key, expected in parse_pairs(row.get("expected_lengths")):
                element = self.visible(key)
                actual = element.get_attribute("value") or ""
                self.assertEqual(len(actual), int(expected),
                                 f"{row['test_case_id']}: {key} should contain {expected} characters, got {len(actual)}.")

        def submit(self):
            self.safe_click(self.visible("save"))

        def assert_validation_errors(self, row):
            pairs = parse_pairs(row.get("expected_errors"))

            # Lấy nội dung thông báo hiển thị trên form.
            body = normalize(
                self.driver.find_element(By.TAG_NAME, "body").text
            ).casefold()

            # Kiểm tra từng thông báo lỗi mong đợi.
            for key, expected in pairs:
                self.assertIn(
                    expected.casefold(),
                    body,
                    f"{row['test_case_id']}: "
                    f"Không tìm thấy lỗi '{expected}' cho field '{key}'."
                )

            # Đảm bảo Moodle vẫn ở trang tạo user.
            self.assertIn(
                "/user/editadvanced.php",
                self.driver.current_url,
                f"{row['test_case_id']}: "
                "Moodle không giữ người dùng ở form tạo user sau validation."
            )
        def assert_user_created(self, row, start_url):
            # 1. Kiểm tra URL có thay đổi sau khi submit hay không.
            try:
                self.wait.until(lambda d: d.current_url != start_url)
                return
            except TimeoutException:
                pass

            # 2. Kiểm tra thông báo thành công.
            success_selectors = [
                ".alert-success",
                ".toast-success",
                "[data-region='notification']",
                ".notification-area .alert",
            ]

            success_keywords = (
                "changes saved",
                "user created",
                "user added",
                "user has been created",
                "user has been added",
            )

            for selector in success_selectors:
                messages = self.driver.find_elements(By.CSS_SELECTOR, selector)

                for message in messages:
                    if message.is_displayed():
                        message_text = normalize(message.text).casefold()

                        if any(keyword in message_text for keyword in success_keywords):
                            return

            # 3. Nếu không có thông báo, kiểm tra nội dung trang.
            body = normalize(
                self.driver.find_element(By.TAG_NAME, "body").text
            ).casefold()

            if any(keyword in body for keyword in success_keywords):
                return

            raise AssertionError(
                f"{row['test_case_id']}: Không xác nhận được Moodle đã tạo user. "
                f"URL={self.driver.current_url}; "
                f"page text={body[:1000]!r}"
            )
        
        def exercise(self, row):
            self.open_form()
            action = (row.get("action") or "save").strip().lower()
            if action == "repair":
                required = {"username", "firstname", "lastname", "email"}

                # Lần 1: bỏ trống các trường bắt buộc.
                self.fill_data(row, omitted_fields=required)
                self.submit()

                # Kiểm tra thông báo validation.
                self.assert_validation_errors(row)

                # Lần 2: chỉ nhập lại bốn trường bắt buộc.
                for key in ("username", "firstname", "lastname", "email"):
                    self.fill_text_field(key, row.get(key, ""))

                # Nhập lại mật khẩu nếu Moodle yêu cầu.
                self.fill_password(row["password"])

                start = self.driver.current_url
                self.submit()
                self.assert_user_created(row, start)
                return
            self.fill_data(row)
            self.assert_expected_lengths(row)
            if action == "cancel":
                self.safe_click(self.visible("cancel"))
                self.wait.until(lambda d: "/user/editadvanced.php" not in d.current_url)
                return
            if action == "upload_invalid":
                # Upload test is intentionally non-submitting: an invalid image must not be attached.
                return
            start = self.driver.current_url
            self.submit()
            if row.get("expected_status", "").strip().lower() == "validation":
                self.assert_validation_errors(row)
            else:
                self.assert_user_created(row, start)

        def record_result(self, row, status, error=""):
            screenshot = ""
            if status in ("FAIL", "ERROR"):
                try:
                    artifact_dir = root / "test-artifacts"
                    artifact_dir.mkdir(parents=True, exist_ok=True)
                    screenshot_path = artifact_dir / f"{row['test_case_id']}.png"
                    self.driver.save_screenshot(str(screenshot_path))
                    screenshot = str(screenshot_path)
                except WebDriverException:
                    pass
            self.results.append({
                "test_case_id": row["test_case_id"],
                "test_case_name": row["test_case_name"],
                "status": status,
                "actual_url": self.driver.current_url,
                "expected_result": row.get("expected_result", ""),
                "error": error,
                "screenshot": screenshot,
            })

    def make_test(test_row):
        def test(self):
            try:
                self.exercise(test_row)
            except AssertionError as exc:
                self.record_result(test_row, "FAIL", str(exc))
                raise
            except Exception as exc:
                self.record_result(test_row, "ERROR", f"{type(exc).__name__}: {exc}")
                raise
            else:
                self.record_result(test_row, "PASS")
        test.__doc__ = f"{test_row['test_case_id']} - {test_row['test_case_name']}"
        return test

    for row in rows:
        name = "test_" + re.sub(r"\W+", "_", row["test_case_id"])
        setattr(AddNewUserTests, name, make_test(row))

    suite = unittest.defaultTestLoader.loadTestsFromTestCase(AddNewUserTests)
    result = unittest.TextTestRunner(
        stream=sys.stdout,
        verbosity=1
    ).run(suite)
    result_file.parent.mkdir(parents=True, exist_ok=True)
    with result_file.open("w", encoding="utf-8-sig", newline="") as output:
        columns = ["test_case_id", "test_case_name", "status", "actual_url", "expected_result", "error", "screenshot"]
        writer = csv.DictWriter(output, fieldnames=columns)
        writer.writeheader()
        writer.writerows(AddNewUserTests.results)
    print(f"\nResult file: {result_file}")
    return 0 if result.wasSuccessful() else 1

