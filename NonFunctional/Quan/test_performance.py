import argparse
import csv
import os
import statistics
import sys
import time
import unittest
from pathlib import Path

from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = ROOT.parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from common.moodle_support import make_driver, login  # noqa: E402

BASE_URL = os.getenv("MOODLE_BASE_URL", "http://127.0.0.1:9501").rstrip("/")
LOGIN_URL = BASE_URL + "/login/index.php"
ADD_USER_URL = BASE_URL + "/user/editadvanced.php?id=-1"

ADMIN_USER = os.getenv("MOODLE_ADMIN_USER", "")
ADMIN_PASSWORD = os.getenv("MOODLE_ADMIN_PASSWORD", "")

TIMEOUT = int(os.getenv("MOODLE_TIMEOUT", "30"))
MEDIAN_THRESHOLD_SECONDS = float(
    os.getenv("PERF_MEDIAN_THRESHOLD", "2.0")
)
MAX_THRESHOLD_SECONDS = float(
    os.getenv("PERF_MAX_THRESHOLD", "5.0")
)


class AddUserPerformanceTest(unittest.TestCase):
    browser = "chrome"
    headed = False
    runs = 5

    @classmethod
    def setUpClass(cls):
        if not ADMIN_USER or not ADMIN_PASSWORD:
            raise RuntimeError(
                "Set MOODLE_ADMIN_USER and MOODLE_ADMIN_PASSWORD first."
            )

        cls.driver = make_driver(cls.browser, cls.headed)
        cls.addClassCleanup(cls.driver.quit)
        cls.wait = WebDriverWait(cls.driver, TIMEOUT)

        # Login happens before measurement and is excluded.
        login(
            cls.driver,
            cls.wait,
            LOGIN_URL,
            ADD_USER_URL,
            ADMIN_USER,
            ADMIN_PASSWORD,
        )

    def open_form_and_measure(self):
        started = time.perf_counter()

        self.driver.get(ADD_USER_URL)

        # Wait until important controls are ready.
        self.wait.until(
            EC.visibility_of_element_located((By.ID, "id_username"))
        )
        self.wait.until(
            EC.element_to_be_clickable((By.ID, "id_submitbutton"))
        )

        return time.perf_counter() - started

    def write_results(self, durations, error=""):
        result_file = ROOT / "performance_results.csv"

        median = statistics.median(durations) if durations else ""
        slowest = max(durations) if durations else ""

        median_pass = (
            bool(durations)
            and median <= MEDIAN_THRESHOLD_SECONDS
        )
        max_pass = (
            bool(durations)
            and slowest <= MAX_THRESHOLD_SECONDS
        )

        fields = [
            "browser",
            "run",
            "duration_seconds",
            "median_seconds",
            "max_seconds",
            "median_threshold_seconds",
            "max_threshold_seconds",
            "median_status",
            "max_status",
            "error",
        ]

        with result_file.open("w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fields)
            writer.writeheader()

            for i, duration in enumerate(durations, 1):
                writer.writerow(
                    {
                        "browser": self.browser,
                        "run": i,
                        "duration_seconds": f"{duration:.3f}",
                        "median_seconds": f"{median:.3f}",
                        "max_seconds": f"{slowest:.3f}",
                        "median_threshold_seconds":
                            MEDIAN_THRESHOLD_SECONDS,
                        "max_threshold_seconds":
                            MAX_THRESHOLD_SECONDS,
                        "median_status":
                            "PASS" if median_pass else "FAIL",
                        "max_status":
                            "PASS" if max_pass else "FAIL",
                        "error": error,
                    }
                )

        print(f"Performance results: {result_file}", flush=True)

    def test_form_response_time(self):
        # Warm-up run: excluded from measurements.
        self.open_form_and_measure()

        durations = []
        measurement_error = ""

        try:
            for run_number in range(1, self.runs + 1):
                try:
                    duration = self.open_form_and_measure()
                    durations.append(duration)

                    print(
                        f"Run {run_number}/{self.runs}: "
                        f"{duration:.3f}s",
                        flush=True,
                    )

                except Exception as exc:
                    measurement_error = (
                        f"Run {run_number}: {exc}"
                    )
                    raise

        finally:
            # Save collected measurements even if a later run fails.
            self.write_results(durations, measurement_error)

        median = statistics.median(durations)
        slowest = max(durations)

        print(
            "Form ready samples (s): "
            + ", ".join(f"{x:.3f}" for x in durations)
            + f"; median={median:.3f}s; max={slowest:.3f}s",
            flush=True,
        )

        self.assertLessEqual(
            median,
            MEDIAN_THRESHOLD_SECONDS,
            f"Median form-ready time exceeded "
            f"{MEDIAN_THRESHOLD_SECONDS:.1f}s.",
        )

        self.assertLessEqual(
            slowest,
            MAX_THRESHOLD_SECONDS,
            f"Slowest form-ready time exceeded "
            f"{MAX_THRESHOLD_SECONDS:.1f}s.",
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)

    parser.add_argument(
        "--browser",
        choices=("chrome", "edge"),
        default="chrome",
    )
    parser.add_argument("--headed", action="store_true")
    parser.add_argument(
        "--runs",
        type=int,
        default=int(os.getenv("PERF_RUNS", "5")),
    )

    args, unittest_args = parser.parse_known_args()

    if args.runs < 1:
        parser.error("--runs must be greater than zero.")

    AddUserPerformanceTest.browser = args.browser
    AddUserPerformanceTest.headed = args.headed
    AddUserPerformanceTest.runs = args.runs

    unittest.main(
        argv=[__file__, *unittest_args],
        verbosity=2,
    )
