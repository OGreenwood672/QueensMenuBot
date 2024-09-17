from PIL import Image, ImageDraw, ImageFont

class PostGenerator:
    def __init__(self):
        self.font_path = "path_to_font.ttf"  # Add the path to your font file
        self.image_size = (1080, 1080)

    def generate_image(self, menu_text, day):
        # Create an empty image with white background
        img = Image.new('RGB', self.image_size, color='white')
        draw = ImageDraw.Draw(img)
        
        # Load font
        font = ImageFont.truetype(self.font_path, 40)

        # Add text to the image
        text = f"{day}'s Menu:\n{menu_text}"
        draw.multiline_text((100, 100), text, fill="black", font=font)

        return img

    def generate_weekly_images(self, weekly_menu):
        days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        images = []
        
        for i, menu in enumerate(weekly_menu):
            img = self.generate_image(menu, days[i])
            images.append(img)
        
        return images

    def generate_daily_image(self, daily_menu):
        today = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'][time.localtime().tm_wday]
        return self.generate_image(daily_menu, today)
