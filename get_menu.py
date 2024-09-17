import requests
from bs4 import BeautifulSoup

class MenuScraper:
    def __init__(self, url):
        self.url = url

    def get_html(self):
        response = requests.get(self.url)
        return response.text

    def get_weekly_menu(self):
        html = self.get_html()
        soup = BeautifulSoup(html, 'html.parser')
        
        # Assuming there's a div with class 'menu-item' for each day's menu
        weekly_menu = []
        for day in soup.find_all('div', class_='menu-item'):
            day_menu = day.get_text(strip=True)
            weekly_menu.append(day_menu)
        
        return weekly_menu

    def get_daily_menu(self):
        weekly_menu = self.get_weekly_menu()
        today_idx = time.localtime().tm_wday  # Monday is 0, Sunday is 6
        return weekly_menu[today_idx]
