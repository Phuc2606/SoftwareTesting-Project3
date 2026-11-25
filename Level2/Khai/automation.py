"""Data-driven Selenium automation for Moodle Feature 001 – Add a Category."""

import argparse
import csv
import logging
import os
import sys
import time
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from uuid import uuid4


HERE = Path(__file__).resolve().parent
DATA_FILE = HERE / "test_data.csv"
CONFIG_FILE = HERE / "test_config.csv"
RESULTS_FILE = HERE / "results" / "latest_results.csv"
REQUIRED_SETTINGS = {"base_url", "login_path", "category_management_path", "add_category_path", "edit_category_path", "timeout_seconds"}
REQUIRED_LOCATORS = {"username", "password", "login", "name", "idnumber", "description", "description_frame", "parent", "submit", "cancel", "body", "error_notifications", "category_links", "category_edit_links", "category_error_name", "category_error_idnumber"}
LOCATOR_STRATEGIES = {"id", "name", "xpath", "css selector", "tag name", "class name", "link text", "partial link text"}
CSV_COLUMNS = {
    "case_id", "technique", "title", "action", "category_name", "name_length",
    "name_pattern", "category_idnumber", "id_length", "id_pattern", "description",
    "description_length", "parent_category", "expected_result", "assertion", "prerequisites",
}
ASSERTIONS = {
    "created_category", "created_details", "required_error", "observe", "duplicate_id",
    "parent_selected", "cancel_no_create", "category_name_too_long", "trim_observation",
    "whitespace_observation", "duplicate_name_allowed", "id_limited_to_100",
    "trimmed_category_created", "created_by_id",
}

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
LOGGER = logging.getLogger("level2.khai")


def read_configuration(path):
    settings, locators = {}, {}
    with path.open("r", encoding="utf-8-sig", newline="") as source:
        reader = csv.DictReader(source)
        required_columns = {"key", "type", "value"}
        if not reader.fieldnames or not required_columns.issubset(reader.fieldnames):
            raise ValueError("test_config.csv must have columns: key,type,value")
        for line, row in enumerate(reader, start=2):
            key, kind, value = tuple((row.get(name) or "").strip()
                                     for name in ("key", "type", "value"))
            if not key or not value:
                raise ValueError(f"test_config.csv line {line}: key, type, and value must be non-empty")
            if key in settings or key in locators:
                raise ValueError(f"test_config.csv line {line}: duplicate key {key!r}")
            if kind == "setting":
                settings[key] = value
            elif kind in LOCATOR_STRATEGIES:
                locators[key] = (kind, value)
            else:
                raise ValueError(f"test_config.csv line {line}: unsupported type/locator strategy {kind!r}")
    missing_settings = REQUIRED_SETTINGS - settings.keys()
    missing_locators = REQUIRED_LOCATORS - locators.keys()
    if missing_settings or missing_locators:
        missing = sorted(missing_settings | missing_locators)
        raise ValueError("Missing required config key(s): " + ", ".join(missing))
    try:
        timeout = int(settings["timeout_seconds"])
    except ValueError as exc:
        raise ValueError("Config key timeout_seconds must be an integer") from exc
    if timeout <= 0:
        raise ValueError("Config key timeout_seconds must be greater than zero")
    settings["base_url"] = settings["base_url"].rstrip("/")
    for key in ("login_path", "category_management_path", "add_category_path", "edit_category_path"):
        if not settings[key].startswith("/"):
            raise ValueError(f"Config key {key} must start with '/'")
    return settings, locators


def read_cases(path=DATA_FILE):
    with path.open("r", encoding="utf-8-sig", newline="") as source:
        reader = csv.DictReader(source)
        if not reader.fieldnames or not CSV_COLUMNS.issubset(reader.fieldnames):
            raise ValueError("CSV thiếu cột bắt buộc: " + ", ".join(sorted(CSV_COLUMNS)))
        rows = list(reader)
    ids = [row["case_id"].strip() for row in rows]
    expected_ids = [f"TC-001-{number:03d}" for number in range(1, 31)]
    if ids != expected_ids:
        raise ValueError("CSV phải có đủ 30 testcase TC-001-001 đến TC-001-030, đúng thứ tự và không trùng ID.")
    for row in rows:
        if row["assertion"] not in ASSERTIONS:
            raise ValueError(f"{row['case_id']}: assertion không hợp lệ: {row['assertion']!r}")
        if row["action"] not in {"submit", "cancel", "select_parent"}:
            raise ValueError(f"{row['case_id']}: action không hợp lệ: {row['action']!r}")
    return rows


def main(argv=None):
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="backslashreplace")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", action="append", help="Chạy testcase ID cụ thể; có thể lặp tùy chọn")
    parser.add_argument("--list", action="store_true", help="Liệt kê testcase mà không mở browser")
    parser.add_argument("--headed", action="store_true", help="Hiển thị cửa sổ browser")
    parser.add_argument("--browser", choices=("chrome", "edge"), default="chrome")
    parser.add_argument("--config", type=Path, default=CONFIG_FILE, help="Đường dẫn test_config.csv")
    parser.add_argument("--data", type=Path, default=DATA_FILE, help="Đường dẫn test_data.csv")
    args = parser.parse_args(argv)
    try:
        rows = read_cases(args.data)
        settings, locators = read_configuration(args.config)
    except (OSError, ValueError, csv.Error) as exc:
        parser.error(str(exc))

    ids = {row["case_id"] for row in rows}
    unknown = set(args.case or ()) - ids
    if unknown:
        parser.error("Không tìm thấy testcase: " + ", ".join(sorted(unknown)))
    selected = [row for row in rows if not args.case or row["case_id"] in args.case]
    if args.list:
        for row in selected:
            print(f"{row['case_id']} | {row['technique']} | {row['title']} | {row['expected_result']}")
        return 0

    base_url = os.getenv("MOODLE_BASE_URL", settings["base_url"]).rstrip("/")
    username, password = os.getenv("MOODLE_USERNAME", ""), os.getenv("MOODLE_PASSWORD", "")
    if not username or not password:
        parser.error("Cần thiết lập MOODLE_USERNAME và MOODLE_PASSWORD. Xem Level2/Khai/README.md.")
    try:
        from selenium import webdriver
        from selenium.common.exceptions import ElementClickInterceptedException, TimeoutException
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.webdriver.support.ui import Select, WebDriverWait
    except ImportError:
        parser.error("Chưa có Selenium. Cài dependencies bằng: python -m pip install -r requirements.txt")

    by_map = {
        "id": By.ID, "name": By.NAME, "xpath": By.XPATH, "css selector": By.CSS_SELECTOR,
        "tag name": By.TAG_NAME, "class name": By.CLASS_NAME,
        "link text": By.LINK_TEXT, "partial link text": By.PARTIAL_LINK_TEXT,
    }
    run_tag = uuid4().hex[:8]
    options = webdriver.ChromeOptions() if args.browser == "chrome" else webdriver.EdgeOptions()
    if not args.headed:
        options.add_argument("--headless=new")
    options.add_argument("--window-size=1440,1000")
    try:
        driver = (webdriver.Chrome if args.browser == "chrome" else webdriver.Edge)(options=options)
    except Exception as exc:
        print(f"ERROR: Không khởi tạo được {args.browser}: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2
    wait = WebDriverWait(driver, int(settings["timeout_seconds"]))
    results = []
    execution_stage = {"value": "initializing"}

    def find(key):
        by, value = locators[key]
        return driver.find_element(by_map[by], value)

    def visible(key):
        by, value = locators[key]
        return wait.until(EC.visibility_of_element_located((by_map[by], value)))

    def elements(key):
        by, value = locators[key]
        return driver.find_elements(by_map[by], value)

    def on_path(setting_key):
        return urlparse(driver.current_url).path.rstrip("/") == settings[setting_key].rstrip("/")

    def related_elements(target, key):
        related = []
        for item in elements(key):
            if driver.execute_script(
                "let n=arguments[0]; for(let i=0;n&&i<10;i++,n=n.parentElement){if(n.contains(arguments[1]))return true;} return false;",
                target, item,
            ):
                related.append(item)
        return related

    def login():
        driver.get(base_url + settings["login_path"])
        visible("username").send_keys(username)
        visible("password").send_keys(password)
        find("login").click()
        wait.until(lambda browser: urlparse(browser.current_url).path.rstrip("/") != settings["login_path"].rstrip("/"))

    def resolve_special(value, case_id):
        value = (value or "").replace("{run}", run_tag)
        if value == "@existing_name":
            value = os.getenv("MOODLE_EXISTING_CATEGORY_NAME", "")
        elif value == "@existing_id":
            value = os.getenv("MOODLE_EXISTING_CATEGORY_ID", "")
        elif value == "@parent":
            value = os.getenv("MOODLE_PARENT_CATEGORY", "")
        if value == "":
            raise ValueError(f"{case_id}: thiếu dữ liệu chuẩn bị; xem cột prerequisites trong CSV.")
        return value

    def make_value(row, value_key, length_key, pattern_key):
        value = row[value_key].replace("{run}", run_tag)
        length = row[length_key].strip()
        if not length:
            return value
        size = int(length)
        pattern = row[pattern_key] or "A"
        unique = row["case_id"].replace("-", "") + run_tag
        if size < 1:
            return ""
        return (unique + pattern * size)[:size]

    def open_form():
        driver.get(base_url + settings["add_category_path"])
        visible("name")

    def set_description(value):
        editor_id = find("description").get_attribute("id")
        tiny_editor_ready = wait.until(lambda browser: browser.execute_script(
            "const tm=window.tinyMCE||window.tinymce; "
            "return Boolean(tm && tm.get(arguments[0]));", editor_id
        ))
        if tiny_editor_ready:
            driver.execute_script(
                "const tm=window.tinyMCE||window.tinymce; "
                "const editor=tm.get(arguments[1]); "
                "editor.setContent(arguments[0]); editor.save();",
                value,
                editor_id,
            )
        else:
            field = visible("description")
            field.clear()
            field.send_keys(value)

    def populate(row):
        name = make_value(row, "category_name", "name_length", "name_pattern")
        idnumber = make_value(row, "category_idnumber", "id_length", "id_pattern")
        if name == "@existing_name":
            name = resolve_special(name, row["case_id"])
        if idnumber == "@existing_id":
            idnumber = resolve_special(idnumber, row["case_id"])
        for key, value in (("name", name), ("idnumber", idnumber)):
            field = visible(key)
            field.clear()
            if value:
                field.send_keys(value)
        description = row["description"]
        if row["description_length"].strip():
            description = (row.get("description_pattern") or "D") * int(row["description_length"])
        if description:
            set_description(description)
        return name, idnumber, description

    def lookup_parent_id(name):
        requested_idnumber = os.getenv("MOODLE_PARENT_CATEGORY_IDNUMBER", "").strip()
        configured_id = os.getenv("MOODLE_PARENT_CATEGORY_ID", "").strip()
        if configured_id.isdigit():
            return configured_id

        driver.get(base_url + settings["category_management_path"])
        visible("body")
        candidates = []
        for anchor in elements("category_links"):
            if anchor.text.strip().casefold() != name.strip().casefold():
                continue
            context = driver.execute_script("return arguments[0].parentElement.parentElement.innerText || '';", anchor)
            if requested_idnumber and requested_idnumber.casefold() not in context.casefold():
                continue
            possible_ids = []
            for link in [anchor, *related_elements(anchor, "category_edit_links")]:
                href = link.get_attribute("href") or ""
                query = parse_qs(urlparse(href).query)
                possible_ids.extend(query.get("categoryid", []))
                possible_ids.extend(query.get("id", []))
            if possible_ids:
                candidates.extend(possible_ids)
        for category_id in candidates:
            if str(category_id).isdigit() and str(category_id) not in {"0", "1"}:
                return str(category_id)
        raise ValueError(
            f"Không tìm được ID Moodle cho category cha {name!r}. "
            "Có thể đặt MOODLE_PARENT_CATEGORY_ID hoặc MOODLE_PARENT_CATEGORY_IDNUMBER."
        )

    def choose_parent(row, parent_id=None):
        requested = resolve_special(row["parent_category"], row["case_id"])
        select_element = parent_select_element()
        select = Select(select_element)
        options = select.options
        matching = next((option for option in options
                         if parent_id and (option.get_attribute("value") or "").strip() == parent_id), None)
        if matching is None:
            matching = next((option for option in options
                             if option.text.strip().casefold() == requested.strip().casefold()), None)
        if matching is None and requested.strip().casefold() == "top":
            # Moodle's root category is commonly value 0; its visible label may be localized
            # or decorated (for example, "Top category") in the native option list.
            matching = next((option for option in options
                             if option.get_attribute("value").strip() == "0"), None)
        if matching is None:
            available = [(option.text.strip(), option.get_attribute("value")) for option in options]
            raise ValueError(
                f"Không tìm thấy Parent category {requested!r} trong selector. Các lựa chọn: {available!r}"
            )
        if select.first_selected_option.get_attribute("value") != matching.get_attribute("value"):
            # Moodle may hide the native <select> behind its accessible autocomplete widget.
            # Set the native form value and dispatch change so the form submits the chosen parent.
            driver.execute_script(
                "const s=arguments[0], v=arguments[1]; "
                "Array.from(s.options).forEach(o => o.selected = (o.value === v)); "
                "s.dispatchEvent(new Event('input', {bubbles:true})); "
                "s.dispatchEvent(new Event('change', {bubbles:true}));",
                select_element,
                matching.get_attribute("value"),
            )
        return requested, select

    def parent_select_element():
        return wait.until(lambda browser: next(iter(elements("parent")), None))

    def page_text():
        return find("body").text

    def safe_click(element):
        driver.execute_script(
            "arguments[0].scrollIntoView({block:'center', inline:'nearest'});", element
        )
        try:
            element.click()
        except ElementClickInterceptedException:
            # Moodle's sticky footer/editor can cover the submit control after scrolling.
            driver.execute_script("arguments[0].click();", element)

    def error_text():
        notices = elements("error_notifications") + elements("category_error_name") + elements("category_error_idnumber")
        return " | ".join(item.text.strip() for item in notices
                          if item.is_displayed() and item.text.strip())

    def category_edit_url(name):
        target = next((item for item in elements("category_links")
                       if item.text.strip().casefold() == name.strip().casefold()), None)
        if target is None:
            return None
        for link in related_elements(target, "category_edit_links"):
            href = link.get_attribute("href")
            if href:
                return href
        return None

    def open_created_category_settings(name, idnumber, expected_saved_id=None):
        # Moodle may redirect to a category detail/index page after creation instead
        # of the configured management URL. Search from the configured list page.
        if not on_path("category_management_path"):
            driver.get(base_url + settings["category_management_path"])
            visible("body")
        edit_url = category_edit_url(name)
        expected_saved_id = idnumber if expected_saved_id is None else expected_saved_id
        candidates = ([edit_url] if edit_url else []) + [
            item.get_attribute("href") for item in elements("category_edit_links")
            if item.get_attribute("href") != edit_url
        ]
        for candidate in candidates:
            if not candidate:
                continue
            try:
                driver.get(candidate)
                body = page_text().casefold()
                if "unknowncategory" in body or "unknown category" in body:
                    continue
                name_fields, id_fields = elements("name"), elements("idnumber")
                if not name_fields or not id_fields:
                    continue
                saved_name = name_fields[0].get_attribute("value")
                saved_id = id_fields[0].get_attribute("value")
                if saved_id == expected_saved_id:
                    return saved_name, saved_id
            except Exception:
                # Stale/deleted category links can be present in Moodle's list.
                continue
        raise ValueError(f"Không tìm được category đã tạo với ID number {expected_saved_id!r}")

    def verify_created(name, idnumber, description, parent_name, parent_id, assertion):
        try:
            wait.until(lambda _: name in page_text() or error_text() or not on_path("edit_category_path"))
        except TimeoutException:
            pass
        body = page_text()
        if on_path("edit_category_path"):
            try:
                submitted_name = find("name").get_attribute("value")
            except Exception:
                submitted_name = "<không đọc được>"
            return False, (
                f"Form vẫn mở sau Submit; Name hiện tại={submitted_name!r}; "
                f"validation={error_text() or 'không tìm thấy thông báo validation'}; "
                f"page={body[:1200]}"
            )
        if assertion == "created_details":
            execution_stage["value"] = "finding the created category edit link"
            edit_url = category_edit_url(name)
            if not edit_url:
                return False, f"Category name was not linked to an edit form; URL={driver.current_url}"
            driver.get(edit_url)
            execution_stage["value"] = "verifying saved category name and ID number"
            edit_name = visible("name").get_attribute("value")
            visible("idnumber")
            wait.until(lambda _: find("idnumber").get_attribute("value") == idnumber)
            edit_id = find("idnumber").get_attribute("value")
            execution_stage["value"] = "verifying saved parent category"
            parent_select = Select(parent_select_element())
            selected_parent_option = parent_select.first_selected_option
            edit_parent = selected_parent_option.text.strip()
            edit_parent_value = (selected_parent_option.get_attribute("value") or "").strip()
            execution_stage["value"] = "verifying saved description"
            frame = elements("description_frame")
            if frame and frame[0].is_displayed():
                driver.switch_to.frame(frame[0])
                try:
                    edit_description = find("body").text.strip()
                finally:
                    driver.switch_to.default_content()
            else:
                edit_description = find("description").get_attribute("value")
            expected_description = driver.execute_script(
                "return new DOMParser().parseFromString(arguments[0], 'text/html').body.textContent.trim();",
                description,
            )
            expected_parent_id = parent_id or ("0" if parent_name.strip().casefold() == "top" else "")
            parent_matches = edit_parent_value == expected_parent_id if expected_parent_id else (
                edit_parent.casefold() == parent_name.casefold()
            )
            checks = {
                "name": edit_name == name,
                "id": edit_id == idnumber,
                "description": edit_description == expected_description,
                "parent": parent_matches,
            }
            return all(checks.values()), (
                f"Saved fields verified: {checks}; ID expected={idnumber!r}, actual={edit_id!r}; "
                f"parent expected={parent_name!r} (ID={expected_parent_id!r}); "
                f"parent actual label={edit_parent!r}, value={edit_parent_value!r}; URL={driver.current_url}"
            )
        if assertion == "created_category":
            return name in body and not error_text(), f"Tên hiển thị={name in body}; lỗi={error_text() or 'không có'}; URL={driver.current_url}"
        return name in body, f"Category tìm thấy={name in body}; URL={driver.current_url}"

    def execute(row):
        action, assertion = row["action"], row["assertion"]
        parent_name = resolve_special(row["parent_category"], row["case_id"])
        parent_id = None
        if parent_name.strip().casefold() != "top":
            execution_stage["value"] = "looking up parent category"
            parent_id = lookup_parent_id(parent_name)
        execution_stage["value"] = "opening category form and locating Name"
        open_form()
        execution_stage["value"] = "filling form fields"
        name, idnumber, description = populate(row)
        execution_stage["value"] = "selecting parent category"
        parent_name, selected_parent = choose_parent(row, parent_id)
        submitted = {
            "name": find("name").get_attribute("value"),
            "idnumber": find("idnumber").get_attribute("value"),
            "description": description,
            "parent": selected_parent.first_selected_option.text.strip(),
        }
        if action == "select_parent":
            selected_values = [option.get_attribute("value") for option in selected_parent.options if option.is_selected()]
            selected = selected_parent.first_selected_option
            expected_selection = parent_id or selected.get_attribute("value")
            passed = selected.get_attribute("value") == expected_selection and len(selected_values) == 1
            return ("PASS" if passed else "FAIL"), (f"Selected label={selected.text!r}; "
                    f"selected value={selected.get_attribute('value')!r}; "
                    f"expected parent ID={expected_selection!r}; selected count={len(selected_values)}"), ""
        if action == "cancel":
            execution_stage["value"] = "cancel action and verify no category was created"
            safe_click(visible("cancel"))
            wait.until(lambda _: not on_path("edit_category_path"))
            driver.get(base_url + settings["category_management_path"])
            visible("body")
            exists = name in page_text()
            passed = not exists
            return ("PASS" if passed else "FAIL"), f"Category tồn tại sau Cancel={exists}; URL={driver.current_url}", ""

        execution_stage["value"] = "clicking Create category"
        safe_click(visible("submit"))
        execution_stage["value"] = "checking Moodle response after submit"
        if assertion == "required_error":
            wait.until(lambda _: error_text() or "Required" in page_text())
            actual_error = error_text() or page_text()[:1500]
            passed = "required" in actual_error.casefold() or "required" in page_text().casefold()
            return ("PASS" if passed else "FAIL"), f"Validation={actual_error}; category không được lưu nếu form còn mở", ""
        if assertion == "category_name_too_long":
            wait.until(lambda _: "category name too long" in page_text().casefold()
                       or "categorytoolong" in page_text().casefold())
            actual_error = error_text() or page_text()[:1500]
            passed = "category name too long" in actual_error.casefold() or "categorytoolong" in actual_error.casefold()
            return ("PASS" if passed else "FAIL"), f"Validation={actual_error}", ""
        if assertion == "duplicate_id":
            try:
                wait.until(lambda _: bool(error_text()))
            except TimeoutException:
                pass
            actual_error = error_text() or page_text()[:1500]
            field_errors = [item for item in elements("category_error_idnumber")
                            if item.is_displayed() and item.text.strip()]
            passed = bool(field_errors) or any(
                word in actual_error.casefold() for word in ("duplicate", "already used", "already exists")
            )
            return ("PASS" if passed else "FAIL"), f"Duplicate ID response={actual_error or 'không tìm thấy lỗi'}", ""
        if assertion in {"trimmed_category_created", "created_by_id", "trim_observation",
                         "whitespace_observation", "duplicate_name_allowed", "id_limited_to_100"}:
            try:
                WebDriverWait(driver, int(settings["timeout_seconds"])).until(
                    lambda _: not on_path("edit_category_path") or error_text()
                )
            except TimeoutException:
                pass
            response_error = error_text()
            if assertion == "whitespace_observation":
                if on_path("category_management_path"):
                    saved_name, saved_id = open_created_category_settings(name, idnumber)
                    return "OBSERVED", f"Moodle đã lưu category; Name={saved_name!r}; ID={saved_id!r}", ""
                return "OBSERVED", f"Moodle validation={response_error or page_text()[:1200]}", ""
            if assertion == "trimmed_category_created":
                try:
                    saved_name, saved_id = open_created_category_settings(name, idnumber)
                    expected_saved_name = name.strip()
                    passed = saved_name == expected_saved_name and saved_id == idnumber
                    return ("PASS" if passed else "FAIL"), (
                        f"Created={bool(saved_id)}; submitted Name={name!r}; "
                        f"saved Name={saved_name!r}; expected trimmed Name={expected_saved_name!r}; "
                        f"saved ID={saved_id!r}; expected ID={idnumber!r}"
                    ), ""
                except Exception:
                    return "FAIL", f"Moodle did not save trimmed-name category: {response_error or page_text()[:1200]}", ""
            if assertion == "created_by_id":
                try:
                    saved_name, saved_id = open_created_category_settings(name, idnumber)
                    passed = saved_id == idnumber
                    return ("PASS" if passed else "FAIL"), (
                        f"Created by ID={passed}; submitted Name={name!r}; saved Name={saved_name!r}; "
                        f"saved ID={saved_id!r}; expected ID={idnumber!r}"
                    ), ""
                except Exception:
                    return "FAIL", f"Moodle did not save category: {response_error or page_text()[:1200]}", ""
            if assertion == "trim_observation":
                if on_path("category_management_path"):
                    saved_name, saved_id = open_created_category_settings(name, idnumber)
                    return "OBSERVED", f"Submitted Name={submitted['name']!r}; saved Name={saved_name!r}; ID={saved_id!r}", ""
                return "OBSERVED", f"Moodle validation={response_error or page_text()[:1200]}", ""
            if assertion == "duplicate_name_allowed":
                try:
                    saved_name, saved_id = open_created_category_settings(name, idnumber)
                    passed = saved_name == name and saved_id == idnumber
                    return ("PASS" if passed else "FAIL"), (
                        f"Duplicate name accepted={passed}; saved Name={saved_name!r}; "
                        f"saved ID={saved_id!r}; expected ID={idnumber!r}"
                    ), ""
                except Exception:
                    return "FAIL", f"Moodle did not create duplicate-name category: {response_error or page_text()[:1200]}", ""
            if assertion == "id_limited_to_100":
                try:
                    saved_name, saved_id = open_created_category_settings(
                        name, idnumber, expected_saved_id=idnumber[:100]
                    )
                except Exception:
                    return "FAIL", f"Moodle did not save the category: {response_error or page_text()[:1200]}", ""
                passed = len(saved_id) == 100
                return ("PASS" if passed else "FAIL"), (
                    f"ID input requested length=101; saved length={len(saved_id)}; "
                    f"saved ID={saved_id!r}; saved Name={saved_name!r}"
                ), ""
        if assertion == "observe":
            try:
                WebDriverWait(driver, int(settings["timeout_seconds"])).until(
                    lambda _: not on_path("edit_category_path") or error_text()
                )
            except TimeoutException:
                pass
            return "NOT ASSERTED", (f"Submitted={submitted}; URL={driver.current_url}; "
                                     f"validation={error_text() or 'không có'}; page={page_text()[:1000]}"), ""
        execution_stage["value"] = "verifying saved category data"
        passed, actual = verify_created(name, idnumber, description, parent_name, parent_id, assertion)
        return ("PASS" if passed else "FAIL"), actual, ""

    try:
        login()
    except Exception as exc:
        driver.quit()
        print(f"ERROR: Moodle login/setup thất bại: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2

    try:
        for row in selected:
            started = time.perf_counter()
            try:
                status, actual, error = execute(row)
            except Exception as exc:
                status, error = "ERROR", f"{type(exc).__name__} at {execution_stage['value']}: {exc}"
                try:
                    field_values = {
                        key: (items[0].get_attribute("value") if items else "<not found>")
                        for key in ("name", "idnumber")
                        for items in [elements(key)]
                    }
                    actual = f"URL={driver.current_url}; form_values={field_values}; page={page_text()[:1000]}"
                except Exception:
                    actual = "Không đọc được trạng thái trình duyệt."
            elapsed = time.perf_counter() - started
            print(f"{row['case_id']}: {status}" + (f" — {error}" if error else ""))
            LOGGER.info("%s %s (%.3fs)", row["case_id"], status, elapsed)
            results.append({"TC_ID": row["case_id"], "Expected Result": row["expected_result"],
                            "Actual Result": actual, "Status": status, "Error Message": error,
                            "Execution Time": f"{elapsed:.3f}s"})
    finally:
        driver.quit()

    RESULTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    result_path = RESULTS_FILE
    try:
        output = result_path.open("w", encoding="utf-8-sig", newline="")
    except PermissionError:
        stamp = time.strftime("%Y%m%d-%H%M%S")
        result_path = RESULTS_FILE.with_name(f"latest_results_{stamp}.csv")
        output = result_path.open("w", encoding="utf-8-sig", newline="")
    with output:
        fields = ["TC_ID", "Expected Result", "Actual Result", "Status", "Error Message", "Execution Time"]
        writer = csv.DictWriter(output, fieldnames=fields)
        writer.writeheader()
        writer.writerows(results)
    counts = {status: sum(item["Status"] == status for item in results)
              for status in ("PASS", "FAIL", "ERROR", "NOT ASSERTED", "OBSERVED")}
    print("\nSummary:")
    print(f"Total: {len(results)}\nPassed: {counts['PASS']}\nFailed: {counts['FAIL']}\nErrors: {counts['ERROR']}\nNot asserted: {counts['NOT ASSERTED']}\nObserved: {counts['OBSERVED']}\nResults: {result_path}")
    return 1 if counts["FAIL"] or counts["ERROR"] else 0


if __name__ == "__main__":
    raise SystemExit(main())

