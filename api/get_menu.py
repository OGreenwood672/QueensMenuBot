import re
import requests
from bs4 import BeautifulSoup
from datetime import datetime

class MenuScraper:
    def __init__(self, url):
        self.url = url
        self.soup = self.get_soup()

    def get_soup(self):
        response = requests.get(self.url)
        if response.status_code == 200:
            return BeautifulSoup(response.content, 'html.parser')
        return None
    
    @staticmethod
    def clean_text(text):
        text = text.strip()
        text = re.sub(r'\s+', ' ', text)
        text = text.encode('ascii', 'ignore').decode()
        
        return text

    def get_queens_menu(self):

        content = self.soup.find('div', class_='content')
        menu = {}
        curr_meal = []

        for td in content.find_all('td'):
            td_text = MenuScraper.clean_text(td.text)
            if td_text:
                curr_meal.append(td_text)
            else:
                is_one_line = len(curr_meal[0].split()) > 1
                if is_one_line:
                    day = curr_meal[0].split()[0]
                    meal = curr_meal[0].split()[1]
                    if not day in menu.keys():
                        menu[day] = {}
                    menu[day][meal] = curr_meal[1:]
                else:
                    if not curr_meal[0] in menu.keys():
                        menu[curr_meal[0]] = {}
                    menu[curr_meal[0]][curr_meal[1]] = curr_meal[2:]
                curr_meal = []

        is_one_line = len(curr_meal[0].split()) > 1
        if is_one_line:
            day = curr_meal[0].split()[0]
            meal = curr_meal[0].split()[1]
            if not day in menu.keys():
                menu[day] = {}
            menu[day][meal] = curr_meal[1:]
        else:
            if not curr_meal[0] in menu.keys():
                menu[curr_meal[0]] = {}
            menu[curr_meal[0]][curr_meal[1]] = curr_meal[2:]

        return menu
    
    def get_queens_week(self):
        content = self.soup.find('div', class_='content')
        date_text = content.find('p').text
        date = date_text.strip()[16:]
        no_suffix = re.sub(r'(\d+)(st|nd|rd|th)', r'\1', date)
        date_obj = datetime.strptime(no_suffix + f" {datetime.now().year}", "%d %B %Y")
        return date_obj


if __name__ == "__main__":
    menu_scraper = MenuScraper("https://www.queens.cam.ac.uk/life-at-queens/catering/cafeteria/cafeteria-menu")
    print(menu_scraper.get_queens_week())