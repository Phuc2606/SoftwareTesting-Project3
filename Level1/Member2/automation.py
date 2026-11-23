import argparse
import csv
import os
from pathlib import Path
import re
import sys
import unittest
from urllib.parse import urlencode
from uuid import uuid4


LOCATORS = {
    "username": ("id", "username"),
    "password": ("id", "password"),
    "login": ("id", "loginbtn"),
    "groups": ("id", "groups"),
    "create": ("id", "showcreateorphangroupform"),
    "edit": ("id", "showeditgroupsettingsform"),
    "delete": ("css selector", "#deletegroup, #deletegroups, [name='action'][value='deletegroup']"),
    "confirm": ("css selector", "form:has(input[name=confirm][value='1']) [type=submit]"),
    "name": ("id", "id_name"),
    "idnumber": ("id", "id_idnumber"),
    "key": ("id", "id_enrolmentkey"),
    "key_edit": ("css selector", "#fitem_id_enrolmentkey a[data-passwordunmask=edit]"),
    "visibility": ("id", "id_visibility"),
    "show": ("id", "id_participation"),
    "messaging": ("id", "id_enablemessaging"),
    "submit": ("id", "id_submitbutton"),
    "cancel": ("id", "id_cancel"),
    "required": ("id", "id_error_name"),
    "key_error": ("id", "id_error_enrolmentkey"),
    "editor_frame": ("id", "id_description_editor_ifr"),
    "editor": ("id", "tinymce"),
    "description": ("id", "id_description_editor"),
    "picture": ("css selector", "#fitem_id_currentpicture img"),
    "picker": ("name", "imagefilechoose"),
    "upload_repo": ("xpath", "//*[contains(@class,'fp-repo-area')]//*[self::a or self::button][contains(normalize-space(.),'Upload a file')]"),
    "upload_input": ("css selector", "input[name=repo_upload_file]"),
    "upload_button": ("css selector", "button.fp-upload-btn"),
    "upload_error": ("css selector", ".moodle-dialogue [role=alert], .fp-error, .moodle-dialogue .fp-dlg-text, .alert-danger, #id_error_imagefile"),
    "picker_close": ("css selector", ".moodle-dialogue button[aria-label=Close]"),
    "draft_file": ("css selector", "#id_imagefile_fieldset .filepicker-filename"),
    "members": ("css selector", "#members option"),
    "body": ("tag name", "body"),
}
FIXTURES = Path(__file__).with_name("fixtures")


def read_csv(path):
    with path.open(encoding="utf-8-sig", newline="") as source:
        return list(csv.DictReader(source))


def run(data_path):
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="backslashreplace")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", action="append", help="Run a specific TC-002 ID (repeatable)")
    parser.add_argument("--list", action="store_true", help="Validate and list cases without Chrome")
    parser.add_argument("--headed", action="store_true")
    parser.add_argument("--browser", choices=("chrome", "edge"), default="chrome")
    args = parser.parse_args()
    rows = read_csv(data_path)
    ids = [row["case_id"] for row in rows]
    if ids != [f"TC-002-{number:03d}" for number in range(1, 58)]:
        parser.error("CSV must contain all 57 original case IDs in order")
    locators = LOCATORS
    settings = {
        "base_url": os.environ.get("MOODLE_BASE_URL", "http://localhost:8082"),
        "login_path": "/login/index.php",
        "groups_path": "/group/index.php",
    }
    if args.case and set(args.case) - set(ids):
        parser.error("Unknown --case ID")
    selected = [row for row in rows if not args.case or row["case_id"] in args.case]
    if args.list:
        for row in selected:
            print(row["case_id"], row["title"])
        return 0
    credentials = {key: os.environ.get(f"MOODLE_{key.upper()}", "") for key in
                   ("username", "password", "course_id")}
    if not all(credentials.values()) or not credentials["course_id"].isdigit():
        parser.error("Set MOODLE_USERNAME, MOODLE_PASSWORD and numeric MOODLE_COURSE_ID for a dedicated course")

    try:
        from selenium import webdriver
        from selenium.common.exceptions import ElementClickInterceptedException
        from selenium.webdriver.common.keys import Keys
        from selenium.webdriver.support.ui import Select, WebDriverWait
    except ImportError:
        parser.error("Install Selenium with python -m pip install -r requirements.txt")

    class CreateGroupTests(unittest.TestCase):
        @classmethod
        def setUpClass(cls):
            browser = webdriver.Chrome if args.browser == "chrome" else webdriver.Edge
            options = webdriver.ChromeOptions() if args.browser == "chrome" else webdriver.EdgeOptions()
            if not args.headed:
                options.add_argument("--headless=new")
            options.add_argument("--window-size=1440,1100")
            cls.driver = browser(options=options)
            cls.addClassCleanup(cls.driver.quit)
            cls.wait = WebDriverWait(cls.driver, 12)
            cls.token = uuid4().hex[:8]
            base = settings["base_url"].rstrip("/")
            cls.groups_url = base + settings["groups_path"] + "?" + urlencode(
                {"id": credentials["course_id"], "lang": "en"}
            )
            try:
                cls.driver.get(base + settings["login_path"] + "?lang=en")
                cls.visible("username").send_keys(credentials["username"])
                cls.visible("password").send_keys(credentials["password"])
                cls.click("login")
                cls.driver.get(cls.groups_url)
                cls.visible("create")
                cls.visible("groups")
            except Exception as error:
                raise RuntimeError("Environment setup failed: check Moodle URL, login, course ID and permissions") from error

        @classmethod
        def elements(cls, key):
            return cls.driver.find_elements(*locators[key])

        @classmethod
        def shown(cls, key):
            return next((item for item in cls.elements(key) if item.is_displayed()), None)

        @classmethod
        def visible(cls, key):
            return cls.wait.until(lambda _: cls.shown(key), f"Expected visible: {key}")

        @classmethod
        def click(cls, key):
            element = cls.wait.until(
                lambda _: next((item for item in cls.elements(key)
                                if item.is_displayed() and item.is_enabled()), None),
                f"Expected clickable: {key}",
            )
            unobstructed = cls.driver.execute_script(
                "const el = arguments[0]; el.scrollIntoView({block:'center', inline:'nearest'}); "
                "const r = el.getBoundingClientRect(); "
                "return el.contains(document.elementFromPoint(r.left + r.width / 2, r.top + r.height / 2));",
                element,
            )
            if not unobstructed:
                cls.driver.execute_script("arguments[0].click();", element)
                return
            try:
                element.click()
            except ElementClickInterceptedException:
                cls.driver.execute_script("arguments[0].click();", element)

        def options(self):
            return Select(self.visible("groups")).options

        def group_labels(self):
            return [option.text for option in self.options()]

        def fill(self, key, value):
            if key == "key" and not self.shown(key):
                if not value:
                    return
                self.click("key_edit")
            element = self.visible(key)
            element.clear()
            if value:
                element.send_keys(value)

        def check_value(self, key, expected):
            element = self.wait.until(lambda _: next(iter(self.elements(key)), None))
            self.assertEqual(element.get_property("value"), expected, key)

        def choose(self, key, value):
            Select(self.visible(key)).select_by_visible_text(value)

        def check_controls(self, visible):
            for key in ("show", "messaging"):
                self.wait.until(lambda _: bool(self.shown(key)) == visible, key)

        def set_description(self, html):
            self.wait.until(lambda _: self.shown("editor_frame") or self.shown("description"))
            frame = self.shown("editor_frame")
            if not frame:
                self.fill("description", html)
                return
            self.driver.switch_to.frame(frame)
            try:
                self.driver.execute_script(
                    "arguments[0].innerHTML = arguments[1]; "
                    "arguments[0].dispatchEvent(new Event('input', {bubbles:true}));",
                    self.visible("editor"), html,
                )
            finally:
                self.driver.switch_to.default_content()

        def check_description(self, expected, formatted):
            self.wait.until(lambda _: self.shown("editor_frame") or self.shown("description"))
            frame = self.shown("editor_frame")
            if frame:
                self.driver.switch_to.frame(frame)
            try:
                editor = self.visible("editor" if frame else "description")
                if formatted:
                    paragraphs = self.driver.execute_script(
                        "const root = arguments[0].tagName === 'TEXTAREA' "
                        "? new DOMParser().parseFromString(arguments[0].value, 'text/html') "
                        ": arguments[0]; return Array.from(root.querySelectorAll('p'), p => "
                        "[p.textContent.trim(), Boolean(p.querySelector('strong,b'))]);", editor
                    )
                    self.assertEqual(paragraphs, [[line, index == 0]
                                                 for index, line in enumerate(expected.splitlines())])
                elif frame:
                    self.assertEqual(editor.text.strip(), expected)
                else:
                    actual = self.driver.execute_script(
                        "return new DOMParser().parseFromString(arguments[0].value, "
                        "'text/html').body.textContent.trim();", editor
                    )
                    self.assertEqual(actual, expected)
            finally:
                self.driver.switch_to.default_content()

        def upload(self, filename):
            picker = self.visible("picker")
            self.wait.until(lambda _: self.shown("upload_input") or self.shown("upload_repo") or
                            self.driver.execute_script("arguments[0].click(); return false;", picker))
            if not self.shown("upload_input"):
                self.click("upload_repo")
            if not filename:
                self.visible("upload_input")
                self.click("picker_close")
                self.wait.until(lambda _: not self.shown("upload_input"))
                return "cancelled"
            source = FIXTURES / filename
            if not source.is_file():
                raise FileNotFoundError(source)
            self.visible("upload_input").send_keys(str(source.resolve()))
            self.click("upload_button")

            def outcome(_):
                for item in self.elements("draft_file"):
                    if item.get_property("textContent").strip() == filename:
                        return "attached"
                reason = " ".join(item.text for item in self.elements("upload_error") if item.is_displayed())
                invalid = re.search(r"invalid|unsupported|not allowed|cannot|corrupt|not accepted|not (?:a |an )?valid|not supported|not an image", reason, re.I)
                if invalid and re.search(r"image|file type|filetype|PNG|TXT|text.plain", reason, re.I):
                    return "rejected"
                return None

            return self.wait.until(
                outcome,
                "Expected an attached file or a rejection",
            )

        def cleanup_group(self, label):
            self.driver.get(self.groups_url)
            if label not in self.group_labels():
                return
            self.choose("groups", label)
            self.click("delete")
            self.click("confirm")
            self.wait.until(lambda _: self.shown("groups") and label not in self.group_labels())

        def exercise(self, row):
            flow = row["flow"]
            name = row["name"].replace("{run}", self.token)
            idnumber = row["idnumber"].replace("{run}", self.token)
            key = row["key"].replace("{run}", self.token)
            expected_name = row["expected_name"].replace("{run}", self.token)
            expected_id = row["expected_idnumber"].replace("{run}", self.token)
            expected_key = row["expected_key"].replace("{run}", self.token)
            label = f"{expected_name} (0)"
            self.driver.get(self.groups_url)
            before = self.group_labels()
            if expected_name and label in before:
                self.fail(f"Dedicated course already contains {label!r}; existing data preserved")
            self.click("create")
            if flow in {"required", "recover"}:
                self.fill("name", "")
                self.click("submit")
                self.assertEqual(self.visible("required").text.strip(), row["expected_error"])
                self.visible("name")
                if flow == "required":
                    self.driver.get(self.groups_url)
                    self.assertEqual(self.group_labels(), before)
                    return

            self.fill("name", name)
            self.check_value("name", expected_name)
            if flow == "recover":
                # Blur the corrected field so Moodle can clear its earlier validation state.
                self.visible("name").send_keys(Keys.TAB)
            if row["check_idnumber"] or idnumber:
                self.fill("idnumber", idnumber)
                self.check_value("idnumber", expected_id)
            if row["check_key"] or key:
                self.fill("key", key)
                self.check_value("key", expected_key)
            if row["description_kind"]:
                self.set_description(row["description_html"])
                self.check_description(row["expected_description"], row["description_kind"] == "formatted")
            for visibility in filter(None, row["visibility_sequence"].split("|")):
                self.choose("visibility", visibility)
                self.check_controls(visibility in {"Visible", "Only visible to members"})
            if row["show"]:
                checkbox = self.visible("show")
                if checkbox.is_selected() != (row["show"] == "on"):
                    self.click("show")
            if row["messaging"]:
                self.choose("messaging", row["messaging"])
            if flow == "cancel":
                self.click("cancel")
                self.assertEqual(self.group_labels(), before)
                return
            if flow in {"picture", "invalid_picture", "cancel_picture"}:
                upload = self.upload(row["fixture"])
                if upload == "rejected" and flow == "invalid_picture":
                    self.driver.get(self.groups_url)
                    self.assertEqual(self.group_labels(), before)
                    return
                self.assertEqual(upload, "cancelled" if flow == "cancel_picture" else "attached")

            if expected_name:
                self.addCleanup(self.cleanup_group, label)
            self.click("submit")
            if flow == "db_error":
                observed = self.visible("body").text
                reproduced = row["expected_error"] in observed
                self.driver.get(self.groups_url)
                self.assertTrue(reproduced, f"DB error not reproduced; group_count_delta="
                                f"{len(self.group_labels()) - len(before)}; page={observed[:250]!r}")
                self.assertEqual(self.group_labels(), before)
                return
            if flow == "invalid_picture" and not self.shown("groups"):
                observed = self.visible("body").text
                self.assertRegex(observed.lower(), r"getimagesize|not an image|invalid (?:image|file)|corrupt|unsupported")
                self.driver.get(self.groups_url)
                if label not in self.group_labels():
                    self.assertEqual(self.group_labels(), before)
                    return
                self.choose("groups", label)
            key_error = self.shown("key_error")
            if key_error:
                self.fail(f"Moodle rejected the enrolment key instead of saving: {key_error.text}")
            self.assertEqual(len(self.group_labels()), len(before) + 1)
            self.assertEqual(Select(self.visible("groups")).first_selected_option.text, label)
            if row["check_members"]:
                self.assertFalse(self.elements("members"))
            self.click("edit")
            self.check_value("name", expected_name)
            if row["check_idnumber"]:
                self.check_value("idnumber", expected_id)
            if row["check_key"]:
                self.check_value("key", expected_key)
            if row["description_kind"]:
                self.check_description(row["expected_description"], row["description_kind"] == "formatted")
            if row["expected_visibility"]:
                self.assertEqual(Select(self.visible("visibility")).first_selected_option.text,
                                 row["expected_visibility"])
                self.check_controls(row["expected_controls"] == "visible")
            if row["show"]:
                self.assertEqual(self.visible("show").is_selected(), row["show"] == "on")
            if row["messaging"]:
                self.assertEqual(Select(self.visible("messaging")).first_selected_option.text,
                                 row["messaging"])
            if row["expected_picture"] == "none":
                self.assertFalse(self.elements("picture"))
            elif row["expected_picture"]:
                image = self.visible("picture")
                self.wait.until(lambda _: image.get_property("naturalWidth") > 0)
                actual = f"{image.get_property('naturalWidth')}x{image.get_property('naturalHeight')}"
                self.assertEqual(actual, row["expected_picture"])

    def test_for(row):
        def test(self):
            self.exercise(row)
        test.__doc__ = f"{row['case_id']} {row['title']}"
        return test

    for row in selected:
        setattr(CreateGroupTests, "test_" + row["case_id"].replace("-", "_"), test_for(row))
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(CreateGroupTests)
    return 0 if unittest.TextTestRunner(stream=sys.stdout, verbosity=2).run(suite).wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(run(Path(__file__).with_name("test_data.csv")))
