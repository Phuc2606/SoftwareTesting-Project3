"""Non-functional #1 – PERFORMANCE (thời gian phản hồi) của chức năng "Add a new course".

Loại kiểm thử : Performance testing - đo response time với 1 người dùng.
Cách tiếp cận : Mỗi kịch bản chạy 1 lần khởi động (không tính) + N lần đo (mặc định 10) bằng time.perf_counter():
                  PERF-01 load_form     : driver.get(form Add a new course) - trả về khi sự kiện load của trang xong
                  PERF-02 load_manage   : driver.get(trang Manage courses and categories)
                  PERF-03 create_course : bấm 'Save and display' tới khi course/view.php tải xong
                PASS khi trung bình <= avg tối đa và lần chậm nhất <= max tối đa (xem SCENARIOS).
Công cụ       : Selenium WebDriver + unittest. Kết quả append vào results/performance_results.csv.
Ghi chú       : Mỗi lần create_course tạo 1 course mới (short name PERF_<mã duy nhất>); nên xóa sau khi đo.

Chạy:  python NonFunctional/Member5/test_performance.py [--runs 10] [--browser chrome|edge|firefox] [--headless]
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

import statistics
import uuid

RESULTS_FILE = HERE / "results" / "performance_results.csv"
ADD_URL = BASE_URL + "/course/edit.php?category=0"
MANAGE_URL = BASE_URL + "/course/management.php"
# (id, mô tả, action, avg tối đa (giây), max tối đa (giây))
SCENARIOS = [
    ("PERF-01", "Thời gian tải form 'Add a new course'", "load_form", 3.0, 5.0),
    ("PERF-02", "Thời gian tải trang 'Manage courses and categories'", "load_manage", 3.0, 5.0),
    ("PERF-03", "Thời gian xử lý khi bấm 'Save and display' (tạo course hợp lệ)", "create_course", 5.0, 8.0),
]
RUNS = [10]
MEASURED = []   # dòng kết quả của lần chạy này


class PerformanceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.driver = make_driver()
        login(cls.driver)

    @classmethod
    def tearDownClass(cls):
        cls.driver.quit()

    def measure(self, action):
        driver = self.driver
        if action == "load_form":
            start = time.perf_counter(); driver.get(ADD_URL)
            return time.perf_counter() - start
        if action == "load_manage":
            start = time.perf_counter(); driver.get(MANAGE_URL)
            return time.perf_counter() - start
        if action == "create_course":
            driver.get(ADD_URL)
            code = uuid.uuid4().hex[:8]
            set_text(driver, find(driver, "id=id_fullname"), "Perf course " + code)
            set_text(driver, find(driver, "id=id_shortname"), "PERF_" + code)
            button = find(driver, "id=id_saveanddisplay")
            start = time.perf_counter()
            click_and_wait(driver, button)
            elapsed = time.perf_counter() - start
            self.assertIn("course/view.php", driver.current_url, "Tạo course thất bại khi đo hiệu năng")
            return elapsed
        raise ValueError("action không hỗ trợ: " + action)


def make_test(scenario):
    scenario_id, description, action, max_avg, max_single = scenario

    def test(self):
        self.measure(action)                                  # chạy khởi động, không tính
        times = [self.measure(action) for _ in range(RUNS[0])]
        avg, worst = statistics.mean(times), max(times)
        ok = avg <= max_avg and worst <= max_single
        MEASURED.append([datetime.now().isoformat(timespec="seconds"), scenario_id, RUNS[0], round(min(times), 3),
                         round(avg, 3), round(worst, 3), max_avg, max_single, "PASS" if ok else "FAIL"])
        print("\n  %s: min=%.2fs avg=%.2fs max=%.2fs (giới hạn avg<=%ss, max<=%ss)" % (
            scenario_id, min(times), avg, worst, max_avg, max_single))
        self.assertLessEqual(avg, max_avg, "Thời gian trung bình vượt giới hạn")
        self.assertLessEqual(worst, max_single, "Có lần chạy vượt giới hạn")
    test.__doc__ = "%s - %s" % (scenario_id, description)
    return test


def main():
    parser = argparse.ArgumentParser(description="Moodle Add a new course - Performance")
    parser.add_argument("--runs", type=int, default=10, help="Số lần đo mỗi kịch bản")
    add_common_arguments(parser)
    args = parser.parse_args()
    OPTIONS.update(browser=args.browser, headless=args.headless)
    RUNS[0] = args.runs
    for scenario in SCENARIOS:
        setattr(PerformanceTest, "test_" + scenario[0].replace("-", "_"), make_test(scenario))
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(PerformanceTest)
    result = unittest.TextTestRunner(stream=sys.stdout, verbosity=2).run(suite)
    RESULTS_FILE.parent.mkdir(exist_ok=True)
    new_file = not RESULTS_FILE.exists()
    with open(RESULTS_FILE, "a", encoding="utf-8-sig", newline="") as target:
        writer = csv.writer(target)
        if new_file:
            writer.writerow(["timestamp", "scenario_id", "runs", "min_s", "avg_s", "max_s", "limit_avg_s", "limit_max_s", "result"])
        writer.writerows(sorted(MEASURED, key=lambda r: r[1]))
    print("Đã ghi kết quả: %s" % RESULTS_FILE)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(main())
