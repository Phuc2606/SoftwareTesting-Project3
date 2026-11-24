"""Non-functional compatibility test across browsers and viewports on Moodle Add a Quiz."""

import os
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

BASE_URL = os.getenv("MOODLE_BASE_URL", "http://127.0.0.1:9501").rstrip("/")
USERNAME = os.getenv("MOODLE_USERNAME", "")
PASSWORD = os.getenv("MOODLE_PASSWORD", "")
COURSE_ID = os.getenv("MOODLE_COURSE_ID", "4")
SECTION_ID = os.getenv("MOODLE_SECTION_ID", "16")

BROWSERS = [b.strip().lower() for b in os.getenv("COMPAT_BROWSERS", "chrome,edge").split(",") if b.strip()]
VIEWPORTS = [
    ("desktop", 1440, 1000),
    ("tablet", 768, 1024),
    ("mobile", 390, 844),
]


def create_driver(browser_name, headless=True):
    if browser_name == "chrome":
        opts = webdriver.ChromeOptions()
        if headless:
            opts.add_argument("--headless=new")
        return webdriver.Chrome(options=opts)
    if browser_name == "edge":
        opts = webdriver.EdgeOptions()
        if headless:
            opts.add_argument("--headless=new")
        return webdriver.Edge(options=opts)
    raise ValueError(f"Unsupported browser: {browser_name}")


def run_for_browser(browser_name, headless=True):
    try:
        driver = create_driver(browser_name, headless=headless)
    except Exception as exc:
        print(f"[{browser_name}] SKIPPED ({exc})")
        return

    wait = WebDriverWait(driver, 20)
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
        driver.get(form_url)
        wait.until(EC.visibility_of_element_located((By.ID, "id_name")))

        for vp_name, w, h in VIEWPORTS:
            driver.set_window_size(w, h)
            info = driver.execute_script(
                """
                const nameEl = document.getElementById('id_name');
                const saveEl = document.getElementById('id_submitbutton');
                return {
                    title: document.title,
                    innerWidth: window.innerWidth,
                    scrollWidth: document.documentElement.scrollWidth,
                    nameDisplayed: !!(nameEl && nameEl.offsetParent !== null),
                    saveDisplayed: !!(saveEl && saveEl.offsetParent !== null)
                };
                """
            )
            overflow = info["scrollWidth"] - info["innerWidth"]
            ok = info["nameDisplayed"] and info["saveDisplayed"]
            print(
                f"[{browser_name} | {vp_name} {w}x{h}] status={'PASS' if ok else 'FAIL'} | "
                f"overflow={overflow}px | name={info['nameDisplayed']} | save={info['saveDisplayed']}"
            )
    finally:
        driver.quit()


def main():
    if not USERNAME or not PASSWORD:
        raise RuntimeError("Set MOODLE_USERNAME and MOODLE_PASSWORD environment variables first")

    headless = os.getenv("HEADLESS", "1") != "0"
    for b in BROWSERS:
        run_for_browser(b, headless=headless)


if __name__ == "__main__":
    main()