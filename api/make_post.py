import os
import random
from uuid import uuid1

from PIL import Image, ImageDraw, ImageFont

DEFAULT_PUBLIC_BASE_URL = "https://tsg36.soc.srcf.net"


class PostGenerator:
    def __init__(self, base_url=None):
        current_dir = os.path.dirname(os.path.abspath(__file__))

        self.font_path = os.path.join(current_dir, "static", "assets", "fonts", "inriasans", "InriaSans-Regular.ttf")
        self.banners_folder = os.path.join(current_dir, "static", "assets", "Images", "banners")
        self.crest_img = os.path.join(current_dir, "static", "assets", "Images", "crest.png")
        self.save_folder = os.path.join(current_dir, "static", "QueensMenus")

        configured_base_url = base_url
        if configured_base_url is None:
            configured_base_url = os.getenv("PUBLIC_BASE_URL") or os.getenv("HOST") or DEFAULT_PUBLIC_BASE_URL
        self.base_url = configured_base_url.rstrip("/")

        os.makedirs(self.save_folder, exist_ok=True)

    def _text_size(self, draw, text, font):
        left, top, right, bottom = draw.textbbox((0, 0), text, font=font)
        return right - left, bottom - top

    def _load_fonts(self, sizes):
        return {name: ImageFont.truetype(self.font_path, size) for name, size in sizes.items()}

    def _pick_banner(self, image_size, banner_height):
        banners = [f for f in os.listdir(self.banners_folder) if os.path.isfile(os.path.join(self.banners_folder, f))]
        banner = Image.open(os.path.join(self.banners_folder, random.choice(banners))).convert("RGBA")
        banner = banner.resize((image_size[0], int(image_size[0] * banner.height / banner.width)))
        top = (banner.height - banner_height) // 2
        return banner.crop((0, top, image_size[0], top + banner_height))

    def _place_crest(self, img, image_size, banner_height, crest_divisor, y_pos):
        crest = Image.open(self.crest_img)
        crest_width, crest_height = crest.size
        crest_scale = min(image_size[0] / crest_width, image_size[1] / crest_height / crest_divisor)
        crest = crest.resize((int(crest_width * crest_scale), int(crest_height * crest_scale)))
        crest_x = image_size[0] - crest.width - 20
        img.paste(crest, (crest_x, y_pos), crest)
        return crest.height

    def _draw_header_box(self, img, draw, title_text, date_text, banner_height, fonts, date_gap=0):
        title_width, title_height = self._text_size(draw, title_text, fonts["header"])
        date_width, date_height = self._text_size(draw, date_text, fonts["date"])

        padding = 20
        box_w = max(title_width, date_width) + 2 * padding
        box_h = title_height + date_height + (2 * padding) + date_gap
        x0 = (img.width - box_w) // 2
        y0 = (banner_height - box_h) // 2

        mask = Image.new("L", (box_w, box_h), 0)
        ImageDraw.Draw(mask).rounded_rectangle([0, 0, box_w, box_h], radius=20, fill=255)
        rounded = Image.new("RGBA", (box_w, box_h), "white")
        rounded.putalpha(mask)
        img.paste(rounded, (x0, y0), rounded)

        draw.text((x0 + padding, y0 + padding), title_text, fill="black", font=fonts["header"])
        date_x = x0 + (box_w - date_width) // 2
        date_y = y0 + padding + title_height + date_gap
        draw.text((date_x, date_y), date_text, fill="black", font=fonts["date"])

        return title_height

    def _iter_menu_lines(self, menu_dict):
        for header, items in menu_dict.items():
            yield f"{header}:", True
            for item in items:
                yield f"• {item}", False

    def _wrap_text(self, draw, text, font, max_width):
        if not text.strip():
            return [""]

        words = text.split()
        lines, line = [], ""
        for word in words:
            test = f"{line}{word} "
            if self._text_size(draw, test, font)[0] <= max_width:
                line = test
            else:
                lines.append(line)
                line = f"{word} "
        lines.append(line)
        return lines

    def _draw_wrapped_text(self, draw, text, x, y, font, max_width, spacing=5):
        for line in self._wrap_text(draw, text, font, max_width):
            draw.text((x, y), line, fill="black", font=font)
            y += self._text_size(draw, line or " ", font)[1] + spacing
        return y

    def _draw_menu_block(self, draw, menu_dict, start_y, fonts, image_width):
        margin = 50
        max_width = image_width - (2 * margin)
        y = start_y

        for text, is_header in self._iter_menu_lines(menu_dict):
            if is_header:
                draw.line([(margin, y + 10), (margin + max_width, y + 10)], fill="black", width=2)
                y += 20
                y = self._draw_wrapped_text(draw, text, margin, y, fonts["section"], max_width)
            else:
                y = self._draw_wrapped_text(draw, text, margin, y, fonts["body"], max_width)
            y += 10

    def _save(self, img):
        name = f"{uuid1()}.jpg"
        path = os.path.join(self.save_folder, name)
        img.save(path, "JPEG")
        return self._public_url(name, path)

    def generate_image(self, day, date_text, menu_dict):
        image_size = (1080, 1080)
        banner_height = int(image_size[1] / 4.3)
        img = Image.new("RGB", image_size, color="white")
        draw = ImageDraw.Draw(img)

        banner = self._pick_banner(image_size, banner_height)
        img.paste(banner, (0, 0), banner)
        crest_h = self._place_crest(img, image_size, banner_height, crest_divisor=5, y_pos=20)

        fonts = self._load_fonts({"header": 60, "date": 30, "section": 40, "body": 24})
        title_h = self._draw_header_box(img, draw, day, date_text, banner_height, fonts)

        start_y = max(crest_h + 20, title_h + 30)
        self._draw_menu_block(draw, menu_dict, start_y, fonts, image_size[0])

        footer = "Bon Appétit!"
        footer_w, _ = self._text_size(draw, footer, fonts["body"])
        draw.text(((image_size[0] - footer_w) / 2, image_size[1] - 50), footer, fill="black", font=fonts["body"])
        return self._save(img)

    def generate_story(self, day, date_text, menu_dict):
        image_size = (1080, 1920)
        banner_height = int(image_size[1] / 3)
        img = Image.new("RGB", image_size, color="white")
        draw = ImageDraw.Draw(img)

        banner = self._pick_banner(image_size, banner_height)
        img.paste(banner, (0, 0), banner)
        self._place_crest(img, image_size, banner_height, crest_divisor=6, y_pos=int(banner_height * 0.2))

        fonts = self._load_fonts({"header": 70, "date": 30, "section": 50, "body": 35})
        self._draw_header_box(img, draw, day, date_text, banner_height, fonts, date_gap=10)

        self._draw_menu_block(draw, menu_dict, banner_height, fonts, image_size[0])

        footer = "Bon Appétit!"
        footer_w, _ = self._text_size(draw, footer, fonts["body"])
        draw.text(((image_size[0] - footer_w) / 2, image_size[1] - 100), footer, fill="black", font=fonts["body"])
        return self._save(img)

    def _public_url(self, menu_name, file_path):
        if self.base_url:
            return f"{self.base_url}/QueensMenus/{menu_name}"
        return file_path


if __name__ == "__main__":
    pg = PostGenerator()
    pg.generate_story("Monday", "16th September", {
        "Lunch": ["beans", "bread"],
        "Dinner": ["Something tasty"]
    })