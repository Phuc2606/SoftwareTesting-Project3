"""Check keyboard access for the Moodle Create group form."""

import argparse
import os
import unittest
from urllib.parse import urlencode

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as ec
from selenium.webdriver.support.ui import Select, WebDriverWait


GROUPS = (By.ID, "groups")
CREATE = (By.ID, "showcreateorphangroupform")
NAME = (By.ID, "id_name")
CANCEL = (By.ID, "id_cancel")
TAB_LIMIT = 80


class GroupsKeyboardTest(unittest.TestCase):
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

    def focus_by_tab(self, locator):
        target = self.wait.until(ec.visibility_of_element_located(locator))
        active = self.driver.switch_to.active_element
        sequence = []
        for _ in range(TAB_LIMIT):
            if active == target:
                return active
            sequence.append(active.get_dom_attribute("id") or active.tag_name)
            webdriver.ActionChains(self.driver).send_keys(Keys.TAB).perform()
            active = self.driver.switch_to.active_element
        if active == target:
            return active
        self.fail(f"Focus did not reach {locator} within {TAB_LIMIT} Tabs; last stops: {sequence[-12:]}")

    def test_nf_002_002_create_group_keyboard_access(self):
        """NF-002-002: Reach Create group, enter a name and cancel using only the keyboard."""
        before = [option.text for option in Select(self.open_groups()).options]
        self.focus_by_tab(CREATE).send_keys(Keys.ENTER)
        group_name = self.focus_by_tab(NAME)
        group_name.send_keys("Member2 keyboard check")
        self.assertEqual(group_name.get_property("value"), "Member2 keyboard check")
        self.focus_by_tab(CANCEL).send_keys(Keys.ENTER)
        groups = self.wait.until(ec.visibility_of_element_located(GROUPS))
        self.assertEqual([option.text for option in Select(groups).options], before)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--browser", choices=("chrome", "edge"), default="chrome")
    parser.add_argument("--headed", action="store_true")
    args, unittest_args = parser.parse_known_args()
    GroupsKeyboardTest.browser = args.browser
    GroupsKeyboardTest.headed = args.headed
    unittest.main(argv=[__file__, *unittest_args], verbosity=2)
