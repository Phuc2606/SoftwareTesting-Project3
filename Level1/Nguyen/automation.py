"""Level 1 – Data-driven automation cho Moodle Feature 005 – Add a new course.

Các test case của Project 2 chỉ khác nhau về dữ liệu được gom thành 3 nhóm (cột `group` trong test_data.csv):
  fields   (29 TC) : Full name / Short name / ID number / Category      -> run_fields
  dates    (11 TC) : Start date / End date                              -> run_dates
  settings (21 TC) : dropdown cài đặt nâng cao (format, group mode...)  -> run_settings
Mỗi dòng của test_data.csv (gồm cả cột Expected Result: expected_result, expected_text, expected_error_*,
verify*_value ...) sinh ra đúng 1 test case. URL và locator được khai báo trực tiếp trong script.

Chạy:  python Level1/Member5/automation.py [--list] [--case TC-005-001] [--browser chrome|edge|firefox] [--headless]
Cần: Moodle đang chạy, dữ liệu Moodle sạch (chưa có các course test), biến môi trường MOODLE_BASE_URL /
MOODLE_USERNAME / MOODLE_PASSWORD (mặc định http://127.0.0.1:9501, admin / admin).
"""

import argparse
import csv
import fnmatch
import os
import platform
import re
import sys
import time
import unittest
from datetime import datetime
from pathlib import Path

from selenium import webdriver
from selenium.common.exceptions import (ElementClickInterceptedException,
                                        ElementNotInteractableException, TimeoutException)
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select, WebDriverWait

HERE = Path(__file__).resolve().parent
BASE_URL = os.environ.get("MOODLE_BASE_URL", "http://127.0.0.1:9501").rstrip("/")
USERNAME = os.environ.get("MOODLE_USERNAME", "admin")
PASSWORD = os.environ.get("MOODLE_PASSWORD", "admin")
TIMEOUT_SECONDS = 10      # thời gian chờ tối đa khi tìm phần tử / tải trang
NAV_TIMEOUT_SECONDS = 5   # thời gian chờ tối đa sau khi click để thấy trang tải lại
LONG_TEXT = 50            # chuỗi >= 50 ký tự được gán bằng JavaScript (như lệnh `type` của Katalon, bỏ qua maxlength)
OPTIONS = {"browser": "chrome", "headless": False}
# Giống lệnh runScript của Katalon: mở các mục thu gọn của form (Expand all)
EXPAND_ALL_JS = ("document.querySelectorAll('a.collapseexpand').forEach(function(a){ "
                 "if(a.textContent.trim()=='Expand all'){ a.click(); } });")


# ---------------------------------------------------------------- dữ liệu / so khớp (không cần trình duyệt)
def read_csv(path):
    with open(path, encoding="utf-8-sig", newline="") as source:
        return [row for row in csv.DictReader(source) if row]


def expand_macros(text):
    """'@repeat(a,1333)' -> chuỗi gồm 1333 ký tự 'a' (để file CSV không phải chứa chuỗi dài)."""
    return re.sub(r"@repeat\((.),(\d+)\)", lambda m: m.group(1) * int(m.group(2)), text or "")


def subst_vars(text, variables):
    """Thay ${ten_bien} bằng giá trị trong dict `variables`."""
    return re.sub(r"\$\{(\w+)\}", lambda m: str(variables[m.group(1)]), text or "")


def glob_match(actual, pattern):
    """'glob:*abc*' (ký tự đại diện), 'regexp:...' hoặc chuỗi thường (khớp tuyệt đối) - như Katalon."""
    if pattern.startswith("glob:"):
        return fnmatch.fnmatchcase(actual, pattern[5:])
    if pattern.startswith("regexp:"):
        return re.fullmatch(pattern[7:], actual, re.S) is not None
    return actual == pattern


def parse_locator(locator):
    """'id=abc' | 'name=..' | 'xpath=..' | 'css=..' | 'link=..' -> (By, giá trị)."""
    kinds = {"id": By.ID, "name": By.NAME, "xpath": By.XPATH, "css": By.CSS_SELECTOR, "link": By.LINK_TEXT}
    match = re.match(r"(id|name|xpath|css|link)=(.*)", locator, re.S)
    if match:
        return kinds[match.group(1)], match.group(2)
    return (By.XPATH, locator) if locator.startswith("//") else (By.ID, locator)


# ---------------------------------------------------------------- thao tác Selenium
def make_driver():
    browser, headless = OPTIONS["browser"], OPTIONS["headless"]
    if browser == "firefox":
        opts = webdriver.FirefoxOptions()
        if headless:
            opts.add_argument("-headless")
        driver = webdriver.Firefox(options=opts)
    elif browser == "edge":
        opts = webdriver.EdgeOptions()
        if headless:
            opts.add_argument("--headless=new")
        opts.add_argument("--window-size=1400,1000")
        driver = webdriver.Edge(options=opts)
    else:
        opts = webdriver.ChromeOptions()
        if headless:
            opts.add_argument("--headless=new")
        opts.add_argument("--window-size=1400,1000")
        driver = webdriver.Chrome(options=opts)
    driver.set_window_size(1400, 1000)
    return driver


def find(driver, locator):
    by, value = parse_locator(locator)
    return WebDriverWait(driver, TIMEOUT_SECONDS).until(EC.presence_of_element_located((by, value)))


def login(driver, login_path="/login/index.php"):
    driver.get(BASE_URL + login_path)
    find(driver, "id=username").send_keys(USERNAME)
    find(driver, "id=password").send_keys(PASSWORD)
    find(driver, "id=loginbtn").click()
    WebDriverWait(driver, TIMEOUT_SECONDS).until(lambda d: "/login/" not in d.current_url)


def safe_click(driver, element):
    try:
        element.click()
    except (ElementClickInterceptedException, ElementNotInteractableException):
        driver.execute_script("arguments[0].click();", element)   # nút bị footer/thanh công cụ che


def wait_page_loaded(driver, old_html):
    """Chờ trang tải lại: phần tử <html> cũ bị thay (tối đa NAV_TIMEOUT_SECONDS) rồi readyState = complete."""
    try:
        WebDriverWait(driver, NAV_TIMEOUT_SECONDS).until(EC.staleness_of(old_html))
    except TimeoutException:
        pass   # form bị chặn ở phía trình duyệt (không tải lại trang)
    WebDriverWait(driver, TIMEOUT_SECONDS).until(
        lambda d: d.execute_script("return document.readyState") == "complete")


def click_and_wait(driver, element):
    """Tương đương clickAndWait của Katalon."""
    old_html = driver.find_element(By.TAG_NAME, "html")
    safe_click(driver, element)
    wait_page_loaded(driver, old_html)


def set_text(driver, element, value):
    """Điền giá trị. Chuỗi dài -> gán bằng JS (bỏ qua maxlength, giống Katalon); TinyMCE -> gõ vào thân editor."""
    if element.get_attribute("contenteditable") == "true":
        try:
            element.click()
        except (ElementClickInterceptedException, ElementNotInteractableException):
            driver.execute_script("arguments[0].focus();", element)
        mod = Keys.COMMAND if platform.system() == "Darwin" else Keys.CONTROL
        element.send_keys(mod, "a")
        element.send_keys(value)
    elif len(value) >= LONG_TEXT:
        driver.execute_script(
            "var e=arguments[0]; e.value=arguments[1];"
            "e.dispatchEvent(new Event('input',{bubbles:true}));"
            "e.dispatchEvent(new Event('change',{bubbles:true}));", element, value)
    else:
        element.clear()
        if value:
            element.send_keys(value)


def select_option(element, spec):
    """spec: 'label=January' | 'value=weeks' | 'index=2' | 'January' (mặc định theo label).
    Dropdown đang bị ẩn (mục thu gọn) -> đặt giá trị bằng JavaScript rồi phát sự kiện 'change'."""
    match = re.match(r"(label|value|index)=(.*)", spec, re.S)
    kind, value = (match.group(1), match.group(2)) if match else ("label", spec)
    try:
        chooser = Select(element)
        if kind == "value":
            chooser.select_by_value(value)
        elif kind == "index":
            chooser.select_by_index(int(value))
        else:
            chooser.select_by_visible_text(value)
    except ElementNotInteractableException:
        found = element.parent.execute_script(
            "var s=arguments[0], v=arguments[1], by=arguments[2];"
            "for (var i=0;i<s.options.length;i++){var o=s.options[i];"
            " var k = by=='value' ? o.value : (by=='index' ? String(i) : o.text.trim());"
            " if (k===v){ s.selectedIndex=i; s.dispatchEvent(new Event('change',{bubbles:true})); return true; } }"
            "return false;", element, value, kind)
        if not found:
            raise AssertionError("Không có tuỳ chọn %s=%r trong dropdown" % (kind, value))


def select_and_wait(driver, element, spec):
    """Chọn dropdown rồi chờ trang tải lại (selectAndWait của Katalon) - dùng cho ô Format."""
    old_html = driver.find_element(By.TAG_NAME, "html")
    select_option(element, spec)
    wait_page_loaded(driver, old_html)


def set_checkbox(driver, element, checked):
    if element.is_selected() != checked:
        safe_click(driver, element)


def text_present(driver, text):
    """Văn bản có trong trang không (chữ nhìn thấy, hoặc textContent của <body>)."""
    body = driver.find_element(By.TAG_NAME, "body")
    return text in body.text or text in (body.get_attribute("textContent") or "")


def expand_all(driver):
    """Bấm 'Expand all' rồi chờ (tối đa 3 giây) tới khi các mục nâng cao hiển thị."""
    driver.execute_script(EXPAND_ALL_JS)
    end = time.time() + 3
    while time.time() < end:
        if driver.execute_script("var e=document.getElementById('id_format');return !!(e && e.offsetParent);"):
            return
        time.sleep(0.2)


def form_errors(driver):
    """Các thông báo lỗi đang hiển thị trên form (ghi vào thông báo khi test Fail)."""
    return driver.execute_script(
        "return Array.from(document.querySelectorAll('.invalid-feedback, .alert-danger, .alert-warning'))"
        ".map(function(e){return (e.id? e.id+': ':'')+e.textContent.trim();})"
        ".filter(function(t){return t.length>0 && !/^[a-z_]+: $/.test(t);});")


# ---------------------------------------------------------------- chạy và ghi kết quả
def add_common_arguments(parser):
    parser.add_argument("--browser", choices=("chrome", "edge", "firefox"), default="chrome")
    parser.add_argument("--headless", action="store_true", help="Chạy ẩn trình duyệt (mặc định: hiện cửa sổ)")


class RecordingResult(unittest.TextTestResult):
    """Như TextTestResult nhưng ghi lại PASS/FAIL/ERROR của từng test case để xuất file CSV."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.rows = []

    @staticmethod
    def _case_id(test):
        return test._testMethodName[5:].replace("_", "-")

    def addSuccess(self, test):
        super().addSuccess(test)
        self.rows.append((self._case_id(test), "PASS", ""))

    def addFailure(self, test, err):
        super().addFailure(test, err)
        self.rows.append((self._case_id(test), "FAIL", str(err[1]).replace("\n", " ")[:300]))

    def addError(self, test, err):
        super().addError(test, err)
        self.rows.append((self._case_id(test), "ERROR", ("%s: %s" % (err[0].__name__, err[1])).replace("\n", " ")[:300]))


def run_suite(suite, results_file):
    result = unittest.TextTestRunner(stream=sys.stdout, verbosity=2, resultclass=RecordingResult).run(suite)
    results_file.parent.mkdir(exist_ok=True)
    with open(results_file, "w", encoding="utf-8-sig", newline="") as target:
        writer = csv.writer(target)
        writer.writerow(["test_case_id", "result", "detail"])
        writer.writerows(sorted(result.rows))
    print("Đã ghi kết quả: %s" % results_file)
    return 0 if result.wasSuccessful() else 1

DATA_FILE = HERE / "test_data.csv"
RESULTS_FILE = HERE / "results" / "latest_results.csv"
ADD_URL = BASE_URL + "/course/edit.php?category=0"
MANAGE_SEARCH = BASE_URL + "/course/management.php?search="
VIEW_PATTERN = "glob:*course/view.php?id=*"
EDIT_PATTERN = "glob:*course/edit.php*"
GROUPS = {"fields", "dates", "settings"}
REQUIRED_COLUMNS = {"test_case_id", "test_case_name", "group", "expected_result"}


def read_cases(path=DATA_FILE):
    rows = read_csv(path)
    if not rows or not REQUIRED_COLUMNS.issubset(rows[0]):
        raise ValueError("test_data.csv thiếu cột bắt buộc: " + ", ".join(sorted(REQUIRED_COLUMNS)))
    for row in rows:
        if row["group"] not in GROUPS:
            raise ValueError("%s: group không hợp lệ: %r" % (row["test_case_id"], row["group"]))
    return sorted(rows, key=lambda r: r["test_case_id"])   # TC-001 chạy trước để tạo dữ liệu nền ST101/ID101


class AddCourseLevel1(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.driver = make_driver()
        login(cls.driver)

    @classmethod
    def tearDownClass(cls):
        cls.driver.quit()

    # ---------------------------------------------------------------- tiện ích
    def el(self, locator):
        return find(self.driver, locator)

    def open_form(self):
        self.driver.get(ADD_URL)
        self.el("id=id_fullname")

    def type_into(self, field_id, value):
        set_text(self.driver, self.el("id=" + field_id), expand_macros(value))

    def select(self, field_id, spec):
        select_option(self.el("id=" + field_id), spec)

    def save(self):
        click_and_wait(self.driver, self.el("id=id_saveanddisplay"))

    def value_of(self, field_id):
        return self.el("id=" + field_id).get_attribute("value")

    def edit_url(self):
        return self.driver.current_url.replace("view.php", "edit.php")

    def fill_names(self, row):
        for column in ("fullname", "shortname", "idnumber"):
            if row.get(column, "") != "":
                self.type_into("id_" + column, row[column])

    # ---------------------------------------------------------------- đối chiếu Expected Result
    def check_expected(self, row):
        driver, url = self.driver, self.driver.current_url
        if row["expected_result"] == "SUCCESS":
            self.assertTrue(glob_match(url, VIEW_PATTERN),
                            "Phải chuyển sang course/view.php nhưng URL = %s. Lỗi trên form: %s" % (url, form_errors(driver)))
        else:
            self.assertTrue(glob_match(url, EDIT_PATTERN), "Phải ở lại course/edit.php nhưng URL = " + url)
        for column, pattern in row.items():
            if column.startswith("expected_error_") and pattern:
                field = column[len("expected_error_"):]
                actual = self.el("id=id_error_" + field).text.strip()
                self.assertTrue(glob_match(actual, pattern),
                                "Lỗi tại '%s': mong đợi %r, thực tế %r" % (field, pattern, actual))
        if row.get("expected_text"):
            self.assertTrue(text_present(driver, row["expected_text"]), "Không thấy văn bản: %r" % row["expected_text"])
        if row.get("expected_fullname_len"):
            driver.get(self.edit_url())
            self.assertEqual(int(row["expected_fullname_len"]), len(self.value_of("id_fullname")))

    # ---------------------------------------------------------------- Nhóm 1: ô nhập văn bản + category
    def run_fields(self, row):
        self.open_form()
        self.fill_names(row)
        if row["clear_category"] == "Y":   # bấm dấu × cạnh 'Category 1'
            safe_click(self.driver, self.el("xpath=//span[starts-with(@id,'form_autocomplete_selection')]/span"))
        self.save()
        self.check_expected(row)

    # ---------------------------------------------------------------- Nhóm 2: ngày bắt đầu / kết thúc
    def run_dates(self, row):
        self.open_form()
        self.fill_names(row)
        for part in ("month", "year", "day", "hour", "minute"):   # chọn tháng, năm trước ngày
            if row["start_" + part]:
                self.select("id_startdate_" + part, row["start_" + part])
        if row["check_start_day_after"]:   # TC-025: 31 Feb tự chuẩn hóa thành 3 / March
            self.assertEqual(row["check_start_day_after"], self.value_of("id_startdate_day"))
            self.assertEqual(row["check_start_month_after"], self.value_of("id_startdate_month"))
        if row["end_enabled"] == "N":
            set_checkbox(self.driver, self.el("id=id_enddate_enabled"), False)
        else:
            for part in ("month", "year", "day", "hour", "minute"):
                if row["end_" + part]:
                    self.select("id_enddate_" + part, row["end_" + part])
        self.save()
        self.check_expected(row)

    # ---------------------------------------------------------------- Nhóm 3: cài đặt nâng cao (dropdown)
    def run_settings(self, row):
        self.open_form()
        expand_all(self.driver)
        for i in ("1", "2"):
            field_id, value = row["setting%s_id" % i], row["setting%s_value" % i]
            if field_id == "id_format":   # đổi Format làm form tải lại -> chọn Format trước khi nhập tên
                select_and_wait(self.driver, self.el("id=" + field_id), "value=" + value)
            elif field_id:
                self.select(field_id, "value=" + value)
        self.fill_names(row)
        self.save()
        if row["verify_mode"] == "manage_search":
            self.driver.get(MANAGE_SEARCH + row["shortname"])
            self.assertTrue(text_present(self.driver, row["expected_text"]), "Không thấy: %r" % row["expected_text"])
            return
        self.assertTrue(glob_match(self.driver.current_url, VIEW_PATTERN),
                        "URL = %s. Lỗi trên form: %s" % (self.driver.current_url, form_errors(self.driver)))
        self.driver.get(self.edit_url())   # mở Edit settings để kiểm tra giá trị đã lưu
        for i in ("1", "2"):
            field_id, expected = row["verify%s_id" % i], row["verify%s_value" % i]
            if field_id:
                self.assertEqual(expected, self.value_of(field_id), "Giá trị đã lưu của %s" % field_id)


def make_test(row):
    def test(self):
        getattr(self, "run_" + row["group"])(row)
    test.__doc__ = "%s - %s" % (row["test_case_id"], row["test_case_name"])
    return test


def main():
    parser = argparse.ArgumentParser(description="Moodle Add a new course - Level 1 (data-driven)")
    parser.add_argument("--list", action="store_true", help="Liệt kê test case, không mở trình duyệt")
    parser.add_argument("--case", action="append", help="Chạy riêng test case theo ID (có thể lặp lại)")
    add_common_arguments(parser)
    args = parser.parse_args()

    cases = read_cases()
    if args.case:
        wanted = set(args.case)
        unknown = wanted - {row["test_case_id"] for row in cases}
        if unknown:
            parser.error("Không có test case: " + ", ".join(sorted(unknown)))
        cases = [row for row in cases if row["test_case_id"] in wanted]
    if args.list:
        for row in cases:
            print("%s  [%s]  %s" % (row["test_case_id"], row["group"], row["test_case_name"]))
        return 0

    OPTIONS.update(browser=args.browser, headless=args.headless)
    for row in cases:
        setattr(AddCourseLevel1, "test_" + row["test_case_id"].replace("-", "_"), make_test(row))
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(AddCourseLevel1)
    return run_suite(suite, RESULTS_FILE)


if __name__ == "__main__":
    sys.exit(main())
