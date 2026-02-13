import re
import time
from datetime import datetime
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError


class MenuScraper:
    def __init__(self, url, headless=True, timeout_ms=10000):
        self.url = url
        self.headless = headless
        self.timeout_ms = timeout_ms
        self.soup = self.get_soup()

    def get_soup(self):
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=self.headless)
                page = browser.new_page()
                page.goto(self.url, wait_until="networkidle", timeout=self.timeout_ms)
                self._wait_for_captcha_clear(page, max_wait_ms=self.timeout_ms)
                html = page.content()
                browser.close()
                return BeautifulSoup(html, "html.parser")
        except PlaywrightTimeoutError as exc:
            print(f"Timeout loading page: {exc}")
        except Exception as exc:
            print(f"Request failed: {exc}")
        return None

    def _wait_for_captcha_clear(self, page, max_wait_ms=10000, poll_ms=1000):
        deadline = time.monotonic() + (max_wait_ms / 1000)
        while time.monotonic() < deadline:
            if "captcha" not in page.url.lower():
                return
            page.wait_for_timeout(poll_ms)

    @staticmethod
    def clean_text(text):
        text = text.strip()
        text = re.sub(r"\s+", " ", text)
        return text.encode("ascii", "ignore").decode()

    def _parse_day(self, day_container):
        meals = {}
        current_meal = None

        for node in day_container.find_all(["p", "ul"], recursive=True):
            if node.name == "p":
                strong = node.find("strong")
                if strong:
                    meal_name = self.clean_text(strong.get_text())
                    if meal_name:
                        current_meal = meal_name
                        meals.setdefault(current_meal, [])
            elif node.name == "ul" and current_meal:
                items = [self.clean_text(li.get_text()) for li in node.find_all("li")]
                meals[current_meal] = [item for item in items if item]

        return meals

    def get_queens_menu(self):
        if not self.soup:
            return {}

        accordion = self.soup.find("dl", class_="accordion-wrapper")
        if not accordion:
            return {}

        menu = {}
        for day_title in accordion.find_all("dt", class_="accordion-title"):
            day = self.clean_text(day_title.get_text())
            day_container = day_title.find_next_sibling("dd")
            if not day or not day_container:
                continue
            menu[day] = self._parse_day(day_container)

        return menu

    def get_queens_week(self):
        if not self.soup:
            return None

        header = self.soup.find("div", class_="sectionheader-content")
        h2 = header.find("h2") if header else self.soup.find("h2")
        if not h2:
            return None

        text = self.clean_text(h2.get_text())
        match = re.search(r"Week Commencing\s+(.+)", text, re.IGNORECASE)
        if not match:
            return None

        date = match.group(1).strip()
        no_suffix = re.sub(r"(\d+)(st|nd|rd|th)", r"\1", date)
        return datetime.strptime(no_suffix + f" {datetime.now().year}", "%d %B %Y")


if __name__ == "__main__":
    menu_scraper = MenuScraper(
        "https://www.queens.cam.ac.uk/life-at-queens/catering/dining-hall/weekly-menu/",
        headless=True,
    )
    print(menu_scraper.get_queens_menu())
