"""Cross-browser and responsive checks for Moodle Add Category (PRJ3 NFR-002)."""

import argparse
import csv
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait


HERE = Path(__file__).resolve().parent
RESULTS_DIR = HERE / "results"
RESULTS_FILE = RESULTS_DIR / "compatibility_results.csv"
BASE_URL = os.getenv("MOODLE_BASE_URL", "http://127.0.0.1:9501").rstrip("/")
LOGIN_PATH = os.getenv("MOODLE_LOGIN_PATH", "/login/index.php")
ADD_CATEGORY_PATH = os.getenv("MOODLE_ADD_CATEGORY_PATH", "/course/editcategory.php?parent=0")
WAIT_SECONDS = int(os.getenv("MOODLE_WAIT_SECONDS", "20"))
VIEWPORTS = {
    "desktop": (1440, 1000),
    "tablet": (768, 1024),
    "mobile": (390, 844),
}
LOG = logging.getLogger("nfr002.compatibility")


def append_results(rows):
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    columns = ["NFR_ID", "Scenario_ID", "Browser", "Viewport", "Expected_Result", "Actual_Result", "Status", "Evidence", "Error_Message", "Timestamp_UTC"]
    write_header = not RESULTS_FILE.exists() or RESULTS_FILE.stat().st_size == 0
    with RESULTS_FILE.open("a", encoding="utf-8-sig", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=columns)
        if write_header:
            writer.writeheader()
        writer.writerows(rows)


def create_driver(browser_name, headed):
    if browser_name == "edge":
        options, start = webdriver.EdgeOptions(), webdriver.Edge
    else:
        options, start = webdriver.ChromeOptions(), webdriver.Chrome
    if not headed:
        options.add_argument("--headless=new")
    options.add_argument("--window-size=1440,1000")
    return start(options=options)


def main(argv=None):
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="backslashreplace")

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--browsers", default=os.getenv("COMPAT_BROWSERS", "chrome,edge"),
                        help="Danh sách chrome,edge; ví dụ --browsers chrome")
    parser.add_argument("--viewports", default="desktop,tablet,mobile",
                        help="Danh sách desktop,tablet,mobile")
    parser.add_argument("--headed", action="store_true", help="Hiện cửa sổ browser")
    args = parser.parse_args(argv)

    browsers = [name.strip().lower() for name in args.browsers.split(",") if name.strip()]
    viewport_names = [name.strip().lower() for name in args.viewports.split(",") if name.strip()]
    if not browsers or any(name not in {"chrome", "edge"} for name in browsers):
        parser.error("--browsers chỉ nhận chrome và/hoặc edge.")
    if not viewport_names or any(name not in VIEWPORTS for name in viewport_names):
        parser.error("--viewports chỉ nhận desktop, tablet và/hoặc mobile.")
    if WAIT_SECONDS < 1:
        parser.error("MOODLE_WAIT_SECONDS phải lớn hơn 0.")
    username, password = os.getenv("MOODLE_USERNAME", ""), os.getenv("MOODLE_PASSWORD", "")
    if not username or not password:
        parser.error("Cần đặt MOODLE_USERNAME và MOODLE_PASSWORD.")

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    rows = []
    for browser_name in browsers:
        driver = None
        active_viewport = "setup"
        try:
            driver = create_driver(browser_name, args.headed)
            driver.set_page_load_timeout(WAIT_SECONDS)
            wait = WebDriverWait(driver, WAIT_SECONDS)
            driver.get(BASE_URL + LOGIN_PATH)
            wait.until(EC.visibility_of_element_located((By.ID, "username"))).send_keys(username)
            driver.find_element(By.ID, "password").send_keys(password)
            driver.find_element(By.ID, "loginbtn").click()
            wait.until(lambda browser: "/login/" not in browser.current_url)

            for viewport_name in viewport_names:
                active_viewport = viewport_name
                width, height = VIEWPORTS[viewport_name]
                # Browser window dimensions include title/tool bars. Set the
                # actual CSS/device viewport so mobile measurements are 390px,
                # not the larger minimum window width reported by the OS.
                driver.set_window_size(max(width, 1440), max(height, 1000))
                driver.execute_cdp_cmd("Emulation.setDeviceMetricsOverride", {
                    "width": width,
                    "height": height,
                    "screenWidth": width,
                    "screenHeight": height,
                    "deviceScaleFactor": 1,
                    # Use a precise CSS viewport for responsive layout checks.
                    # Mobile emulation changes layout width when a page lacks
                    # or customizes its viewport meta tag.
                    "mobile": False,
                })
                driver.get(BASE_URL + ADD_CATEGORY_PATH)
                wait.until(EC.visibility_of_element_located((By.ID, "id_name")))
                wait.until(EC.element_to_be_clickable((By.ID, "id_submitbutton")))
                metrics = driver.execute_script("""
                    const selectors = {name: '#id_name', idnumber: '#id_idnumber', submit: '#id_submitbutton'};
                    const controls = {};
                    const visible = element => {
                      if (!element) return false;
                      const rect = element.getBoundingClientRect();
                      const style = getComputedStyle(element);
                      return rect.width > 0 && rect.height > 0 &&
                        style.display !== 'none' && style.visibility !== 'hidden';
                    };
                    const scrollToControl = element => {
                      if (!element) return null;
                      document.documentElement.style.scrollBehavior = 'auto';
                      document.body.style.scrollBehavior = 'auto';
                      element.scrollIntoView({block: 'center', inline: 'nearest', behavior: 'instant'});
                      let rect = element.getBoundingClientRect();
                      if (rect.top < 0 || rect.bottom > innerHeight) {
                        const root = document.scrollingElement;
                        root.scrollTop += rect.top - (innerHeight - rect.height) / 2;
                        rect = element.getBoundingClientRect();
                      }
                      return rect;
                    };
                    for (const [key, selector] of Object.entries(selectors)) {
                      const element = document.querySelector(selector);
                      const target = visible(element) ? element : null;
                      const rect = scrollToControl(target);
                      controls[key] = {
                        exists: !!element,
                        visible: visible(element),
                        enabled: !!(element && !element.disabled),
                        inViewportX: !!(rect && rect.right > 0 && rect.left < innerWidth),
                        inViewportY: !!(rect && rect.bottom > 0 && rect.top < innerHeight),
                        topAfterScroll: rect ? Math.round(rect.top) : null,
                        bottomAfterScroll: rect ? Math.round(rect.bottom) : null,
                        inViewport: !!(rect && rect.bottom > 0 && rect.top < innerHeight &&
                          rect.right > 0 && rect.left < innerWidth)
                      };
                    }
                    const parentField = document.querySelector('#id_parent');
                    const parentLabel = document.querySelector('label[for="id_parent"]') ||
                      Array.from(document.querySelectorAll('label')).find(label =>
                        /parent category/i.test(label.innerText || label.textContent || ''));
                    const parentContainer = document.querySelector('#fitem_id_parent') ||
                      parentField?.closest('.fitem, .form-group, .mb-3') ||
                      parentLabel?.parentElement?.parentElement || parentField?.parentElement?.parentElement;
                    const parentWidgets = parentContainer
                      ? Array.from(parentContainer.querySelectorAll('input:not([type="hidden"]), button, select, [role="combobox"], [role="listbox"], .form-autocomplete-selection'))
                      : [];
                    const visibleParentWidget = parentWidgets.find(visible);
                    const parentTarget = visible(parentField) ? parentField :
                      visibleParentWidget || (visible(parentLabel) ? parentLabel : null);
                    const parentRect = scrollToControl(parentTarget);
                    controls.parent = {
                      exists: !!parentField || !!visibleParentWidget,
                      visible: visible(parentField) || !!visibleParentWidget || visible(parentLabel),
                      enabled: !!((visibleParentWidget && !visibleParentWidget.disabled) ||
                        (parentField && !parentField.disabled)),
                      inViewportX: !!(parentRect && parentRect.right > 0 && parentRect.left < innerWidth),
                      inViewportY: !!(parentRect && parentRect.bottom > 0 && parentRect.top < innerHeight),
                      topAfterScroll: parentRect ? Math.round(parentRect.top) : null,
                      bottomAfterScroll: parentRect ? Math.round(parentRect.bottom) : null,
                      inViewport: !!(parentRect && parentRect.bottom > 0 && parentRect.top < innerHeight &&
                        parentRect.right > 0 && parentRect.left < innerWidth)
                    };
                    return {
                      viewportWidth: innerWidth,
                      documentWidth: document.documentElement.scrollWidth,
                      requestedWidth: arguments[0],
                      viewportMismatch: Math.abs(innerWidth - arguments[0]),
                      horizontalOverflow: Math.max(0, document.documentElement.scrollWidth - arguments[0]),
                      controls
                    };
                """, width)
                controls = metrics["controls"]
                missing = [key for key in ("name", "idnumber", "parent", "submit")
                           if not controls[key]["exists"] or not controls[key]["visible"]]
                unusable = [key for key in ("name", "submit")
                            if not controls[key]["enabled"] or not controls[key]["inViewport"]]
                if metrics["viewportMismatch"] > 1:
                    unusable.append("viewport")
                overflow = metrics["horizontalOverflow"]
                passed = not missing and not unusable and overflow <= 20
                status = "PASS" if passed else "FAIL"
                evidence = (f"window={width}x{height}; requestedWidth={metrics['requestedWidth']}; "
                            f"viewportWidth={metrics['viewportWidth']}; viewportMismatch={metrics['viewportMismatch']}px; "
                            f"documentWidth={metrics['documentWidth']}; horizontalOverflow={overflow}px; "
                            f"controls={controls}; missing={missing}; unusable={unusable}")
                rows.append({"NFR_ID": "NFR-002", "Scenario_ID": f"NFR-002-{viewport_name.upper()}",
                             "Browser": browser_name, "Viewport": f"{width}x{height}",
                             "Expected_Result": "Các trường Name, ID, Parent và nút Submit hiển thị; Name/Submit dùng được; không tràn ngang quá 20px.",
                             "Actual_Result": evidence, "Status": status, "Evidence": evidence,
                             "Error_Message": "", "Timestamp_UTC": datetime.now(timezone.utc).isoformat()})
                print(f"NFR-002 | {browser_name} | {viewport_name} {width}x{height} | {status} | overflow={overflow}px")
        except Exception as exc:
            LOG.exception("Compatibility run failed for %s at %s", browser_name, active_viewport)
            rows.append({"NFR_ID": "NFR-002", "Scenario_ID": "NFR-002-SETUP",
                         "Browser": browser_name, "Viewport": active_viewport,
                         "Expected_Result": "Browser đăng nhập được và tải được Add Category form.",
                         "Actual_Result": f"Scenario không hoàn tất: {type(exc).__name__}: {exc}",
                         "Status": "ERROR", "Evidence": "Không có đầy đủ phép đo cho browser này.",
                         "Error_Message": f"{type(exc).__name__}: {exc}", "Timestamp_UTC": datetime.now(timezone.utc).isoformat()})
        finally:
            if driver is not None:
                try:
                    driver.quit()
                except Exception:
                    LOG.exception("Could not close %s cleanly", browser_name)

    append_results(rows)
    failed = sum(row["Status"] == "FAIL" for row in rows)
    errors = sum(row["Status"] == "ERROR" for row in rows)
    passed = sum(row["Status"] == "PASS" for row in rows)
    print(f"\nNFR-002 Compatibility: PASS={passed}, FAIL={failed}, ERROR={errors}")
    print(f"Report: {RESULTS_FILE}")
    return 1 if failed or errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
