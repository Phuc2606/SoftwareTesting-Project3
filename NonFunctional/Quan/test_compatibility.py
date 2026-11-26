import argparse
import csv
import os
import sys
from pathlib import Path
import unittest

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
MAX_HORIZONTAL_OVERFLOW = int(os.getenv("MAX_HORIZONTAL_OVERFLOW", "40"))

VIEWPORTS = (
    ("desktop", 1440, 1000),
    ("tablet", 768, 1024),
    ("mobile", 390, 844),
)

CONTROLS = {
    "username": (By.ID, "id_username"),
    "firstname": (By.ID, "id_firstname"),
    "email": (By.ID, "id_email"),
    "save": (By.ID, "id_submitbutton"),
}


class AddUserCompatibilityTest(unittest.TestCase):
    browser = "chrome"
    headed = False

    @classmethod
    def setUpClass(cls):
        if not ADMIN_USER or not ADMIN_PASSWORD:
            raise RuntimeError(
                "Set MOODLE_ADMIN_USER and MOODLE_ADMIN_PASSWORD first."
            )

        cls.driver = make_driver(cls.browser, cls.headed)
        cls.addClassCleanup(cls.driver.quit)
        cls.addClassCleanup(
            lambda: cls.driver.execute_cdp_cmd(
                "Emulation.clearDeviceMetricsOverride", {}
            )
        )

        cls.wait = WebDriverWait(cls.driver, TIMEOUT)

        login(
            cls.driver,
            cls.wait,
            LOGIN_URL,
            ADD_USER_URL,
            ADMIN_USER,
            ADMIN_PASSWORD,
        )

    def write_results(self, results):
        result_file = ROOT / "compatibility_results.csv"

        fields = [
            "browser",
            "viewport",
            "target_width",
            "target_height",
            "actual_width",
            "document_width",
            "overflow_px",
            "username_visible",
            "firstname_visible",
            "email_visible",
            "save_visible",
            "status",
            "error",
        ]

        with result_file.open("w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fields)
            writer.writeheader()
            writer.writerows(results)

        print(f"Compatibility results: {result_file}", flush=True)

    def test_form_controls_render_at_supported_viewports(self):
        results = []

        try:
            for name, width, height in VIEWPORTS:
                with self.subTest(viewport=name):
                    result = {
                        "browser": self.browser,
                        "viewport": name,
                        "target_width": width,
                        "target_height": height,
                        "actual_width": "",
                        "document_width": "",
                        "overflow_px": "",
                        "username_visible": False,
                        "firstname_visible": False,
                        "email_visible": False,
                        "save_visible": False,
                        "status": "FAIL",
                        "error": "",
                    }

                    try:
                        # Set the actual CSS viewport through Chrome DevTools.
                        self.driver.execute_cdp_cmd(
                            "Emulation.setDeviceMetricsOverride",
                            {
                                "width": width,
                                "height": height,
                                "deviceScaleFactor": 1,
                                "mobile": width <= 480,
                            },
                        )

                        self.driver.get(ADD_USER_URL)

                        self.wait.until(
                            lambda d: d.execute_script(
                                "return window.innerWidth"
                            ) == width
                        )

                        # Check important form controls.
                        for key, locator in CONTROLS.items():
                            element = self.wait.until(
                                EC.visibility_of_element_located(locator)
                            )

                            result[f"{key}_visible"] = element.is_displayed()

                            self.assertTrue(
                                result[f"{key}_visible"],
                                f"{key} is not visible at {name}.",
                            )

                        # Measure horizontal overflow.
                        dimensions = self.driver.execute_script(
                            """
                            return {
                                width: window.innerWidth,
                                documentWidth:
                                    document.documentElement.scrollWidth
                            };
                            """
                        )

                        actual_width = dimensions["width"]
                        document_width = dimensions["documentWidth"]
                        overflow = max(0, document_width - actual_width)

                        result["actual_width"] = actual_width
                        result["document_width"] = document_width
                        result["overflow_px"] = overflow

                        print(
                            f"{self.browser} {name} "
                            f"{width}x{height}: "
                            f"document={document_width}px, "
                            f"overflow={overflow}px",
                            flush=True,
                        )

                        self.assertLessEqual(
                            overflow,
                            MAX_HORIZONTAL_OVERFLOW,
                            f"Horizontal overflow is {overflow}px "
                            f"at {name}; allowed maximum is "
                            f"{MAX_HORIZONTAL_OVERFLOW}px.",
                        )

                        result["status"] = "PASS"

                    except Exception as exc:
                        result["error"] = str(exc).replace("\n", " ")
                        raise

                    finally:
                        results.append(result)

        finally:
            # Preserve collected results even if a viewport fails.
            self.write_results(results)


if __name__ == "__main__":

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--browser",
        choices=("chrome", "edge"),
        default="chrome",
    )
    parser.add_argument("--headed", action="store_true")

    args, unittest_args = parser.parse_known_args()

    AddUserCompatibilityTest.browser = args.browser
    AddUserCompatibilityTest.headed = args.headed

    unittest.main(
        argv=[__file__, *unittest_args],
        verbosity=2,
    )
