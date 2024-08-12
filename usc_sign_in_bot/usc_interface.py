import os

from datetime import datetime as dt, timedelta

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoSuchElementException
from webdriver_manager.chrome import ChromeDriverManager
from dotenv import load_dotenv


# Define the URL of the webpage you want to fetch
USC_URL = 'https://my.uscsport.nl/pages/login'

class USC_Interface(webdriver.Chrome):

    def __init__(self, username:str, password:str, uva_login:bool=False):
        service = Service(ChromeDriverManager().install())
        super().__init__(service=service)

        self._login(username, password, uva_login)

    def _login(self, username:str, password:str, uva_login:bool=False) -> None:
        """Login to the my USC environment"""
        self.get(USC_URL)

        if uva_login:
            self._login_with_uva(username, password)

        else:
            raise NotImplementedError("For now it will only work with UVA login, feel free to add it yourself in a pull request!")

    def _login_with_uva(self, username:str, password:str):
        """Call this function to handle the UVA login page"""
        # Start with clicking the button to redirect to the uva login
        self._search_for_element('button[data-test-id="oidc-login-button"]').click()

        # Wait up to 10 seconds for the button to become clickable
        try:
            # Because sometimes it shows this element and other times the other, let's try both
           self._search_for_element('li[data-title="universiteit van amsterdam"]').click()
            
        except Exception as e:
            button = self._search_for_element('input[value="http://login.uva.nl/adfs/services/trust"]')\
                .find_element(By.XPATH, "..")\
                .find_element(By.TAG_NAME, 'button')
            self.execute_script("arguments[0].click();", button)
        
        # Wait for the username field to be present and fill it in
        self._search_for_element('input[id="userNameInput"]')\
            .send_keys(os.environ['UVA_USERNAME'])
        
        # Wait for the password field to be present and fill it in
        self._search_for_element('input[id="passwordInput"]')\
            .send_keys(os.environ['UVA_PASSWORD'])
        
        # Find and click the submit button
        self._search_for_element('span[id="submitButton"]').click()

    def _search_for_element(self, selector_path:str, select_with:webdriver.common.by.By=By.CSS_SELECTOR) -> webdriver.remote.webelement.WebElement:
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
            The type of selector to use (e.g., By.CSS_SELECTOR, By.XPATH, etc.). The default is By.CSS_SELECTOR.

        Returns
        -------
        selenium.webdriver.remote.webelement.WebElement
            The first web element that matches the specified selector.

        Raises
        ------
        selenium.common.exceptions.TimeoutException
        If the element is not found within the specified wait time.
        """
        return WebDriverWait(self, 2).until(
            EC.presence_of_element_located((select_with, selector_path))
        )

    def _select_all_elements(self, selector_path:str, selector_with:webdriver.common.by.By=By.CSS_SELECTOR) -> list[webdriver.remote.webelement.WebElement]:
        """
        Select all web elements matching the given selector path.

        This method waits for all elements that match the specified selector to be present
        on the page and returns them as a list.

        Parameters
        ----------
        selector_path : str
            The selector path used to locate the web elements (e.g., a CSS selector or XPath).
        selector_with : selenium.webdriver.common.by.By, optional
            The type of selector to use (e.g., By.CSS_SELECTOR, By.XPATH). Defaults to By.CSS_SELECTOR.

        Returns
        -------
        list of selenium.webdriver.remote.webelement.WebElement
            A list of web elements that match the specified selector.

        Raises
        ------
        selenium.common.exceptions.TimeoutException
            If the elements are not found within the specified wait time.
        """
        return WebDriverWait(self, 2).until(
            EC.presence_of_all_elements_located((selector_with, selector_path))
        )
    
    def _filter_for_sport(self, sport:str) -> None:
        """Set the filter for the sport we want to filter for"""

        # Click the dropdown menu with the filters
        dropdown = self._search_for_element('i[class="fas text-primary fa-chevron-down"]')
        dropdown.click()

        # Find the right element fitting with the sport
        sports_element = self._search_for_element(f'//li[label[text()="{sport}"]]', select_with=By.XPATH)

        # Click the selection box
        sports_element.find_element(By.TAG_NAME, 'input').click()

        # Click again on the dropdown to make it go away
        dropdown.click()
    
    def _filter_webelements(self, list_of_webelements: list[webdriver.remote.webelement.WebElement], xPathCondition:str) -> list[webdriver.remote.webelement.WebElement]:
        """Filter the elements for a specific XPATH. If it has the XPATH, return the elements"""
        # Create a return list
        filtered_elements = []

    	# Loop over the webelements
        for element in list_of_webelements:
            try:
                # Try to find the elements, append it if it exists, continue if not.
                _ = element.find_element(By.XPATH, xPathCondition)
                filtered_elements.append(element)
            except NoSuchElementException:
                continue
    
        # Return the filtered elements
        return filtered_elements
    
    @staticmethod
    def _extract_info_from_timeslot(slot, day_ahead):
        """Extract the info from a timeslot element"""
        extracted_time : str = slot.find_element(By.CSS_SELECTOR, 'p[data-test-id="bookable-slot-start-time"] > strong').text
        trainer : str = slot.find_element(By.CSS_SELECTOR, 'span[data-test-id="bookable-slot-supervisor-first-name"]').text

        # Comibine the time from the element with the days ahead to a datetime object
        time : dt = dt.combine(
            dt.now() + timedelta(days=day_ahead),
            dt.strptime(extracted_time, "%H:%M").time()
        )

        return {
            "Time": time,
            "trainer": trainer
        }

    def _loop_over_the_days(self, target_days:int, sport:str, function_to_do:exec):
        """Loop over the days in the thingie"""
        days_ahead = 0
        days = self._select_all_elements('a[data-test-id-day-selector="day-selector"]')
        day_length = len(days)

        while days_ahead < target_days:

            if not days:
                # Move foreword for the number of the days shown
                for _ in range(len(day_length)): self._search_for_element('a[data-test-id="advance-one-day-button"]').click()

                # Now select all the days in our new window
                days = self._select_all_elements('a[data-test-id-day-selector="day-selector"]')

            # Get first element
            day = days.pop(0)

            # Click that day with javascript
            self.execute_script("arguments[0].click();", day)

            # Now get the list of sports available
            sorting_slots = self._select_all_elements('div[data-test-id="bookable-slot-list"]')
            slots = self._filter_webelements(sorting_slots, f'.//*[contains(text(), "{sport}")]')

            # Depending on what we loop over for, do different actions
            return [function_to_do(slot, days_ahead) for slot in slots]       

    def get_all_lessons(self, sport:str, days_in_future:int=7):
        """Get a list of all the lessons that are given in the sport"""
        self._filter_for_sport(sport)

        return self._loop_over_the_days(days_in_future, sport, self._extract_info_from_timeslot)

        

        

if __name__ == "__main__":
    load_dotenv()
    driver = USC_Interface(
        os.environ['UVA_USERNAME'],
        os.environ['UVA_PASSWORD'],
        uva_login=True
    )
    trainings = driver.get_all_lessons("Schermen")
    print(trainings)
    driver.close()