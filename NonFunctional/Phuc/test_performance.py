"""Non-functional performance test for Moodle Add a Quiz."""

import os
import statistics
import time
from selenium import webdriver
from selenium.common.exceptions import ElementClickInterceptedException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

BASE_URL = os.getenv("MOODLE_BASE_URL", "http://127.0.0.1:9501").rstrip("/")
USERNAME = os.getenv("MOODLE_USERNAME", "")
PASSWORD = os.getenv("MOODLE_PASSWORD", "")
COURSE_ID = os.getenv("MOODLE_COURSE_ID", "4")
SECTION_ID = os.getenv("MOODLE_SECTION_ID", "16")
RUNS = int(os.getenv("PERF_RUNS", "5"))
FORM_THRESHOLD_SEC = 3.0
SUBMIT_THRESHOLD_SEC = 4.0


def summarize(label, values):
    print(
        f"{label}: runs={len(values)}, min={min(values):.3f}s, "
        f"mean={statistics.mean(values):.3f}s, median={statistics.median(values):.3f}s, "
        f"max={max(values):.3f}s"
    )


def main():
    if not USERNAME or not PASSWORD:
        raise RuntimeError("Set MOODLE_USERNAME and MOODLE_PASSWORD environment variables first")

    headless = os.getenv("HEADLESS", "1") != "0"
    options = webdriver.ChromeOptions()
    if headless:
        options.add_argument("--headless=new")
    options.add_argument("--window-size=1440,1000")

    driver = webdriver.Chrome(options=options)
    wait = WebDriverWait(driver, 20)

    form_times = []
    submit_times = []

    try:
        driver.get(f"{BASE_URL}/login/index.php")
        wait.until(EC.visibility_of_element_located((By.ID, "username"))).send_keys(USERNAME)
        driver.find_element(By.ID, "password").send_keys(PASSWORD)
        driver.find_element(By.ID, "loginbtn").click()
        wait.until(lambda d: "/login/" not in d.current_url)

        form_url = (
            f"{BASE_URL}/course/modedit.php?add=quiz&type"
            f"&course={COURSE_ID}&sectionid={SECTION_ID}&return=0&beforemod=0"
        )

        for idx in range(1, RUNS + 1):
            t0 = time.perf_counter()
            driver.get(form_url)
            wait.until(EC.visibility_of_element_located((By.ID, "id_name")))
            t1 = time.perf_counter()
            form_elapsed = t1 - t0
            form_times.append(form_elapsed)

            name_input = driver.find_element(By.ID, "id_name")
            name_input.clear()
            name_input.send_keys(f"Perf_Quiz_{int(time.time())}_{idx}")

            before_url = driver.current_url
            save_btn = wait.until(EC.element_to_be_clickable((By.ID, "id_submitbutton")))
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", save_btn)

            t2 = time.perf_counter()
            try:
                save_btn.click()
            except ElementClickInterceptedException:
                driver.execute_script("arguments[0].click();", save_btn)

            wait.until(lambda d: d.current_url != before_url)
            wait.until(lambda d: d.execute_script("return document.readyState") == "complete")
            t3 = time.perf_counter()
            submit_elapsed = t3 - t2
            submit_times.append(submit_elapsed)

            print(f"[Run {idx}] form_load={form_elapsed:.3f}s | submit_redirect={submit_elapsed:.3f}s")

        print("-" * 64)
        summarize("Form Load Time", form_times)
        summarize("Submit Time", submit_times)

        avg_form = statistics.mean(form_times)
        avg_submit = statistics.mean(submit_times)
        status = "PASS" if (avg_form <= FORM_THRESHOLD_SEC and avg_submit <= SUBMIT_THRESHOLD_SEC) else "WARN/FAIL"
        print(
            f"Threshold check (form<={FORM_THRESHOLD_SEC}s, submit<={SUBMIT_THRESHOLD_SEC}s): {status}"
        )
    finally:
        driver.quit()


if __name__ == "__main__":
    main()