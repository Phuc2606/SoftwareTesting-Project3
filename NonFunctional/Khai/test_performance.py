"""Performance checks for Moodle's Add Category flow (PRJ3 NFR-001)."""

import argparse
import csv
import logging
import os
import statistics
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from selenium import webdriver
from selenium.common.exceptions import ElementClickInterceptedException, TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait


HERE = Path(__file__).resolve().parent
RESULTS_DIR = HERE / "results"
RESULTS_FILE = RESULTS_DIR / "performance_results.csv"
BASE_URL = os.getenv("MOODLE_BASE_URL", "http://127.0.0.1:9501").rstrip("/")
LOGIN_PATH = os.getenv("MOODLE_LOGIN_PATH", "/login/index.php")
ADD_CATEGORY_PATH = os.getenv("MOODLE_ADD_CATEGORY_PATH", "/course/editcategory.php?parent=0")
CATEGORY_MANAGEMENT_PATH = os.getenv("MOODLE_CATEGORY_MANAGEMENT_PATH", "/course/management.php?categoryid=0")
WAIT_SECONDS = int(os.getenv("MOODLE_WAIT_SECONDS", "20"))
LOAD_THRESHOLD_SECONDS = float(os.getenv("PERF_LOAD_THRESHOLD_SECONDS", "3"))
SUBMIT_THRESHOLD_SECONDS = float(os.getenv("PERF_SUBMIT_THRESHOLD_SECONDS", "5"))
LOG = logging.getLogger("nfr001.performance")


def csv_append(rows):
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    columns = ["Run_ID", "Test_ID", "Run", "Execution_Time_Seconds", "Threshold_Seconds", "Status", "Evidence", "Timestamp_UTC"]
    write_header = not RESULTS_FILE.exists() or RESULTS_FILE.stat().st_size == 0
    with RESULTS_FILE.open("a", encoding="utf-8-sig", newline="") as result_file:
        writer = csv.DictWriter(result_file, fieldnames=columns)
        if write_header:
            writer.writeheader()
        writer.writerows(rows)


def create_driver(browser, headed):
    if browser == "edge":
        options = webdriver.EdgeOptions()
        start = webdriver.Edge
    else:
        options = webdriver.ChromeOptions()
        start = webdriver.Chrome
    if not headed:
        options.add_argument("--headless=new")
    options.add_argument("--window-size=1440,1000")
    return start(options=options)


def click_submit(driver, button):
    """Scroll the button clear of Moodle's sticky footer before submitting."""
    driver.execute_script("arguments[0].scrollIntoView({block: 'center', inline: 'nearest'});", button)
    try:
        button.click()
    except ElementClickInterceptedException:
        # Some Moodle themes keep a sticky footer over the form's submit button.
        driver.execute_script("arguments[0].click();", button)


def summarize(label, timings, threshold, all_completed):
    average = statistics.mean(timings)
    median = statistics.median(timings)
    stdev = statistics.stdev(timings) if len(timings) > 1 else 0.0
    within_threshold = all(value <= threshold for value in timings)
    status = "PASS" if within_threshold and all_completed else "FAIL"
    print(f"\n{label}")
    print("Runs:", len(timings))
    print("Times:", ", ".join(f"{value:.3f}s" for value in timings))
    print(f"Min: {min(timings):.3f}s | Max: {max(timings):.3f}s | Mean: {average:.3f}s | Median: {median:.3f}s | Std dev: {stdev:.3f}s")
    print(f"Threshold: <= {threshold:.3f}s | Result: {status}")
    return status


def main(argv=None):
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="backslashreplace")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs", type=int, default=int(os.getenv("PERF_RUNS", "5")), help="Số lần đo cho mỗi scenario (tối thiểu 5)")
    parser.add_argument("--browser", choices=("chrome", "edge"), default="chrome")
    parser.add_argument("--headed", action="store_true", help="Hiện cửa sổ browser")
    parser.add_argument("--load-threshold", type=float, default=LOAD_THRESHOLD_SECONDS)
    parser.add_argument("--submit-threshold", type=float, default=SUBMIT_THRESHOLD_SECONDS)
    args = parser.parse_args(argv)
    if args.runs < 5:
        parser.error("--runs phải từ 5 trở lên; một lần chạy đầu được dùng làm warm-up riêng.")
    if args.load_threshold <= 0 or args.submit_threshold <= 0:
        parser.error("Threshold phải lớn hơn 0.")
    username, password = os.getenv("MOODLE_USERNAME", ""), os.getenv("MOODLE_PASSWORD", "")
    if not username or not password:
        parser.error("Cần đặt MOODLE_USERNAME và MOODLE_PASSWORD trước khi chạy.")
    if WAIT_SECONDS < 1:
        parser.error("MOODLE_WAIT_SECONDS phải lớn hơn 0.")

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    driver = None
    run_id = uuid4().hex[:10]
    records = []
    load_times, submit_times = [], []
    load_completed, submit_completed = True, True
    try:
        driver = create_driver(args.browser, args.headed)
        driver.set_page_load_timeout(WAIT_SECONDS)
        wait = WebDriverWait(driver, WAIT_SECONDS)

        # Login time is setup and is deliberately excluded from both metrics.
        driver.get(BASE_URL + LOGIN_PATH)
        wait.until(EC.visibility_of_element_located((By.ID, "username"))).send_keys(username)
        driver.find_element(By.ID, "password").send_keys(password)
        driver.find_element(By.ID, "loginbtn").click()
        wait.until(lambda browser: "/login/" not in browser.current_url)

        def open_form_ready():
            driver.get(BASE_URL + ADD_CATEGORY_PATH)
            wait.until(EC.visibility_of_element_located((By.ID, "id_name")))
            wait.until(EC.element_to_be_clickable((By.ID, "id_submitbutton")))

        # One warm-up, excluded from reported samples.
        open_form_ready()
        LOG.info("Warm-up completed; login and warm-up are excluded from timing.")

        for run_number in range(1, args.runs + 1):
            started = time.perf_counter()
            open_form_ready()
            elapsed = time.perf_counter() - started
            load_times.append(elapsed)
            status = "PASS" if elapsed <= args.load_threshold else "FAIL"
            evidence = "Name input visible and Create category button clickable."
            records.append({"Run_ID": run_id, "Test_ID": "NFR-001-S1", "Run": run_number,
                            "Execution_Time_Seconds": f"{elapsed:.4f}", "Threshold_Seconds": args.load_threshold,
                            "Status": status, "Evidence": evidence, "Timestamp_UTC": datetime.now(timezone.utc).isoformat()})
            print(f"[Load {run_number}/{args.runs}] {elapsed:.3f}s — {status}")

        # Submit warm-up uses its own unique record and is excluded from samples.
        open_form_ready()
        warmup_name, warmup_id = f"NFRPerf_{run_id}_warmup", f"NFRPERF_{run_id}_warmup"
        driver.find_element(By.ID, "id_name").send_keys(warmup_name)
        driver.find_element(By.ID, "id_idnumber").send_keys(warmup_id)
        warmup_submit = wait.until(EC.element_to_be_clickable((By.ID, "id_submitbutton")))
        click_submit(driver, warmup_submit)
        wait.until(lambda browser: browser.execute_script("return document.readyState") == "complete")
        driver.get(BASE_URL + CATEGORY_MANAGEMENT_PATH)
        wait.until(EC.visibility_of_element_located((By.TAG_NAME, "body")))
        wait.until(lambda browser: warmup_name in browser.find_element(By.TAG_NAME, "body").text
                   and warmup_id in browser.find_element(By.TAG_NAME, "body").text)
        LOG.info("Submit warm-up completed and verified; excluded from measurements.")

        for run_number in range(1, args.runs + 1):
            open_form_ready()
            suffix = f"{run_id}_{run_number}"
            category_name, idnumber = f"NFRPerf_{suffix}", f"NFRPERF_{suffix}"
            name_field = driver.find_element(By.ID, "id_name")
            id_field = driver.find_element(By.ID, "id_idnumber")
            name_field.clear()
            name_field.send_keys(category_name)
            id_field.clear()
            id_field.send_keys(idnumber)
            submit = wait.until(EC.element_to_be_clickable((By.ID, "id_submitbutton")))

            # Time from the click through a server response and confirmation that
            # this exact category is visible in Moodle's category management list.
            started = time.perf_counter()
            click_submit(driver, submit)
            wait.until(lambda browser: browser.execute_script("return document.readyState") == "complete")
            driver.get(BASE_URL + CATEGORY_MANAGEMENT_PATH)
            wait.until(EC.visibility_of_element_located((By.TAG_NAME, "body")))
            try:
                wait.until(lambda browser: category_name in browser.find_element(By.TAG_NAME, "body").text
                           and idnumber in browser.find_element(By.TAG_NAME, "body").text)
                elapsed = time.perf_counter() - started
                status = "PASS" if elapsed <= args.submit_threshold else "FAIL"
                evidence = f"Category {category_name!r} and ID {idnumber!r} visible in management list."
            except TimeoutException:
                elapsed = time.perf_counter() - started
                status = "FAIL"
                submit_completed = False
                evidence = f"Category/ID not found in management list; URL={driver.current_url}; page={driver.find_element(By.TAG_NAME, 'body').text[:500]}"
            submit_times.append(elapsed)
            records.append({"Run_ID": run_id, "Test_ID": "NFR-001-S2", "Run": run_number,
                            "Execution_Time_Seconds": f"{elapsed:.4f}", "Threshold_Seconds": args.submit_threshold,
                            "Status": status, "Evidence": evidence, "Timestamp_UTC": datetime.now(timezone.utc).isoformat()})
            print(f"[Submit {run_number}/{args.runs}] {elapsed:.3f}s — {status}")

        load_status = summarize("Scenario 1 — Load Add Category form", load_times, args.load_threshold, load_completed)
        submit_status = summarize("Scenario 2 — Submit and verify category in list", submit_times, args.submit_threshold, submit_completed)
        csv_append(records)
        print(f"\nReport: {RESULTS_FILE}")
        print(f"Generated categories use prefix NFRPerf_{run_id}_ and are left for manual review/cleanup.")
        return 0 if load_status == "PASS" and submit_status == "PASS" else 1
    except Exception as exc:
        LOG.exception("Performance run failed during setup or measurement")
        print(f"ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        if records:
            csv_append(records)
            print(f"Partial report: {RESULTS_FILE}")
        return 2
    finally:
        if driver is not None:
            try:
                driver.quit()
            except Exception:
                LOG.exception("Could not close browser cleanly")


if __name__ == "__main__":
    raise SystemExit(main())
