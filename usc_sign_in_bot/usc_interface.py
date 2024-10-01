"""Module to hold the """
import json
import logging
import os
import time
from datetime import datetime as dt
from datetime import timedelta

from dotenv import load_dotenv
from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException, TimeoutException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager

USC_URL = "https://my.uscsport.nl/pages/login"
TIMEZONE = "Europe/Amsterdam"

with open("shortened_weekdays.json", "r", encoding="UTF-8") as file:
    weekdays = json.load(file)["NL"]

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
# set higher logging level for httpx to avoid all GET and POST requests being logged
logging.getLogger("httpx").setLevel(logging.INFO)
logger = logging.getLogger(__name__)


class UscInterface(webdriver.Chrome):
    """Interface to interact with USC"""

    def __init__(self, username: str, password: str, uva_login: bool = False):
        service = Service(ChromeDriverManager().install())

        chrome_options = Options()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--window-size=1920x1080")

        super().__init__(service=service, options=chrome_options)

        self._set_browser_timezone(TIMEZONE)

        self._login(username, password, uva_login)

    def _login(self, username: str, password: str, uva_login: bool = False) -> None:
        """Login to the my USC environment"""
        self.get(USC_URL)

        if uva_login:
            self._login_with_uva(username, password)

        else:
            raise NotImplementedError(
                "For now it will only work with UVA login, feel free to add it yourself in a pull"+
                "request!"
            )

    def _login_with_uva(self, username: str, password: str):
        """Call this function to handle the UVA login page"""
        # Start with clicking the button to redirect to the uva login
        self._select_element('button[data-test-id="oidc-login-button"]').click()

        # Wait up to 10 seconds for the button to become clickable
        try:
            # Because sometimes it shows this element and other times the other, let's try both
            self._select_element('li[data-title="universiteit van amsterdam"]').click()

        # pylint: disable=broad-exception-caught
        except Exception:
            button = (
                self._select_element(
                    'input[value="http://login.uva.nl/adfs/services/trust"]'
                )
                .find_element(By.XPATH, "..")
                .find_element(By.TAG_NAME, "button")
            )
            self.execute_script("arguments[0].click();", button)

        # Wait for the username field to be present and fill it in
        self._select_element('input[id="userNameInput"]').send_keys(username)

        # Wait for the password field to be present and fill it in
        self._select_element('input[id="passwordInput"]').send_keys(password)

        # Find and click the submit button
        self._select_element('span[id="submitButton"]').click()

        logger.info("UVA login successfull")

    def _log_page_to_output_file(self):
        """Logs the page to html output in case of errors such that it can be inspected where the
        error came from"""
        with open('error_output_page.html', 'w', encoding='utf-8') as file_log:
            file_log.write(self.page_source)

    def _set_browser_timezone(self, timezone):
        self.execute_cdp_cmd("Emulation.setTimezoneOverride", {"timezoneId": timezone})

    def _click_and_find_element(self, css_selector: str) -> None:
        """
        Click an element specified by the CSS selector using JavaScript.

        Parameters
        ----------
        css_selector : str
            The CSS selector of the element to locate and click.

        Returns
        -------
        None
            This function does not return any value.

        Notes
        -----
        This method uses JavaScript to perform the click action on the element, which can
        be useful when the standard Selenium click method is obstructed or fails due to
        overlaying elements or other issues.

        Examples
        --------
        >>> _click_and_find_element('button.submit')
        """
        element = self._select_element(css_selector)
        self.execute_script("arguments[0].click();", element)

    def _select_element(
        self, selector_path: str, select_with: webdriver.common.by.By = By.CSS_SELECTOR
    ) -> webdriver.remote.webelement.WebElement:
        """
        Search for a single web element using a specified selector.

        This method waits for a web element to be present on the page and then returns it.
        The search is conducted based on the selector path provided and the selection method
        (e.g., CSS selector, XPath, etc.).

        Parameters
        ----------
        selector_path : str
            The path of the selector used to locate the web element (e.g., a CSS selector or XPath).
        select_with : selenium.webdriver.common.by.By, optional
            The type of selector to use (e.g., By.CSS_SELECTOR, By.XPATH, etc.). The default is 
            By.CSS_SELECTOR.

        Returns
        -------
        selenium.webdriver.remote.webelement.WebElement
            The first web element that matches the specified selector.

        Raises
        ------
        selenium.common.exceptions.TimeoutException
        If the element is not found within the specified wait time.
        """
        try:
            return WebDriverWait(self, 5).until(
                EC.presence_of_element_located((select_with, selector_path))
            )
        except TimeoutException as timeout_error:
            self._log_page_to_output_file()
            raise timeout_error

    def _select_all_elements(
        self,
        selector_path: str,
        selector_with: webdriver.common.by.By = By.CSS_SELECTOR,
    ) -> list[webdriver.remote.webelement.WebElement]:
        """
        Select all web elements matching the given selector path.

        This method waits for all elements that match the specified selector to be present
        on the page and returns them as a list.

        Parameters
        ----------
        selector_path : str
            # The selector path used to locate the web elements (e.g., a CSS selector or XPath).
        selector_with : selenium.webdriver.common.by.By, optional
            The type of selector to use (e.g., By.CSS_SELECTOR, By.XPATH). Defaults to
            By.CSS_SELECTOR.

        Returns
        -------
        list of selenium.webdriver.remote.webelement.WebElement
            A list of web elements that match the specified selector.

        Raises
        ------
        selenium.common.exceptions.TimeoutException
            If the elements are not found within the specified wait time.
        """
        try:
            return WebDriverWait(self, 10).until(
                EC.presence_of_all_elements_located((selector_with, selector_path))
            )
        except TimeoutException as error:
            self._log_page_to_output_file()
            raise error


    def _filter_for_sport(self, sport: str) -> None:
        """Set the filter for the sport we want to filter for"""

        # Click the dropdown menu with the filters
        dropdown = self._select_element('i[class="fas text-primary fa-chevron-down"]')
        dropdown.click()

        # Find the right element fitting with the sport
        sports_element = self._select_element(
            f'//li[label[text()="{sport}"]]', select_with=By.XPATH
        )

        # Click the selection box
        input_element = sports_element.find_element(By.TAG_NAME, "input")
        self.execute_script("arguments[0].click();", input_element)

        # Click again on the dropdown to make it go away
        dropdown.click()

    def _filter_webelements(
        self,
        list_of_webelements: list[webdriver.remote.webelement.WebElement],
        x_path_condition: str,
    ) -> list[webdriver.remote.webelement.WebElement]:
        """Filter the elements for a specific XPATH. If it has the XPATH, return the elements"""
        # Create a return list
        filtered_elements = []

        # Loop over the webelements
        for element in list_of_webelements:
            try:
                # Try to find the elements, append it if it exists, continue if not.
                _ = element.find_element(By.XPATH, x_path_condition)
                filtered_elements.append(element)
            except NoSuchElementException:
                continue

        # Return the filtered elements
        return filtered_elements

    @staticmethod
    def _extract_info_from_timeslot(slot, day_ahead):
        """Extract the info from a timeslot element"""
        # Sleep such that the slot is loaded correctly
        time.sleep(0.2)
        extracted_time = slot.find_element(
            By.CSS_SELECTOR, 'p[data-test-id="bookable-slot-start-time"] > strong'
        ).text
        trainer: str = slot.find_element(
            By.CSS_SELECTOR, 'span[data-test-id="bookable-slot-supervisor-first-name"]'
        ).text

        if not extracted_time:
            logger.error(f"Time extraction Failed for %s {slot}")
            raise ValueError(f"Time Extraction failed for slot {slot}")

        # Comibine the time from the element with the days ahead to a datetime object
        dt_time: dt = dt.combine(
            dt.now() + timedelta(days=day_ahead - 1),
            dt.strptime(extracted_time, "%H:%M").time(),
        )

        return {"time": dt_time, "trainer": trainer}

    def _loop_over_the_days(self, target_days: int, sport: str, function_to_do: exec):
        """
        Loop over the days to perform a specified action for a given number of days.

        This method iterates over a set number of days, selects each day, and performs
        a specified action (function) for each available sports slot on the selected day.
        The days are advanced if necessary until the target number of days is reached.

        Parameters
        ----------
        target_days : int
            The number of days to loop over from the current selection.
        sport : str
            The name of the sport to filter available slots.
        function_to_do : callable
            A function to be applied to each slot. This function should accept two parameters:
            - A web element representing a slot.
            - An integer representing the current day index.

        Returns
        -------
        list
            A list of results obtained from applying `function_to_do` to each slot.
        """
        days_ahead = 0
        days = self._select_all_elements('a[data-test-id-day-selector="day-selector"]')
        day_length = len(days)
        result = []

        while days_ahead < target_days:

            if not days:
                # Move foreword for the number of the days shown
                for _ in range(day_length):
                    self._click_and_find_element(
                        'a[data-test-id="advance-one-day-button"]'
                    )

                # Now select all the days in our new window
                days = self._select_all_elements(
                    'a[data-test-id-day-selector="day-selector"]'
                )

            # Get first element
            day = days.pop(0)
            days_ahead += 1

            # Click that day with javascript
            self.execute_script("arguments[0].click();", day)

            # Now get the list of sports available
            try:
                sorting_slots = self._select_all_elements(
                    'div[data-test-id="bookable-slot-list"]'
                )
                slots = self._filter_webelements(
                    sorting_slots, f'.//*[contains(text(), "{sport}")]'
                )
            except TimeoutException:
                continue

            # Depending on what we loop over for, do different actions
            result.extend([function_to_do(slot, days_ahead) for slot in slots])

        return result

    def _select_day(self, go_to_date: dt) -> None:
        """Make sure to go to specific day in the USC interface"""
        if go_to_date.date() < dt.today().date():
            raise ValueError("Date is in the past")

        if go_to_date.date() == dt.today().date():
            date_str = "Vandaag"

        else:
            date_str = f"{weekdays[go_to_date.strftime('%w')]} {go_to_date.strftime('%-d-%-m')}"

        while True:
            days = self._select_all_elements(
                'a[data-test-id-day-selector="day-selector"]'
            )
            date_selector = self._filter_webelements(
                days, f'.//*[contains(text(), "{date_str}")]'
            )

            if len(date_selector) > 0:
                break

            for _ in range(len(days)):
                self._select_element('a[data-test-id="advance-one-day-button"]').click()

        self.execute_script("arguments[0].click();", date_selector[0])

    def _click_bookable_right_course(self, sport: str, course_date: dt):
        """Find the right course and click on it. We assume we are allready on the correct day and
        that the course exists"""

        # Start by extracting the rightly formatted time
        time_str = course_date.strftime("%H:%M")

        # Get all the slots in the day
        sorting_slots = self._select_all_elements(
            'div[data-test-id="bookable-slot-list"]'
        )

        # Then filter those sorts for one with the right sport and the right time
        slots = self._filter_webelements(
            sorting_slots, f"*[contains(., '{sport}') and contains(., '{time_str}')]"
        )

        # Assuming there are no slots with the same sport and time there is only one slot left. For
        # that slot find the button for booking and click on that button
        button = slots[0].find_element(
            By.CSS_SELECTOR, 'button[data-test-id="bookable-slot-book-button"]'
        )
        self.execute_script("arguments[0].click()", button)

    def _click_sign_on(self) -> None:
        """We have arrived at the extra information page, now we need to click on the last booking
        button"""
        # First click on the reserve button
        button = self._select_element('button[data-test-id="details-book-button"]')
        self.execute_script("arguments[0].click()", button)

        # Close the details tab by clicking the close button
        self._select_element('button[data-test-id="button-close-modal"]').click()

    def reset_driver(self) -> None:
        """Reset the browser such that the next operation can be performed"""

        while True:
            # Now get the days that are shown in the header
            days = self._select_all_elements(
                'a[data-test-id-day-selector="day-selector"]'
            )

            # If there is an element headed with 'Vandaag' (today), break the loop as we have
            # arrived at the start of history and the driver has been resetted for the next request
            if (
                len(self._filter_webelements(days, "//*[contains(text(), 'Vandaag')]"))
                > 0
            ):
                break

            # Move back one day
            self._select_element(
                '//i[@class="fa fa-chevron-left"]/..', select_with=By.XPATH
            ).click()

    def sign_up_for_lesson(self, sport: str, lesson_date: dt) -> bool:
        """Sign up for a lesson based on day and time and sport"""
        try:
            self._filter_for_sport(sport)
            self._select_day(lesson_date)
            self._click_bookable_right_course(sport, lesson_date)
            self._click_sign_on()

        finally:
            self.reset_driver()

    def get_all_lessons(self, sport: str, days_in_future: int = 7):
        """
        Retrieve a list of all lessons available for a specified sport over a given number of 
        future days.

        This method filters lessons based on the specified sport and then iterates over the
        specified number of future days to collect information about the available lessons.

        Parameters
        ----------
        sport : str
            The name of the sport for which to retrieve the lessons.
        days_in_future : int, optional
            The number of future days to search for available lessons. Defaults to 7 days.

        Returns
        -------
        list
            A list of information extracted from each available timeslot for the specified sport.
        """
        try:

            self._filter_for_sport(sport)

            return self._loop_over_the_days(
                days_in_future, sport, self._extract_info_from_timeslot
            )

        finally:
            self.reset_driver()


if __name__ == "__main__":
    load_dotenv()
    driver = UscInterface(
        os.environ["UVA_USERNAME"], os.environ["UVA_PASSWORD"], uva_login=True
    )
    date = dt(2024, 8, 19, 19, 0, 0)
    driver.sign_up_for_lesson("Schermen", date)

    driver.close()
