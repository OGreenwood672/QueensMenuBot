from flask import Flask
from get_menu import MenuScraper
from make_post import PostGenerator
from insta import InstagramAPI
import schedule
import time
import threading

app = Flask(__name__)

# Initialize classes
menu_scraper = MenuScraper('https://www.queens.cam.ac.uk/life-at-queens/catering/cafeteria/cafeteria-menu')
post_generator = PostGenerator()
instagram_api = InstagramAPI()

def post_weekly_menu():
    menus = menu_scraper.get_weekly_menu()
    images = post_generator.generate_weekly_images(menus)
    instagram_api.post_images(images, "Weekly Menu!")

def post_daily_story():
    menu = menu_scraper.get_daily_menu()
    image = post_generator.generate_daily_image(menu)
    instagram_api.post_story(image, "Today's Menu!")


@app.route('/')
def index():
    return "Menu Bot is running!"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
