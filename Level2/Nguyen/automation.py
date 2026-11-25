"""Level 2 – Data-driven + keyword-driven cho Moodle Feature 005 – Add a new course.

Script KHÔNG chứa sẵn URL, locator hay dữ liệu kiểm thử. Tất cả được cung cấp qua file:
  test_data.csv   : các bước của 67 test case (test_case_id, test_case_name, step_no, keyword, target, value)
  test_config.csv : item_type,key,by,value - URL của trang (url) và phần tử giao diện (element: ô nhập, nút, liên kết...)
Từ khóa dùng đúng tên lệnh Katalon (open, type, select, selectAndWait, click, clickAndWait, check, uncheck, runScript,
selectFrame, storeEval, storeLocation, echo, verifyLocation, verifyText, verifyValue, verifyTextPresent,
verifyTextNotPresent, verifyEval); biến dùng cú pháp ${ten_bien}.

Chạy:  python Level2/Member5/automation.py [--list] [--case TC-005-001] [--browser chrome|edge|firefox] [--headless]
Cần: Moodle đang chạy, dữ liệu Moodle sạch, biến môi trường MOODLE_BASE_URL / MOODLE_USERNAME / MOODLE_PASSWORD.
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
CONFIG_FILE = HERE / "test_config.csv"
RESULTS_FILE = HERE / "results" / "latest_results.csv"
REQUIRED_DATA_COLUMNS = {"test_case_id", "test_case_name", "step_no", "keyword", "target", "value"}
REQUIRED_CONFIG_COLUMNS = {"item_type", "key", "by", "value"}
BY_PREFIX = {"id": "id", "name": "name", "xpath": "xpath", "css selector": "css", "link text": "link"}
# Từ khóa mà `target` là tên URL / tên phần tử trong test_config.csv
RESOLVE_TARGET = {"open", "type", "select", "selectandwait", "click", "clickandwait", "check", "uncheck",
                  "verifytext", "verifyvalue", "verifylocation"}


def load_config(path=CONFIG_FILE):
    rows = read_csv(path)
    if not rows or not REQUIRED_CONFIG_COLUMNS.issubset(rows[0]):
        raise ValueError("test_config.csv thiếu cột bắt buộc: " + ", ".join(sorted(REQUIRED_CONFIG_COLUMNS)))
    urls, elements = {}, {}
    for row in rows:
        if row["item_type"] == "url":
            urls[row["key"]] = row["value"]
        elif row["item_type"] == "element":
            if row["by"] not in BY_PREFIX:
                raise ValueError("%s: kiểu locator không hợp lệ: %r" % (row["key"], row["by"]))
            elements[row["key"]] = "%s=%s" % (BY_PREFIX[row["by"]], row["value"])
        else:
            raise ValueError("item_type không hợp lệ: %r" % row["item_type"])
    return urls, elements


def load_testcases(path=DATA_FILE):
    rows = read_csv(path)
    if not rows or not REQUIRED_DATA_COLUMNS.issubset(rows[0]):
        raise ValueError("test_data.csv thiếu cột bắt buộc: " + ", ".join(sorted(REQUIRED_DATA_COLUMNS)))
    cases = {}
    for row in rows:
        case = cases.setdefault(row["test_case_id"], {"name": row["test_case_name"], "steps": []})
        case["steps"].append(row)
    for case in cases.values():
        case["steps"].sort(key=lambda step: int(step["step_no"]))
    return dict(sorted(cases.items()))


class KeywordRunner:
    """Thực thi từng bước (keyword, target, value) của một test case."""
    def __init__(self, driver, urls, elements):
        self.driver, self.urls, self.elements = driver, urls, elements
        self.vars = {"base_url": BASE_URL}

    def _sub(self, text):
        return subst_vars(text, self.vars)

    def _target(self, keyword, target):
        if keyword not in RESOLVE_TARGET:
            return self._sub(target)
        if target in self.urls:
            return BASE_URL + self.urls[target]
        return self._sub(self.elements.get(target, target))

    def _el(self, locator):
        return find(self.driver, locator)

    def run_steps(self, steps):
        for step in steps:
            keyword = step["keyword"].strip().lower()
            action = getattr(self, "kw_" + keyword, None)
            if action is None:
                raise ValueError("Từ khóa chưa hỗ trợ: %s" % step["keyword"])
            action(self._target(keyword, step["target"]), self._sub(step["value"]))

    # ---- hành động
    def kw_open(self, target, value):                      # value (nếu có) nối vào URL, vd ?search=<mã>
        self.driver.get(target + value)

    def kw_type(self, target, value):
        set_text(self.driver, self._el(target), value)

    def kw_select(self, target, value):
        select_option(self._el(target), value)

    def kw_selectandwait(self, target, value):
        select_and_wait(self.driver, self._el(target), value)

    def kw_click(self, target, value):
        safe_click(self.driver, self._el(target))

    def kw_clickandwait(self, target, value):
        click_and_wait(self.driver, self._el(target))

    def kw_check(self, target, value):
        set_checkbox(self.driver, self._el(target), True)

    def kw_uncheck(self, target, value):
        set_checkbox(self.driver, self._el(target), False)

    def kw_runscript(self, target, value):
        self.driver.execute_script(target)

    def kw_selectframe(self, target, value):               # index=N | relative=top
        kind, _, number = target.partition("=")
        if kind == "relative" and number == "top":
            self.driver.switch_to.default_content()
        else:
            self.driver.switch_to.frame(int(number))

    # ---- biến
    def kw_storeeval(self, target, value):                 # target = biểu thức JS, value = tên biến
        self.vars[value] = self.driver.execute_script("return " + target)

    def kw_storelocation(self, target, value):             # target = tên biến
        self.vars[target] = self.driver.current_url

    def kw_echo(self, target, value):
        print("  [echo]", target)

    # ---- kiểm tra (Expected Result)
    def kw_verifylocation(self, target, value):
        url = self.driver.current_url
        assert glob_match(url, target), "verifyLocation: mong đợi %r, thực tế %r" % (target, url)

    def kw_verifytext(self, target, value):
        text = self._el(target).text.strip()
        assert glob_match(text, value), "verifyText %s: mong đợi %r, thực tế %r" % (target, value, text)

    def kw_verifyvalue(self, target, value):
        actual = self._el(target).get_attribute("value")
        assert actual == value, "verifyValue %s: mong đợi %r, thực tế %r" % (target, value, actual)

    def kw_verifytextpresent(self, target, value):
        assert text_present(self.driver, target), "verifyTextPresent: không thấy %r" % target

    def kw_verifytextnotpresent(self, target, value):
        assert not text_present(self.driver, target), "verifyTextNotPresent: vẫn thấy %r" % target

    def kw_verifyeval(self, target, value):
        actual = str(self.driver.execute_script("return " + target))
        assert actual == value, "verifyEval %s: mong đợi %r, thực tế %r" % (target, value, actual)


URLS, ELEMENTS = {}, {}


class AddCourseLevel2(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.driver = make_driver()
        login(cls.driver, URLS.get("login_path", "/login/index.php"))

    @classmethod
    def tearDownClass(cls):
        cls.driver.quit()


def make_test(case_id, case):
    def test(self):
        runner = KeywordRunner(self.driver, URLS, ELEMENTS)   # mỗi TC có bộ biến riêng
        try:
            runner.run_steps(case["steps"])
        finally:
            self.driver.switch_to.default_content()            # phòng khi TC dừng giữa chừng trong iframe
    test.__doc__ = "%s - %s" % (case_id, case["name"])
    return test


def main():
    parser = argparse.ArgumentParser(description="Moodle Add a new course - Level 2 (keyword-driven)")
    parser.add_argument("--list", action="store_true", help="Liệt kê test case, không mở trình duyệt")
    parser.add_argument("--case", action="append", help="Chạy riêng test case theo ID (có thể lặp lại)")
    add_common_arguments(parser)
    args = parser.parse_args()

    URLS.update(load_config()[0])
    ELEMENTS.update(load_config()[1])
    cases = load_testcases()
    if args.case:
        unknown = set(args.case) - set(cases)
        if unknown:
            parser.error("Không có test case: " + ", ".join(sorted(unknown)))
        cases = {key: value for key, value in cases.items() if key in args.case}
    if args.list:
        for case_id, case in cases.items():
            print("%s  (%d bước)  %s" % (case_id, len(case["steps"]), case["name"]))
        return 0

    OPTIONS.update(browser=args.browser, headless=args.headless)
    for case_id, case in cases.items():
        setattr(AddCourseLevel2, "test_" + case_id.replace("-", "_"), make_test(case_id, case))
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(AddCourseLevel2)
    return run_suite(suite, RESULTS_FILE)


if __name__ == "__main__":
    sys.exit(main())
