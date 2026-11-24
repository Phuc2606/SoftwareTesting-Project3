"""Level 2 data-driven automation for Moodle LMS - Add a Quiz.

Reads test cases from test_data.csv and site URLs + UI elements from test_config.csv.
"""

import argparse
import csv
import os
import re
import sys
import unittest
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DATA_FILE = BASE_DIR / "test_data.csv"
CONFIG_FILE = BASE_DIR / "test_config.csv"

REQUIRED_DATA_COLS = {
    "test_case_id", "test_case_name", "group", "quiz_name",
    "time_limit_enabled", "time_limit_minutes", "grade_to_pass",
    "attempts_allowed", "action", "expected_result",
}

REQUIRED_CONFIG_COLS = {"item_type", "key", "by", "value"}


def read_csv_rows(path, required_cols, label):
    with path.open("r", encoding="utf-8-sig", newline="") as source:
        rows = list(csv.DictReader(source))
    if not rows or not required_cols.issubset(rows[0].keys()):
        raise ValueError(f"{label} is empty or missing required columns")
    return rows


def load_config(path):
    rows = read_csv_rows(path, REQUIRED_CONFIG_COLS, "test_config.csv")
    urls = {}
    elements = {}

    for row in rows:
        item_type = (row["item_type"] or "").strip().lower()
        key = (row["key"] or "").strip()
        by = (row["by"] or "").strip().lower()
        value = row["value"] if row["value"] is not None else ""
        if not key:
            continue
        if item_type == "url":
            urls[key] = value.strip()
        elif item_type == "element":
            if not by or not value.strip():
                raise ValueError(f"Invalid element locator for '{key}' in test_config.csv")
            elements[key] = (by, value.strip())

    return urls, elements


def main():
    parser = argparse.ArgumentParser(description="Moodle Add a Quiz - Level 2 tests")
    parser.add_argument("--case", action="append", help="Specific test case ID (repeatable)")
    parser.add_argument("--list", action="store_true", help="List test cases")
    parser.add_argument("--headed", action="store_true", help="Show browser window")
    parser.add_argument("--browser", choices=("chrome", "edge"), default="chrome")
    args = parser.parse_args()

    rows = read_csv_rows(DATA_FILE, REQUIRED_DATA_COLS, "test_data.csv")
    urls, locators = load_config(CONFIG_FILE)

    known_ids = [r["test_case_id"].strip() for r in rows]
    if args.case and set(args.case) - set(known_ids):
        parser.error(
            "Unknown test case ID: " + ", ".join(sorted(set(args.case) - set(known_ids)))
        )

    selected = [r for r in rows if not args.case or r["test_case_id"].strip() in args.case]
    if args.list:
        for r in selected:
            print(f"{r['test_case_id']} | {r['group']} | {r['test_case_name']} | Expected: {r['expected_result']}")
        return 0

    base_url = os.getenv("MOODLE_BASE_URL", "http://127.0.0.1:9501").rstrip("/")
    username = os.getenv("MOODLE_USERNAME", "")
    password = os.getenv("MOODLE_PASSWORD", "")
    course_id = os.getenv("MOODLE_COURSE_ID", "4")
    section_id = os.getenv("MOODLE_SECTION_ID", "16")

    if not username or not password:
        parser.error("Set MOODLE_USERNAME and MOODLE_PASSWORD environment variables first")
    if not course_id.isdigit() or not section_id.isdigit():
        parser.error("MOODLE_COURSE_ID and MOODLE_SECTION_ID must be numeric")

    login_path = urls.get("login_path", "/login/index.php")
    add_quiz_path = urls.get(
        "add_quiz_path",
        "/course/modedit.php?add=quiz&type&course={course_id}&sectionid={section_id}&return=0&beforemod=0",
    )

    try:
        from selenium import webdriver
        from selenium.common.exceptions import (
            ElementClickInterceptedException,
            StaleElementReferenceException,
            TimeoutException,
        )
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.webdriver.support.ui import Select, WebDriverWait
    except ImportError:
        parser.error("Selenium is missing. Install with: python -m pip install 'selenium>=4.20,<5'")

    by_map = {"id": By.ID, "css selector": By.CSS_SELECTOR, "xpath": By.XPATH, "tag name": By.TAG_NAME}

    for key, (by, _) in locators.items():
        if by not in by_map:
            raise ValueError(f"Unsupported locator strategy '{by}' for element '{key}'")

    class AddQuizLevel2Tests(unittest.TestCase):
        @classmethod
        def setUpClass(cls):
            opts = webdriver.ChromeOptions() if args.browser == "chrome" else webdriver.EdgeOptions()
            if not args.headed:
                opts.add_argument("--headless=new")
            opts.add_argument("--window-size=1440,1000")
            cls.driver = (webdriver.Chrome if args.browser == "chrome" else webdriver.Edge)(options=opts)
            cls.addClassCleanup(cls.driver.quit)
            cls.wait = WebDriverWait(cls.driver, 15)

            u_by, u_val = locators["username"]
            p_by, p_val = locators["password"]
            l_by, l_val = locators["login"]

            try:
                cls.driver.get(base_url + login_path)
                cls.wait.until(EC.visibility_of_element_located((by_map[u_by], u_val))).send_keys(username)
                cls.driver.find_element(by_map[p_by], p_val).send_keys(password)
                cls.driver.find_element(by_map[l_by], l_val).click()
                cls.wait.until(lambda d: "/login/" not in d.current_url)
            except Exception as exc:
                raise RuntimeError("Moodle login failed. Check URL, credentials and permissions.") from exc

        def locate(self, key):
            by, val = locators[key]
            return self.driver.find_element(by_map[by], val)

        def visible(self, key):
            by, val = locators[key]
            return self.wait.until(EC.visibility_of_element_located((by_map[by], val)))

        def page_text(self):
            return self.locate("body").text

        def safe_click(self, el):
            self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", el)
            try:
                el.click()
            except ElementClickInterceptedException:
                self.driver.execute_script("arguments[0].click();", el)

        def open_form(self):
            rel_url = add_quiz_path.format(course_id=course_id, section_id=section_id)
            self.driver.get(base_url + rel_url)
            self.visible("name")

        def is_overall_feedback_open(self):
            b_by, b_val = locators.get("feedback_boundary", ("id", "id_feedbackboundaries_0"))
            boundaries = self.driver.find_elements(by_map[b_by], b_val)
            if boundaries and boundaries[0].is_displayed():
                return True
            return len(self.driver.find_elements(By.TAG_NAME, "iframe")) >= 3

        def _open_parent_for(self, key):
            by, val = locators[key]
            els = self.driver.find_elements(by_map[by], val)
            if not els or els[0].is_displayed():
                return
            self.driver.execute_script(
                """
                let node = arguments[0].parentElement;
                while (node) {
                    if (node.classList && node.classList.contains('collapse') && !node.classList.contains('show')) {
                        const t = node.id ? document.querySelector(`[aria-controls="${node.id}"], a[href="#${node.id}"]`) : null;
                        t ? (t.scrollIntoView({block: 'center'}), t.click()) : node.classList.add('show');
                    }
                    if (node.tagName === 'FIELDSET' && node.classList.contains('collapsed')) {
                        const l = node.querySelector('legend a, legend button, .fheader');
                        if (l) { l.scrollIntoView({block: 'center'}); l.click(); }
                    }
                    node = node.parentElement;
                }
                """,
                els[0],
            )

        def expand_section(self, section_number, min_iframes=None):
            if section_number == 9 and self.is_overall_feedback_open():
                return
            if section_number == 1:
                self._open_parent_for("time_enabled")
            elif section_number == 2:
                self._open_parent_for("grade_to_pass")
                self._open_parent_for("attempts")

            el_id = f"collapseElement-{section_number}"
            panels = self.driver.find_elements(By.ID, el_id)
            if panels and panels[0].is_displayed() and min_iframes is None:
                return

            sel = f"#{el_id}, [aria-controls='{el_id}'], a[href='#{el_id}'], [data-target='#{el_id}'], [data-bs-target='#{el_id}']"
            if section_number == 1:
                sel += ", #id_timinghdr a.fheader, #id_timinghdr button"
            elif section_number == 2:
                sel += ", #id_modgradehdr a.fheader, #id_modgradehdr button"
            elif section_number == 9:
                sel += ", a[href*='overallfeedbackhdrcontainer'], [aria-controls*='overallfeedbackhdrcontainer'], #id_overallfeedbackhdr a.fheader, #id_overallfeedbackhdr button"

            for toggle in self.driver.find_elements(By.CSS_SELECTOR, sel):
                if toggle.is_displayed():
                    if toggle.get_attribute("aria-expanded") == "true" and min_iframes is None:
                        break
                    self.safe_click(toggle)
                    if min_iframes is None:
                        break

            if min_iframes is not None:
                self.wait.until(lambda d: self.is_overall_feedback_open())

        def fill(self, key, value):
            el = self.visible(key)
            el.clear()
            if value != "":
                el.send_keys(str(value))
            return el

        def _is_frame_ready(self, frame):
            try:
                if not frame.is_displayed():
                    return False
                r = frame.rect
                return r.get("width", 0) > 10 and r.get("height", 0) > 10
            except Exception:
                return False

        def fill_overall_feedback(self):
            self.expand_section(9, min_iframes=3)

            synced = self.driver.execute_script(
                """
                const tm = window.tinymce || window.tinyMCE;
                if (!tm || !tm.editors || !tm.editors.length) return false;
                const targets = tm.editors.filter(
                    ed => ed.id && ed.id.includes('feedbacktext') && !ed.id.includes('intro')
                );
                if (!targets.length) return false;
                targets.forEach((ed, i) => {
                    ed.setContent(i === 0 ? '<p>Good</p>' : '<p>Bad</p>');
                    ed.fire('input');
                    ed.fire('change');
                });
                if (typeof tm.triggerSave === 'function') tm.triggerSave();
                return true;
                """
            )
            if not synced:
                fb_frames = [
                    f for f in self.driver.find_elements(
                        By.CSS_SELECTOR,
                        "#id_overallfeedbackhdr iframe, #collapseElement-9 iframe, [id*='overallfeedback'] iframe"
                    )
                    if self._is_frame_ready(f)
                ]
                for i, frame in enumerate(fb_frames[:2]):
                    self.driver.switch_to.frame(frame)
                    try:
                        eds = self.driver.find_elements(By.ID, "tinymce") or self.driver.find_elements(By.TAG_NAME, "body")
                        if eds:
                            self.driver.execute_script(
                                "arguments[0].innerHTML = '<p>' + arguments[1] + '</p>';"
                                "arguments[0].dispatchEvent(new Event('input', {bubbles: true}));"
                                "arguments[0].dispatchEvent(new Event('change', {bubbles: true}));",
                                eds[0],
                                "Good" if i == 0 else "Bad",
                            )
                    finally:
                        self.driver.switch_to.default_content()

            self.driver.execute_script(
                """
                const msgs = ['Good', 'Bad'];
                document.querySelectorAll("textarea[id^='id_feedbacktext'], textarea[name^='feedbacktext']")
                    .forEach((ta, i) => {
                        ta.value = '<p>' + (msgs[i] || 'Good') + '</p>';
                        ta.dispatchEvent(new Event('input', {bubbles: true}));
                        ta.dispatchEvent(new Event('change', {bubbles: true}));
                    });
                const tm = window.tinymce || window.tinyMCE;
                if (tm && typeof tm.triggerSave === 'function') tm.triggerSave();
                """
            )

        def _wait_settled(self, start_url):
            def ready(d):
                try:
                    if d.current_url != start_url and "/course/modedit.php" not in d.current_url:
                        return True
                    if "You must fill in the feedback boxes without leaving any gaps." in d.find_element(By.TAG_NAME, "body").text:
                        return True
                    if d.find_elements(By.CSS_SELECTOR, ".form-control-feedback.invalid-feedback, .error"):
                        return True
                except StaleElementReferenceException:
                    return False
                return False

            try:
                self.wait.until(ready)
            except TimeoutException:
                pass

        def exercise(self, row):
            case_id = row["test_case_id"].strip()
            action = (row["action"] or "save").strip().lower()
            expected = row["expected_result"]

            self.open_form()
            self.fill("name", row["quiz_name"])

            time_enabled = (row["time_limit_enabled"] or "").strip().lower() == "true"
            if time_enabled:
                self.expand_section(1)
                cb = self.visible("time_enabled")
                if not cb.is_selected():
                    cb.click()
                if row["time_limit_minutes"] != "":
                    self.fill("time_minutes", row["time_limit_minutes"])

            if row["grade_to_pass"] != "":
                self.expand_section(2)
                self.fill("grade_to_pass", row["grade_to_pass"])

            if row["attempts_allowed"] != "":
                self.expand_section(2)
                Select(self.visible("attempts")).select_by_visible_text(row["attempts_allowed"])

            if action != "cancel":
                self.fill_overall_feedback()

            if action == "cancel":
                self.safe_click(self.visible("cancel"))
                self.wait.until(lambda d: d.execute_script("return document.readyState") == "complete")
                self.assertNotIn(expected, self.page_text(), f"{case_id}: '{expected}' should not be present after cancel")
                return

            entered_time = self.visible("time_minutes").get_attribute("value") if time_enabled else None
            start_url = self.driver.current_url
            self.safe_click(self.visible("save"))
            self._wait_settled(start_url)

            norm_text = re.sub(r"\s+", " ", self.page_text())
            norm_expected = re.sub(r"\s+", " ", expected)
            self.assertIn(
                norm_expected,
                norm_text,
                f"{case_id}: expected '{expected}' not found.\n"
                f"Entered time value: {entered_time!r}\n"
                f"Current URL: {self.driver.current_url}\n"
                f"Page snippet: {norm_text[:500]}",
            )

    def make_test(row):
        def test(self):
            self.exercise(row)
        test.__doc__ = f"{row['test_case_id']} - {row['test_case_name']}"
        return test

    for row in selected:
        setattr(AddQuizLevel2Tests, "test_" + re.sub(r"\W+", "_", row["test_case_id"].strip()), make_test(row))

    suite = unittest.defaultTestLoader.loadTestsFromTestCase(AddQuizLevel2Tests)
    result = unittest.TextTestRunner(stream=sys.stdout, verbosity=2).run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())