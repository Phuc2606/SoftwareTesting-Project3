"""Measure the Moodle Groups page-open time."""

import argparse
import os
from statistics import median
from time import perf_counter
import unittest
from urllib.parse import urlencode

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as ec
from selenium.webdriver.support.ui import WebDriverWait


GROUPS = (By.ID, "groups")
CREATE = (By.ID, "showcreateorphangroupform")
SAMPLES = 7
MEDIAN_LIMIT_SECONDS = 2.0
MAX_LIMIT_SECONDS = 5.0


class GroupsPerformanceTest(unittest.TestCase):
    browser = "chrome"
    headed = False

    @classmethod
    def setUpClass(cls):
        base_url = os.environ.get("MOODLE_BASE_URL", "http://localhost:8082").rstrip("/")
        username = os.environ.get("MOODLE_USERNAME")
        password = os.environ.get("MOODLE_PASSWORD")
        course_id = os.environ.get("MOODLE_COURSE_ID", "")
        if not username or not password or not course_id.isdecimal():
            raise RuntimeError("Set MOODLE_USERNAME, MOODLE_PASSWORD and MOODLE_COURSE_ID")
        if cls.browser == "edge":
            options = webdriver.EdgeOptions()
            start_driver = webdriver.Edge
        else:
            options = webdriver.ChromeOptions()
            start_driver = webdriver.Chrome
        if not cls.headed:
            options.add_argument("--headless=new")
        options.add_argument("--window-size=1440,1100")
        cls.driver = start_driver(options=options)
        cls.addClassCleanup(cls.driver.quit)
        cls.driver.set_page_load_timeout(20)
        cls.wait = WebDriverWait(cls.driver, 12)
        cls.groups_url = base_url + "/group/index.php?" + urlencode({"id": course_id, "lang": "en"})
        cls.driver.get(base_url + "/login/index.php?lang=en")
        cls.wait.until(ec.visibility_of_element_located((By.ID, "username"))).send_keys(username)
        cls.driver.find_element(By.ID, "password").send_keys(password)
        cls.driver.find_element(By.ID, "loginbtn").click()
        cls.open_groups()

    @classmethod
    def open_groups(cls):
        cls.driver.get(cls.groups_url)
        groups = cls.wait.until(ec.visibility_of_element_located(GROUPS))
        cls.wait.until(ec.element_to_be_clickable(CREATE))
        return groups

    def test_nf_002_001_groups_open_performance(self):
        """NF-002-001: Groups page becomes usable within the local performance budget."""
        self.open_groups()  # Warm the browser and server before taking samples.
        timings = []
        for _ in range(SAMPLES):
            started = perf_counter()
            self.open_groups()
            timings.append(perf_counter() - started)
        typical, slowest = median(timings), max(timings)
        print(
            f"Samples (s): {', '.join(f'{sample:.3f}' for sample in timings)}; "
            f"median={typical:.3f}s; max={slowest:.3f}s",
            flush=True,
        )
        self.assertLessEqual(typical, MEDIAN_LIMIT_SECONDS, "Median page-open time")
        self.assertLessEqual(slowest, MAX_LIMIT_SECONDS, "Slowest page-open time")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--browser", choices=("chrome", "edge"), default="chrome")
    parser.add_argument("--headed", action="store_true")
    args, unittest_args = parser.parse_known_args()
    GroupsPerformanceTest.browser = args.browser
    GroupsPerformanceTest.headed = args.headed
    unittest.main(argv=[__file__, *unittest_args], verbosity=2)
