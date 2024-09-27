# pylint: disable=redefined-outer-name, protected-access
"""Module where you can find the tests for the USC Interface"""

import json
from datetime import datetime as dt
from datetime import timedelta
from unittest.mock import ANY, MagicMock, patch

import pytest
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.common.by import By

from usc_sign_in_bot import UscInterface


@pytest.fixture
def weekdays():
    """Fixture to define weekdays"""
    return json.load(open("shortened_weekdays.json", "r", encoding="UTF-8"))["NL"]


@pytest.fixture
def mock_browser():
    """Fixture for mocking the UscInterface class."""
    with patch(
        "usc_sign_in_bot.usc_interface.webdriver.Chrome", new=MagicMock
    ) as mock_chrome:
        mock_instance = mock_chrome.return_value
        yield mock_instance


@pytest.fixture
def usc_interface():
    """Fixture for creating a UscInterface instance."""
    with patch.object(
        UscInterface, "_login", return_value=None
    ) as _, patch.object(
        UscInterface, "_set_browser_timezone", return_value=None
    ):
        return UscInterface(username="testuser", password="testpass", uva_login=True)


def test_constructor_calls_login_and_set_timezone():
    """Test if constructor calls login and sets the timezone."""
    with patch.object(
        UscInterface, "_login", return_value=None
    ) as mock_login, patch.object(
        UscInterface, "_set_browser_timezone", return_value=None
    ) as mock_set_timezone:
        UscInterface(username="testuser", password="testpass", uva_login=True)

        mock_login.assert_called_once_with("testuser", "testpass", True)
        mock_set_timezone.assert_called_once_with("Europe/Amsterdam")


def test_login_with_uva(usc_interface):
    """Test the UVA login process."""
    with patch.object(
        usc_interface, "_select_element", side_effect=MagicMock()
    ) as mock_select:
        usc_interface._login_with_uva("testuser", "testpass")

        # Check if the correct elements were selected and interacted with
        mock_select.assert_any_call('button[data-test-id="oidc-login-button"]')
        mock_select.assert_any_call('li[data-title="universiteit van amsterdam"]')
        mock_select.assert_any_call('input[id="userNameInput"]')
        mock_select.assert_any_call('input[id="passwordInput"]')
        mock_select.assert_any_call('span[id="submitButton"]')


def test_set_browser_timezone(usc_interface):
    """Test setting the browser timezone."""
    with patch.object(usc_interface, "execute_cdp_cmd") as mock_execute_cmd:
        usc_interface._set_browser_timezone("Europe/Amsterdam")
        mock_execute_cmd.assert_called_once_with(
            "Emulation.setTimezoneOverride", {"timezoneId": "Europe/Amsterdam"}
        )


def test_click_and_find_element(usc_interface):
    """Test clicking an element using JavaScript."""
    with patch.object(
        usc_interface, "execute_script"
    ) as mock_execute_script, patch.object(
        usc_interface, "_select_element", return_value=MagicMock()
    ) as mock_select_element:
        usc_interface._click_and_find_element("button.submit")

        mock_select_element.assert_called_once_with("button.submit")
        mock_execute_script.assert_called_once()


def test_select_element(usc_interface):
    """Test selecting an element."""
    with patch("usc_sign_in_bot.usc_interface.WebDriverWait") as mock_wait:
        mock_element = MagicMock()
        mock_wait.return_value.until.return_value = mock_element

        element = usc_interface._select_element("div.some-element")
        assert element == mock_element

        mock_wait.assert_called_once_with(usc_interface, 5)
        mock_wait.return_value.until.assert_called_once()
        print(mock_wait.return_value.until.list_call_args)
        mock_wait.return_value.until.assert_called_once()


def test_select_all_elements(usc_interface):
    """Test selecting all elements matching a selector."""
    with patch("usc_sign_in_bot.usc_interface.WebDriverWait") as mock_wait:
        mock_element1 = MagicMock()
        mock_element2 = MagicMock()
        mock_wait.return_value.until.return_value = [mock_element1, mock_element2]

        elements = usc_interface._select_all_elements("div.some-element")
        assert elements == [mock_element1, mock_element2]

        mock_wait.assert_called_once_with(usc_interface, 2)
        mock_wait.return_value.until.assert_called_once()


def test_filter_for_sport(usc_interface):
    """Test filtering for a specific sport."""
    with patch.object(
        usc_interface, "_select_element", side_effect=MagicMock()
    ) as mock_select_element, patch.object(
        usc_interface, "execute_script"
    ) as mock_execute_script:
        dropdown_mock = MagicMock()
        sports_element_mock = MagicMock()
        input_element_mock = MagicMock()

        # Mock the dropdown and sports element selection
        mock_select_element.side_effect = [dropdown_mock, sports_element_mock]
        sports_element_mock.find_element.return_value = input_element_mock

        # Call the method
        usc_interface._filter_for_sport("Football")

        # Check if elements were selected and clicked
        mock_select_element.assert_any_call(
            'i[class="fas text-primary fa-chevron-down"]'
        )
        mock_select_element.assert_any_call(
            '//li[label[text()="Football"]]', select_with=By.XPATH
        )
        dropdown_mock.click.assert_called()
        mock_execute_script.assert_called_once_with(
            "arguments[0].click();", input_element_mock
        )


def test_filter_webelements(usc_interface):
    """Test filtering web elements for a specific XPath condition."""
    element1 = MagicMock()
    element2 = MagicMock()
    element3 = MagicMock()

    # Mock find_element calls to simulate finding an element or raising an exception
    element1.find_element.side_effect = NoSuchElementException
    element2.find_element.return_value = MagicMock()  # Assume element is found
    element3.find_element.return_value = MagicMock()  # Assume element is found

    elements = [element1, element2, element3]

    # Call the method
    filtered_elements = usc_interface._filter_webelements(
        elements, "//div[contains(@class, 'desired')]"
    )

    # Assert that only the elements where the XPath was found are returned
    assert filtered_elements == [element2, element3]

    # Check that find_element was called on each element
    element1.find_element.assert_called_once_with(
        By.XPATH, "//div[contains(@class, 'desired')]"
    )
    element2.find_element.assert_called_once_with(
        By.XPATH, "//div[contains(@class, 'desired')]"
    )
    element3.find_element.assert_called_once_with(
        By.XPATH, "//div[contains(@class, 'desired')]"
    )


@patch("time.sleep", return_value=None)
def test_extract_info_from_timeslot(mock_sleep, usc_interface):
    """Test extraction of info from a timeslot."""
    slot = MagicMock()
    slot.find_element.side_effect = [
        MagicMock(text="12:30"),
        MagicMock(text="John Doe"),
    ]

    result = usc_interface._extract_info_from_timeslot(slot, day_ahead=1)

    assert result["time"] == dt.combine(
        dt.now().date(), dt.strptime("12:30", "%H:%M").time()
    )
    assert result["trainer"] == "John Doe"

    slot.find_element.assert_any_call(
        By.CSS_SELECTOR, 'p[data-test-id="bookable-slot-start-time"] > strong'
    )
    slot.find_element.assert_any_call(
        By.CSS_SELECTOR, 'span[data-test-id="bookable-slot-supervisor-first-name"]'
    )
    mock_sleep.assert_called_once()


def test_extract_info_from_timeslot_error_handling(usc_interface):
    """Test error handling in the extraction of info from a timeslot when time extraction fails."""
    slot = MagicMock()
    slot.find_element.side_effect = [
        MagicMock(text=""),  # Empty text to simulate failed time extraction
        MagicMock(text="John Doe"),
    ]

    with pytest.raises(ValueError), patch(
        "usc_sign_in_bot.usc_interface.logger"
    ) as mock_logger:  # Mock logger for error handling
        result = usc_interface._extract_info_from_timeslot(slot, day_ahead=1)

        assert mock_logger.error.called
        mock_logger.error.assert_called_with(f"Time extraction Failed for {slot}")
        assert (
            result["time"] is not None
        )  # Even if time extraction fails, a datetime should still be returned


def test_loop_over_the_days(usc_interface):
    """Test looping over the days to apply a function."""
    with patch.object(
        usc_interface,
        "_select_all_elements",
        return_value=[MagicMock() for _ in range(3)],
    ) as _, patch.object(
        usc_interface, "_click_and_find_element"
    ), patch.object(
        usc_interface,
        "_filter_webelements",
        return_value=[MagicMock() for _ in range(2)],
    ) as _, patch.object(
        usc_interface, "execute_script"
    ), patch.object(
        usc_interface, "reset_driver"
    ):

        # Define a mock function to apply to each slot
        mock_function = MagicMock(return_value="result")

        result = usc_interface._loop_over_the_days(
            target_days=2, sport="Football", function_to_do=mock_function
        )

        # Check that the slots were filtered and the function was applied to each slot
        assert len(result) == 4  # 2 slots for 2 days
        mock_function.assert_called()


def test_select_day(usc_interface, weekdays):
    """Test selecting a specific day on the USC interface."""
    date = dt.now() + timedelta(days=3)
    date_str = f"{weekdays[date.strftime('%w')]} {date.strftime('%-d-%-m')}"

    with patch.object(
        usc_interface,
        "_select_all_elements",
        return_value=[MagicMock() for _ in range(5)],
    ) as _, patch.object(
        usc_interface, "_filter_webelements", side_effect=[[MagicMock()], []]
    ) as mock_filter_elements, patch.object(
        usc_interface, "execute_script"
    ):

        usc_interface._select_day(date)

        # Verify that the method filtered for the correct date string
        mock_filter_elements.assert_any_call(
            ANY, f'.//*[contains(text(), "{date_str}")]'
        )
        usc_interface.execute_script.assert_called_once()


def test_click_bookable_right_course(usc_interface):
    """Test clicking on the correct course button."""
    sport = "Football"
    date = dt.now()

    with patch.object(
        usc_interface,
        "_select_all_elements",
        return_value=[MagicMock() for _ in range(3)],
    ) as mock_select_elements, patch.object(
        usc_interface, "_filter_webelements", return_value=[MagicMock()]
    ) as mock_filter_webelements, patch.object(
        usc_interface, "execute_script"
    ) as mock_execute_script:

        # Mocking button inside the slot
        mock_button = MagicMock()
        mock_filter_webelements.return_value[0].find_element.return_value = mock_button

        usc_interface._click_bookable_right_course(sport, date)

        mock_select_elements.assert_called_once_with(
            'div[data-test-id="bookable-slot-list"]'
        )
        mock_filter_webelements.assert_called_once_with(
            ANY,
            f"*[contains(., '{sport}') and contains(., '{date.strftime('%H:%M')}')]",
        )
        mock_execute_script.assert_called_once_with("arguments[0].click()", mock_button)


def test_click_sign_on(usc_interface):
    """Test the clicking on the final booking button and closing the modal."""
    with patch.object(
        usc_interface, "_select_element", side_effect=[MagicMock(), MagicMock()]
    ) as mock_select_element, patch.object(
        usc_interface, "execute_script"
    ) as mock_execute_script:

        # Call the function
        usc_interface._click_sign_on()

        # Verify that the correct elements were selected and clicked
        mock_select_element.assert_any_call(
            'button[data-test-id="details-book-button"]'
        )
        mock_select_element.assert_any_call('button[data-test-id="button-close-modal"]')
        mock_execute_script.assert_called_once()


def test_reset_driver(usc_interface):
    """Test resetting the driver to the 'Vandaag' (today) date."""
    with patch.object(
        usc_interface,
        "_select_all_elements",
        return_value=[MagicMock() for _ in range(3)],
    ) as mock_select_all_elements, patch.object(
        usc_interface, "_filter_webelements", side_effect=[[], [MagicMock()]]
    ) as mock_filter_webelements, patch.object(
        usc_interface, "_select_element"
    ) as mock_select_element:

        usc_interface.reset_driver()

        # The function should loop until it finds 'Vandaag'
        mock_select_all_elements.assert_called_with(
            'a[data-test-id-day-selector="day-selector"]'
        )
        mock_filter_webelements.assert_called_with(
            ANY, "//*[contains(text(), 'Vandaag')]"
        )
        mock_select_element.assert_called_with(
            '//i[@class="fa fa-chevron-left"]/..', select_with=By.XPATH
        )


def test_sign_up_for_lesson(usc_interface):
    """Test the entire flow of signing up for a lesson."""
    sport = "Football"
    date = dt.now()

    with patch.object(
        usc_interface, "_filter_for_sport"
    ) as mock_filter_for_sport, patch.object(
        usc_interface, "_select_day"
    ) as mock_select_day, patch.object(
        usc_interface, "_click_bookable_right_course"
    ) as mock_click_bookable_right_course, patch.object(
        usc_interface, "_click_sign_on"
    ) as mock_click_sign_on, patch.object(
        usc_interface, "reset_driver"
    ) as mock_reset_driver:

        usc_interface.sign_up_for_lesson(sport, date)

        # Ensure the flow is executed correctly
        mock_filter_for_sport.assert_called_once_with(sport)
        mock_select_day.assert_called_once_with(date)
        mock_click_bookable_right_course.assert_called_once_with(sport, date)
        mock_click_sign_on.assert_called_once()
        mock_reset_driver.assert_called_once()


def test_sign_up_for_lesson_with_exception(usc_interface):
    """Test signing up for a lesson when an exception occurs (and reset is still called)."""
    sport = "Football"
    date = dt.now()

    with patch.object(
        usc_interface, "_filter_for_sport", side_effect=Exception("Test exception")
    ), patch.object(usc_interface, "reset_driver") as mock_reset_driver:

        with pytest.raises(Exception, match="Test exception"):
            usc_interface.sign_up_for_lesson(sport, date)

        # Ensure reset_driver is still called even after an exception
        mock_reset_driver.assert_called_once()


def test_get_all_lessons(usc_interface):
    """Test retrieving all lessons for a given sport over a specified number of days."""
    sport = "Basketball"
    days_in_future = 7

    with patch.object(
        usc_interface, "_filter_for_sport"
    ) as mock_filter_for_sport, patch.object(
        usc_interface, "_loop_over_the_days", return_value=["lesson1", "lesson2"]
    ) as mock_loop_over_the_days, patch.object(
        usc_interface, "reset_driver"
    ) as mock_reset_driver:

        result = usc_interface.get_all_lessons(sport, days_in_future)

        # Verify the correct calls are made
        mock_filter_for_sport.assert_called_once_with(sport)
        mock_loop_over_the_days.assert_called_once_with(
            days_in_future, sport, usc_interface._extract_info_from_timeslot
        )
        mock_reset_driver.assert_called_once()

        assert result == ["lesson1", "lesson2"]


def test_get_all_lessons_with_exception(usc_interface):
    """Test getting lessons when an exception occurs, ensuring reset_driver is still called."""
    sport = "Basketball"
    days_in_future = 7

    with patch.object(
        usc_interface, "_filter_for_sport", side_effect=Exception("Test exception")
    ), patch.object(usc_interface, "reset_driver") as mock_reset_driver:

        with pytest.raises(Exception, match="Test exception"):
            usc_interface.get_all_lessons(sport, days_in_future)

        # Ensure reset_driver is still called even after an exception
        mock_reset_driver.assert_called_once()
