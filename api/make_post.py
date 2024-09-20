import random
import os
from PIL import Image, ImageDraw, ImageFont
from .get_emoji import get_top_emoji
import emoji

class PostGenerator:
    def __init__(self):
        current_dir = os.path.dirname(os.path.abspath(__file__))

        self.font_path = os.path.join(current_dir, "static", "assets", "fonts", "inriasans", "InriaSans-Regular.ttf")
        self.emoji_font_path = os.path.join(current_dir, "static", "assets", "fonts", "notocolour", "NotoEmoji-VariableFont_wght.ttf")
        self.banners_folder = os.path.join(current_dir, "static", "assets", "Images", "banners")
        self.crest_img = os.path.join(current_dir, "static", "assets", "Images", "crest.png")
        self.save_folder = os.path.join(current_dir, "static", "QueensMenus")
        self.image_size = (1080, 1080)

    def generate_image(self, day, menu_dict):
        # Create an image with a white background
        img = Image.new('RGB', self.image_size, color='white')
        draw = ImageDraw.Draw(img)
        
        banners = [f for f in os.listdir(self.banners_folder) if os.path.isfile(os.path.join(self.banners_folder, f))]
        selected_banner = random.choice(banners)
        banner_img = Image.open(os.path.join(self.banners_folder, selected_banner))
        banner_img = banner_img.convert('RGBA')  # Ensure it's in RGBA mode
        
        # Stretch the banner image to full width
        banner_img = banner_img.resize((self.image_size[0], int(self.image_size[0] * banner_img.height / banner_img.width)))
        
        # Crop the center of the banner image
        banner_height = int(self.image_size[1] / 4.3)  # Top section height (adjust if necessary)
        top = (banner_img.height - banner_height) // 2
        bottom = top + banner_height
        banner_img = banner_img.crop((0, top, self.image_size[0], bottom))
        
        # Paste the banner image at the top
        img.paste(banner_img, (0, 0), banner_img)
        
        # Load and place the crest image
        crest_img = Image.open(self.crest_img)
        crest_width, crest_height = crest_img.size
        crest_scale = min(self.image_size[0] / crest_width, self.image_size[1] / crest_height / 5)  # Scale to fit within top fifth of the image
        crest_img = crest_img.resize((int(crest_width * crest_scale), int(crest_height * crest_scale)))
        crest_x = self.image_size[0] - crest_img.width - 20  # 20 pixels from the right edge
        img.paste(crest_img, (crest_x, 20), crest_img)  # Place crest in the top right corner

        # Load fonts
        font_header = ImageFont.truetype(self.font_path, 60)  # Larger font for the header
        font_header_larger = ImageFont.truetype(self.font_path, 40)  # Larger font for menu headers
        font_body = ImageFont.truetype(self.font_path, 24)    # Smaller font for body text
        font_emoji = ImageFont.truetype(self.emoji_font_path, 24)
        
        # Draw the title text with a white background and curved corners
        title_text = day
        text_width, text_height = draw.textsize(title_text, font=font_header)
        
        # Rounded rectangle parameters
        padding = 20
        rounded_rect_width = text_width + 2 * padding
        rounded_rect_height = text_height + 2 * padding
        rect_x0 = (self.image_size[0] - rounded_rect_width) // 2
        rect_y0 = (banner_height - rounded_rect_height) // 2
        rect_x1 = rect_x0 + rounded_rect_width
        rect_y1 = rect_y0 + rounded_rect_height
        
        # Create a mask for rounded corners
        rounded_mask = Image.new('L', (rounded_rect_width, rounded_rect_height), 0)
        mask_draw = ImageDraw.Draw(rounded_mask)
        mask_draw.rounded_rectangle([0, 0, rounded_rect_width, rounded_rect_height], radius=20, fill=255)
        rounded_rect_img = Image.new('RGBA', (rounded_rect_width, rounded_rect_height), 'white')
        rounded_rect_img.putalpha(rounded_mask)
        
        # Paste the rounded rectangle background
        img.paste(rounded_rect_img, (rect_x0, rect_y0), rounded_rect_img)
        
        # Draw the title text on top
        draw.text((rect_x0 + padding, rect_y0 + padding), title_text, fill="black", font=font_header)
        
        # Prepare and draw the menu text with proper spacing
        menu_text = ""
        for header, items in menu_dict.items():
            menu_text += f"\n{header}:\n"
            for item in items:
                item_emoji = get_top_emoji(item)
                menu_text += " • " + (item_emoji if item_emoji else '\t') + item + "\n"
        
        margin = 50
        offset = max(crest_img.height + 20, text_height + 30)  # Starting offset below the crest or title text
        max_text_width = self.image_size[0] - 2 * margin

        # Function to draw text with wrapping
        def draw_wrapped_text(draw, text, position, font, max_width):
            lines = []
            words = text.split()
            line = ""
            for word in words:
                test_line = line + (word + " ")
                if draw.textsize(test_line, font=font)[0] <= max_width:
                    line = test_line
                else:
                    lines.append(line)
                    line = word + " "
            lines.append(line)
            y = position[1]
            for line in lines:
                # Split line into characters
                chars = list(line)
                x = position[0]
                for char in chars:
                    if emoji.is_emoji(char):
                        draw.text((x, y), char, fill="black", font=font_emoji)
                        x += draw.textsize(char, font=font_emoji)[0]
                    else:
                        draw.text((x, y), char, fill="black", font=font)
                        x += draw.textsize(char, font=font)[0]
                y += font.getsize(line)[1] + 5
            return y

        for line in menu_text.split('\n'):
            if ':' in line:  # Only add a decorative line under headers
                # Draw decorative line
                line_width = max_text_width
                draw.line([(margin, offset + 10), (margin + line_width, offset + 10)], fill="black", width=2)
                offset += 20  # Space after the decorative line
                # Draw menu header in larger font
                offset = draw_wrapped_text(draw, line, (margin, offset), font_header_larger, max_text_width)
            else:
                # Draw body text
                offset = draw_wrapped_text(draw, line, (margin, offset), font_body, max_text_width)
            offset += 10  # Space after each line

        # Add a footer with a fun message or college motto
        footer_text = "Bon Appétit!"# from Queens’ College!"
        footer_width, footer_height = draw.textsize(footer_text, font=font_body)
        draw.text(((self.image_size[0] - footer_width) / 2, self.image_size[1] - 50), footer_text, fill="black", font=font_body)
        
        # Save the image with the filename as {day}_menu.png
        menu_name = f"{day}_menu.png"
        file_path = os.path.join(self.save_folder, menu_name)
        img.save(file_path)

        return menu_name

