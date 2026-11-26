import argparse
import csv
import os
import sys
from pathlib import Path

from selenium.webdriver.common.by import By

ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = ROOT.parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from common.moodle_support import run_data_driven_suite  # noqa: E402

DATA_FILE = ROOT / "test_data.csv"
CONFIG_FILE = ROOT / "test_config.csv"
RESULT_FILE = ROOT / "test_results.csv"

REQUIRED_COLUMNS = {
    "test_case_id", "test_case_name", "group", "action",
    "expected_result", "expected_status", "expected_errors",
    "expected_lengths",
}

BY_TYPES = {
    "id": By.ID,
    "name": By.NAME,
    "css": By.CSS_SELECTOR,
    "xpath": By.XPATH,
    "tag": By.TAG_NAME,
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


def read_config():
    with CONFIG_FILE.open("r", encoding="utf-8-sig", newline="") as source:
        reader = csv.DictReader(source)
        required = {"item_type", "key", "by", "value"}

        if not reader.fieldnames or not required.issubset(reader.fieldnames):
            raise ValueError(
                "test_config.csv must contain item_type,key,by,value."
            )

        rows = list(reader)

    urls, locators = {}, {}

    for row in rows:
        kind = (row["item_type"] or "").strip().lower()
        key = (row["key"] or "").strip()
        value = (row["value"] or "").strip()

        if not key:
            continue

        if kind == "url":
            urls[key] = value

        elif kind == "element":
            by = (row["by"] or "").strip().lower()

            if by not in BY_TYPES or not value:
                raise ValueError(
                    f"Invalid locator configuration for '{key}'."
                )

            locators[key] = (BY_TYPES[by], value)

        else:
            raise ValueError(
                f"Unsupported item_type '{kind}' in test_config.csv."
            )

    required_urls = {"base_url", "login_path", "add_user_path"}

    if not required_urls.issubset(urls) or not all(
        urls[key] for key in required_urls
    ):
        raise ValueError(
            "test_config.csv must define base_url, login_path and add_user_path."
        )

    required_locators = {
        "login_username", "login_password", "login_button",
        "username", "password", "password_edit",
        "firstname", "lastname", "email",
        "auth", "maildisplay", "moodlenetprofile",
        "city", "country", "timezone", "lang",
        "description", "picturedescription",
        "firstnamephonetic", "lastnamephonetic",
        "middlename", "alternatename", "interests",
        "idnumber", "institution", "department",
        "phone1", "phone2", "address", "newpicture",
        "suspended", "generatepassword", "forcepasswordchange",
        "save", "cancel", "body",
        "error_username", "error_firstname",
        "error_lastname", "error_email",
    }

    missing = required_locators - set(locators)

    if missing:
        raise ValueError(
            "Missing locators in test_config.csv: "
            + ", ".join(sorted(missing))
        )

    return urls, locators


def main():
    parser = argparse.ArgumentParser(description=__doc__)

    parser.add_argument(
        "--case",
        action="append",
        help="Run one test case ID; repeat to select multiple."
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List available test cases."
    )
    parser.add_argument(
        "--headed",
        action="store_true",
        help="Show the browser window."
    )
    parser.add_argument(
        "--browser",
        choices=("chrome", "edge"),
        default="chrome"
    )

    args = parser.parse_args()

    try:
        rows = read_test_data()
        urls, locators = read_config()
    except (OSError, ValueError) as exc:
        parser.error(str(exc))

    known = {row["test_case_id"].strip() for row in rows}
    unknown = set(args.case or ()) - known

    if unknown:
        parser.error(
            "Unknown test case ID: " + ", ".join(sorted(unknown))
        )

    selected = [
        row for row in rows
        if not args.case or row["test_case_id"].strip() in args.case
    ]

    if args.list:
        for row in selected:
            print(
                f"{row['test_case_id']} | "
                f"{row['group']} | {row['test_case_name']}"
            )
        return 0

    admin_user = os.getenv("MOODLE_ADMIN_USER", "")
    admin_password = os.getenv("MOODLE_ADMIN_PASSWORD", "")

    if not admin_user or not admin_password:
        parser.error(
            "Set MOODLE_ADMIN_USER and MOODLE_ADMIN_PASSWORD before running tests."
        )

    base_url = os.getenv(
        "MOODLE_BASE_URL",
        urls["base_url"]
    ).rstrip("/")

    timeout = int(os.getenv("MOODLE_TIMEOUT", "30"))

    return run_data_driven_suite(
        rows=selected,
        locators=locators,
        base_url=base_url,
        login_path=urls["login_path"],
        add_user_path=urls["add_user_path"],
        admin_user=admin_user,
        admin_password=admin_password,
        browser_name=args.browser,
        headed=args.headed,
        timeout=timeout,
        root=ROOT,
        result_file=RESULT_FILE,
    )


if __name__ == "__main__":
    raise SystemExit(main())
