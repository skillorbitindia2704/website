import os
from PIL import Image, ImageDraw, ImageFont

target_dir = os.path.join("static", "uploads", "ai_lab", "courses", "thumbnails")
os.makedirs(target_dir, exist_ok=True)

WIDTH = 800
HEIGHT = 500

def create_gradient_img(c1, c2, c3):
    img = Image.new("RGBA", (WIDTH, HEIGHT))
    draw = ImageDraw.Draw(img)
    for y in range(HEIGHT):
        t = y / HEIGHT
        # 3-stop gradient
        if t < 0.5:
            factor = t * 2
            r = int(c1[0] * (1 - factor) + c2[0] * factor)
            g = int(c1[1] * (1 - factor) + c2[1] * factor)
            b = int(c1[2] * (1 - factor) + c2[2] * factor)
        else:
            factor = (t - 0.5) * 2
            r = int(c2[0] * (1 - factor) + c3[0] * factor)
            g = int(c2[1] * (1 - factor) + c3[1] * factor)
            b = int(c2[2] * (1 - factor) + c3[2] * factor)
        draw.line([(0, y), (WIDTH, y)], fill=(r, g, b, 255))
    return img

def get_font(size, bold=False):
    font_paths = [
        "C:\\Windows\\Fonts\\segoeuib.ttf" if bold else "C:\\Windows\\Fonts\\segoeui.ttf",
        "C:\\Windows\\Fonts\\arialbd.ttf" if bold else "C:\\Windows\\Fonts\\arial.ttf",
    ]
    for p in font_paths:
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                pass
    return ImageFont.load_default()

def draw_card(draw, x, y, w, h, bg_color, border_color):
    draw.rounded_rectangle([x, y, x + w, y + h], radius=16, fill=bg_color, outline=border_color, width=2)

# 1. AI & Machine Learning
def gen_ai_course():
    img = create_gradient_img((11, 18, 37), (49, 46, 129), (124, 58, 237))
    draw = ImageDraw.Draw(img)
    
    # Grid lines
    for x in range(0, WIDTH, 40):
        draw.line([(x, 0), (x, HEIGHT)], fill=(255, 255, 255, 12), width=1)
    for y in range(0, HEIGHT, 40):
        draw.line([(0, y), (WIDTH, y)], fill=(255, 255, 255, 12), width=1)
        
    # Neural network nodes & connections
    nodes = [
        (150, 150), (150, 250), (150, 350),
        (280, 180), (280, 320),
        (400, 250),
        (520, 180), (520, 320),
        (650, 250)
    ]
    edges = [
        (0, 3), (0, 4), (1, 3), (1, 4), (2, 3), (2, 4),
        (3, 5), (4, 5),
        (5, 6), (5, 7),
        (6, 8), (7, 8)
    ]
    for i1, i2 in edges:
        p1, p2 = nodes[i1], nodes[i2]
        draw.line([p1, p2], fill=(6, 182, 212, 100), width=2)
        
    for x, y in nodes:
        draw.ellipse([x - 14, y - 14, x + 14, y + 14], fill=(79, 70, 229, 200), outline=(6, 182, 212, 255), width=2)
        draw.ellipse([x - 6, y - 6, x + 6, y + 6], fill=(255, 255, 255, 240))

    # Glass container overlay for title
    overlay = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    ov_draw = ImageDraw.Draw(overlay)
    ov_draw.rounded_rectangle([60, 340, 740, 450], radius=16, fill=(15, 23, 42, 210), outline=(255, 255, 255, 45), width=1)
    
    # Pill
    ov_draw.rounded_rectangle([80, 358, 260, 388], radius=8, fill=(79, 70, 229, 230))
    font_sm = get_font(14, bold=True)
    ov_draw.text((95, 364), "AI & MACHINE LEARNING", fill=(255, 255, 255, 255), font=font_sm)
    
    # Title
    font_lg = get_font(24, bold=True)
    ov_draw.text((80, 400), "Artificial Intelligence & Machine Learning", fill=(255, 255, 255, 255), font=font_lg)
    
    font_desc = get_font(14)
    ov_draw.text((530, 407), "Neural Nets • Vision • NLP", fill=(6, 182, 212, 240), font=font_desc)

    img = Image.alpha_composite(img, overlay)
    out_path = os.path.join(target_dir, "bcca9e3ec6ed4ad2bde4a692228c6b0c_ChatGPT_Image_Sep_7_2026_12_26_22_PM.png")
    img.save(out_path, "PNG")
    print(f"Generated {out_path}")

# 2. Full Stack Web Development
def gen_web_course():
    img = create_gradient_img((15, 23, 42), (3, 105, 161), (13, 148, 136))
    draw = ImageDraw.Draw(img)
    
    # Background code / matrix dots
    for x in range(0, WIDTH, 35):
        for y in range(0, HEIGHT, 35):
            draw.ellipse([x - 1, y - 1, x + 1, y + 1], fill=(255, 255, 255, 25))
            
    # Mock browser / editor window
    win_x, win_y, win_w, win_h = 160, 50, 480, 250
    draw.rounded_rectangle([win_x, win_y, win_x + win_w, win_y + win_h], radius=12, fill=(15, 23, 42, 230), outline=(56, 189, 248, 80), width=2)
    # Window header
    draw.rounded_rectangle([win_x, win_y, win_x + win_w, win_y + 36], radius=12, fill=(30, 41, 59, 240))
    # Window dots
    draw.ellipse([win_x + 14, win_y + 12, win_x + 24, win_y + 22], fill=(239, 68, 68, 220))
    draw.ellipse([win_x + 30, win_y + 12, win_x + 40, win_y + 22], fill=(245, 158, 11, 220))
    draw.ellipse([win_x + 46, win_y + 12, win_x + 56, win_y + 22], fill=(34, 197, 94, 220))
    
    # Code snippet graphics
    font_code = get_font(16, bold=True)
    draw.text((win_x + 30, win_y + 55), "const app = express();", fill=(147, 197, 253, 230), font=font_code)
    draw.text((win_x + 30, win_y + 85), "const [state, setState] = useState();", fill=(52, 211, 153, 230), font=font_code)
    draw.text((win_x + 30, win_y + 115), "export default function FullStackApp() {", fill=(244, 114, 182, 230), font=font_code)
    draw.text((win_x + 50, win_y + 145), "return <DatabaseIntegration live={true} />;", fill=(251, 191, 36, 230), font=font_code)
    draw.text((win_x + 30, win_y + 175), "}", fill=(244, 114, 182, 230), font=font_code)
    
    # Tag chips on the window
    chips = ["React", "Node.js", "Python", "PostgreSQL"]
    cx = win_x + 30
    for chip in chips:
        c_len = len(chip) * 9 + 20
        draw.rounded_rectangle([cx, win_y + 210, cx + c_len, win_y + 234], radius=6, fill=(56, 189, 248, 40), outline=(56, 189, 248, 120), width=1)
        draw.text((cx + 10, win_y + 214), chip, fill=(224, 242, 254, 240), font=get_font(12, bold=True))
        cx += c_len + 12

    # Glass container overlay for title
    overlay = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    ov_draw = ImageDraw.Draw(overlay)
    ov_draw.rounded_rectangle([60, 340, 740, 450], radius=16, fill=(15, 23, 42, 210), outline=(255, 255, 255, 45), width=1)
    
    # Pill
    ov_draw.rounded_rectangle([80, 358, 280, 388], radius=8, fill=(2, 132, 199, 230))
    font_sm = get_font(14, bold=True)
    ov_draw.text((95, 364), "WEB DEVELOPMENT", fill=(255, 255, 255, 255), font=font_sm)
    
    # Title
    font_lg = get_font(24, bold=True)
    ov_draw.text((80, 400), "Full Stack Web Development", fill=(255, 255, 255, 255), font=font_lg)
    
    font_desc = get_font(14)
    ov_draw.text((520, 407), "Frontend • Backend • Cloud", fill=(56, 189, 248, 240), font=font_desc)

    img = Image.alpha_composite(img, overlay)
    out_path = os.path.join(target_dir, "2fe6524684204db3977d162d97ca70e9_ChatGPT_Image_Sep_7_2026_12_47_07_PM.png")
    img.save(out_path, "PNG")
    print(f"Generated {out_path}")

# 3. Robotics & IoT Engineering
def gen_robotics_course():
    img = create_gradient_img((15, 23, 42), (22, 101, 52), (180, 83, 9))
    draw = ImageDraw.Draw(img)
    
    # Circuit tracks
    tracks = [
        [(80, 100), (220, 100), (280, 160), (450, 160)],
        [(120, 220), (240, 220), (320, 140), (520, 140)],
        [(300, 300), (420, 300), (480, 240), (680, 240)],
        [(400, 80), (550, 80), (620, 150), (720, 150)],
    ]
    for track in tracks:
        draw.line(track, fill=(245, 158, 11, 140), width=3)
        for pt in track:
            draw.ellipse([pt[0] - 5, pt[1] - 5, pt[0] + 5, pt[1] + 5], fill=(251, 191, 36, 220))
            
    # Microcontroller chip graphic
    chip_x, chip_y, chip_w, chip_h = 320, 90, 160, 160
    draw.rectangle([chip_x, chip_y, chip_x + chip_w, chip_y + chip_h], fill=(30, 41, 59, 240), outline=(245, 158, 11, 220), width=2)
    # Chip pins
    for py in range(chip_y + 15, chip_y + chip_h - 10, 20):
        draw.rectangle([chip_x - 16, py, chip_x, py + 8], fill=(203, 213, 225, 230))
        draw.rectangle([chip_x + chip_w, py, chip_x + chip_w + 16, py + 8], fill=(203, 213, 225, 230))
    for px in range(chip_x + 15, chip_x + chip_w - 10, 20):
        draw.rectangle([px, chip_y - 16, px + 8, chip_y], fill=(203, 213, 225, 230))
        draw.rectangle([px, chip_y + chip_h, px + 8, chip_y + chip_h + 16], fill=(203, 213, 225, 230))
        
    font_chip = get_font(18, bold=True)
    draw.text((chip_x + 36, chip_y + 45), "ESP32", fill=(255, 255, 255, 240), font=font_chip)
    draw.text((chip_x + 28, chip_y + 75), "ROBOTICS", fill=(245, 158, 11, 230), font=get_font(14, bold=True))
    draw.text((chip_x + 48, chip_y + 105), "IoT Core", fill=(148, 163, 184, 220), font=get_font(12))

    # Glass container overlay for title
    overlay = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    ov_draw = ImageDraw.Draw(overlay)
    ov_draw.rounded_rectangle([60, 340, 740, 450], radius=16, fill=(15, 23, 42, 210), outline=(255, 255, 255, 45), width=1)
    
    # Pill
    ov_draw.rounded_rectangle([80, 358, 290, 388], radius=8, fill=(217, 119, 6, 230))
    font_sm = get_font(14, bold=True)
    ov_draw.text((95, 364), "ROBOTICS & HARDWARE", fill=(255, 255, 255, 255), font=font_sm)
    
    # Title
    font_lg = get_font(24, bold=True)
    ov_draw.text((80, 400), "Robotics & IoT Engineering", fill=(255, 255, 255, 255), font=font_lg)
    
    font_desc = get_font(14)
    ov_draw.text((510, 407), "Arduino • ESP32 • ROS • Sensors", fill=(251, 191, 36, 240), font=font_desc)

    img = Image.alpha_composite(img, overlay)
    out_path = os.path.join(target_dir, "88bfbe42314b48c4b61082654028fdc6_ChatGPT_Image_Sep_7_2026_12_53_48_PM.png")
    img.save(out_path, "PNG")
    print(f"Generated {out_path}")

gen_ai_course()
gen_web_course()
gen_robotics_course()
