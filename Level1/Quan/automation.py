import argparse
import csv
import os
import re
import sys
from pathlib import Path

from selenium.webdriver.common.by import By

ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = ROOT.parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
from common.moodle_support import run_data_driven_suite  # noqa: E402

DATA_FILE = ROOT / "test_data.csv"
RESULT_FILE = ROOT / "test_results.csv"

BASE_URL = os.getenv("MOODLE_BASE_URL", "http://127.0.0.1:9501").rstrip("/")
LOGIN_PATH = "/login/index.php"
ADD_USER_PATH = "/user/editadvanced.php?id=-1"
TIMEOUT = int(os.getenv("MOODLE_TIMEOUT", "30"))

# Level 1: locators are maintained directly in Python.
LOCATORS = {
    "login_username": (By.ID, "username"),
    "login_password": (By.ID, "password"),
    "login_button": (By.ID, "loginbtn"),
    "username": (By.ID, "id_username"),
    "password": (By.ID, "id_newpassword"),
    "firstname": (By.ID, "id_firstname"),
    "lastname": (By.ID, "id_lastname"),
    "email": (By.ID, "id_email"),
    "auth": (By.ID, "id_auth"),
    "maildisplay": (By.ID, "id_maildisplay"),
    "moodlenetprofile": (By.ID, "id_moodlenetprofile"),
    "city": (By.ID, "id_city"),
    "country": (By.ID, "id_country"),
    "timezone": (By.ID, "id_timezone"),
    "lang": (By.ID, "id_lang"),
    "description": (By.ID, "id_description_editor"),
    "picturedescription": (By.ID, "id_imagealt"),
    "firstnamephonetic": (By.ID, "id_firstnamephonetic"),
    "lastnamephonetic": (By.ID, "id_lastnamephonetic"),
    "middlename": (By.ID, "id_middlename"),
    "alternatename": (By.ID, "id_alternatename"),
    "interests": (By.CSS_SELECTOR,'input[id^="form_autocomplete_input-"]'),
    "idnumber": (By.ID, "id_idnumber"),
    "institution": (By.ID, "id_institution"),
    "department": (By.ID, "id_department"),
    "phone1": (By.ID, "id_phone1"),
    "phone2": (By.ID, "id_phone2"),
    "address": (By.ID, "id_address"),
    "newpicture": (By.CSS_SELECTOR, "input[type='file']"),
    "suspended": (By.ID, "id_suspended"),
    "generatepassword": (By.ID, "id_createpassword"),
    "forcepasswordchange": (By.ID,"id_preference_auth_forcepasswordchange"),
    "save": (By.ID, "id_submitbutton"),
    "cancel": (By.ID, "id_cancel"),
    "body": (By.TAG_NAME, "body"),
    "error_username": (By.ID, "id_error_username"),
    "error_firstname": (By.ID, "id_error_firstname"),
    "error_lastname": (By.ID, "id_error_lastname"),
    "error_email": (By.ID, "id_error_email"),
}

REQUIRED_COLUMNS = {
    "test_case_id", "test_case_name", "group", "action", "expected_result",
    "expected_status", "expected_errors", "expected_lengths",
}


def read_test_data():
    with DATA_FILE.open("r", encoding="utf-8-sig", newline="") as source:
        reader = csv.DictReader(source)
        if not reader.fieldnames or not REQUIRED_COLUMNS.issubset(reader.fieldnames):
            raise ValueError("test_data.csv is missing required columns.")
        rows = list(reader)
    if not rows:
        raise ValueError("test_data.csv is empty.")
    ids = [row["test_case_id"].strip() for row in rows]
    if len(ids) != len(set(ids)):
        raise ValueError("test_data.csv contains duplicate test_case_id values.")
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", action="append", help="Run one test case ID; repeat to select multiple.")
    parser.add_argument("--list", action="store_true", help="List available test cases.")
    parser.add_argument("--headed", action="store_true", help="Show the browser window.")
    parser.add_argument("--browser", choices=("chrome", "edge"), default="chrome")
    args = parser.parse_args()

    try:
        rows = read_test_data()
    except (OSError, ValueError) as exc:
        parser.error(str(exc))

    known = {row["test_case_id"].strip() for row in rows}
    unknown = set(args.case or ()) - known
    if unknown:
        parser.error("Unknown test case ID: " + ", ".join(sorted(unknown)))
    selected = [row for row in rows if not args.case or row["test_case_id"].strip() in args.case]

    if args.list:
        for row in selected:
            print(f"{row['test_case_id']} | {row['group']} | {row['test_case_name']}")
        return 0

    admin_user = os.getenv("MOODLE_ADMIN_USER", "")
    admin_password = os.getenv("MOODLE_ADMIN_PASSWORD", "")
    if not admin_user or not admin_password:
        parser.error("Set MOODLE_ADMIN_USER and MOODLE_ADMIN_PASSWORD before running tests.")

    return run_data_driven_suite(
        rows=selected,
        locators=LOCATORS,
        base_url=BASE_URL,
        login_path=LOGIN_PATH,
        add_user_path=ADD_USER_PATH,
        admin_user=admin_user,
        admin_password=admin_password,
        browser_name=args.browser,
        headed=args.headed,
        timeout=TIMEOUT,
        root=ROOT,
        result_file=RESULT_FILE,
    )


if __name__ == "__main__":
    raise SystemExit(main())
