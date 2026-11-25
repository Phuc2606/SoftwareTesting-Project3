"""Non-functional #2 – SECURITY (kiểm thử bảo mật đầu vào) của form "Add a new course".

Loại kiểm thử : Security testing - input validation / output encoding (XSS, HTML injection, SQL injection).
Cách tiếp cận : Mỗi payload (xem PAYLOADS) được đưa vào 1 trường (full name / short name / ID number), các trường khác
                dùng dữ liệu hợp lệ. Sau khi bấm Save:
                  1. KHÔNG có hộp thoại alert() nào xuất hiện (script không được thực thi) - trên trang kết quả
                     và trên trang Manage courses (nơi course được liệt kê).
                  2. Payload chứa thẻ HTML (check_raw=True): chuỗi nguyên bản KHÔNG được xuất hiện trong page_source
                     (phải được mã hóa thành &lt;...&gt;).
                  3. Không lộ thông báo lỗi cơ sở dữ liệu / stack trace (SQL injection).
                Course được tạo (payload lưu như văn bản thường) hoặc bị từ chối đều chấp nhận.
Công cụ       : Selenium WebDriver + unittest. Kết quả: results/latest_results.csv.
Ghi chú       : Chỉ chạy trên môi trường Moodle Docker demo của bài tập, không dùng cho hệ thống thật.

Chạy:  python NonFunctional/Member5/test_security.py [--browser chrome|edge|firefox] [--headless]
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

import uuid
from selenium.common.exceptions import NoAlertPresentException, UnexpectedAlertPresentException

RESULTS_FILE = HERE / "results" / "security_results.csv"
ADD_URL = BASE_URL + "/course/edit.php?category=0"
MANAGE_SEARCH = BASE_URL + "/course/management.php?search="
DB_ERRORS = ("error reading from database", "sqlstate", "stack trace", "fatal error", "debug info:")
# (id, loại, trường, payload, check_raw)
PAYLOADS = [
    ("SEC-01", "XSS", "fullname", "<script>alert('xss1')</script>", True),
    ("SEC-02", "XSS", "fullname", "<img src=x onerror=alert('xss2')>", True),
    ("SEC-03", "XSS", "shortname", "<svg/onload=alert('xss3')>", True),
    ("SEC-04", "XSS", "idnumber", "\"><script>alert('xss4')</script>", True),
    ("SEC-05", "HTML injection", "fullname", "<b>bold</b><a href=\"http://evil.example\">x</a>", True),
    ("SEC-06", "SQL injection", "fullname", "' OR '1'='1' --", False),
    ("SEC-07", "SQL injection", "shortname", "x'; DROP TABLE mdl_course; --", False),
    ("SEC-08", "SQL injection", "idnumber", "1' UNION SELECT username,password FROM mdl_user --", False),
]


class SecurityTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.driver = make_driver()
        login(cls.driver)

    @classmethod
    def tearDownClass(cls):
        cls.driver.quit()

    def alert_text(self):
        """Nội dung alert nếu có (và đóng nó), ngược lại None."""
        try:
            alert = self.driver.switch_to.alert
            text = alert.text
            alert.accept()
            return text
        except NoAlertPresentException:
            return None

    def go(self, url):
        try:
            self.driver.get(url)
        except UnexpectedAlertPresentException:
            pass
        self.assertIsNone(self.alert_text(), "XSS: alert() bị thực thi khi mở " + url)


def make_test(payload):
    payload_id, category, field, text, check_raw = payload

    def test(self):
        driver = self.driver
        uid = uuid.uuid4().hex[:6]
        data = {"fullname": "Sec test " + uid, "shortname": "SEC_" + uid, "idnumber": ""}
        data[field] = text
        self.go(ADD_URL)
        for name in ("fullname", "shortname", "idnumber"):
            if data[name]:
                set_text(driver, find(driver, "id=id_" + name), data[name])
        try:
            click_and_wait(driver, find(driver, "id=id_saveanddisplay"))
        except UnexpectedAlertPresentException:
            self.fail("XSS: alert() bị thực thi sau khi gửi form")
        self.assertIsNone(self.alert_text(), "XSS: alert() bị thực thi sau khi gửi form")
        page_text = driver.find_element(By.TAG_NAME, "body").text.lower()
        if check_raw:
            self.assertNotIn(text, driver.page_source, "Payload xuất hiện nguyên bản (chưa mã hóa) trong HTML")
        for error in DB_ERRORS:
            self.assertNotIn(error, page_text, "Lộ thông báo lỗi hệ thống/CSDL: " + error)
        if "course/view.php" in driver.current_url:   # course được tạo -> kiểm tra thêm nơi nó được liệt kê
            self.go(MANAGE_SEARCH + data["shortname"])
            if check_raw:
                self.assertNotIn(text, driver.page_source, "Payload chưa mã hóa ở trang Manage courses")
    test.__doc__ = "%s (%s) - trường %s" % (payload_id, category, field)
    return test


def main():
    parser = argparse.ArgumentParser(description="Moodle Add a new course - Security")
    add_common_arguments(parser)
    args = parser.parse_args()
    OPTIONS.update(browser=args.browser, headless=args.headless)
    for payload in PAYLOADS:
        setattr(SecurityTest, "test_" + payload[0].replace("-", "_"), make_test(payload))
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(SecurityTest)
    return run_suite(suite, RESULTS_FILE)


if __name__ == "__main__":
    sys.exit(main())
