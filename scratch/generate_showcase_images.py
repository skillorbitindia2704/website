import os
import math
from PIL import Image, ImageDraw, ImageFont

output_dir = os.path.join(os.path.dirname(__file__), "..", "static", "uploads", "ai_lab", "courses", "showcase")
os.makedirs(output_dir, exist_ok=True)

projects = [
    {
        "filename": "afc8aa4003234b12867f8fcad4639702_ChatGPT_Image_Oct_1_2026_09_36_41_PM.png",
        "title": "Smart Classroom System",
        "subtitle": "Automated Environment & Energy Control",
        "badge": "IoT & SENSORS",
        "badge_color": (56, 189, 248),
        "accent": (99, 102, 241),
        "grad_stops": [(8, 14, 30), (15, 23, 42), (30, 58, 138), (79, 70, 229)]
    },
    {
        "filename": "9afb419868974182847bef60d72060af_ChatGPT_Image_Oct_1_2026_09_41_44_PM.png",
        "title": "Smart Waste Management",
        "subtitle": "Real-time Ultrasonic Fill Monitoring",
        "badge": "CLEANTECH · ARDUINO",
        "badge_color": (52, 211, 153),
        "accent": (16, 185, 129),
        "grad_stops": [(6, 26, 24), (13, 43, 38), (5, 150, 105), (14, 165, 233)]
    },
    {
        "filename": "b227d04081b24f1a8013a8355886bdde_ChatGPT_Image_Oct_1_2026_09_49_21_PM.png",
        "title": "Obstacle Avoiding Robot",
        "subtitle": "Autonomous Ultrasonic Navigation",
        "badge": "MOBILE ROBOTICS",
        "badge_color": (251, 146, 60),
        "accent": (249, 115, 22),
        "grad_stops": [(15, 23, 42), (30, 27, 75), (124, 58, 237), (234, 88, 12)]
    },
    {
        "filename": "a2ec07518edf40b7946737861813ee58_ChatGPT_Image_Oct_1_2026_09_52_04_PM.png",
        "title": "Weather Monitoring System",
        "subtitle": "DHT11 Climate Telemetry & Cloud IoT",
        "badge": "ENVIRONMENTAL IOT",
        "badge_color": (56, 189, 248),
        "accent": (2, 132, 199),
        "grad_stops": [(8, 20, 36), (15, 35, 65), (2, 132, 199), (56, 189, 248)]
    },
    {
        "filename": "53b657aa5fa8448fbd34aa4cd57e581f_ChatGPT_Image_Oct_1_2026_09_54_34_PM.png",
        "title": "Bluetooth Controlled Robot",
        "subtitle": "Wireless Smartphone Teleoperation",
        "badge": "ROBOTICS & EMBEDDED",
        "badge_color": (244, 114, 182),
        "accent": (217, 70, 239),
        "grad_stops": [(24, 12, 48), (48, 20, 85), (147, 51, 234), (236, 72, 153)]
    },
    {
        "filename": "d8f8def3189e47b397febe8ddfb689d3_ChatGPT_Image_Oct_1_2026_09_56_51_PM.png",
        "title": "Smart Dustbin Prototype",
        "subtitle": "Touchless Proximity Lid Actuation",
        "badge": "AUTOMATION PROTOTYPE",
        "badge_color": (45, 212, 191),
        "accent": (20, 184, 166),
        "grad_stops": [(10, 25, 30), (20, 48, 55), (13, 148, 136), (56, 189, 248)]
    }
]

W, H = 800, 500

for p in projects:
    im = Image.new("RGBA", (W, H))
    draw = ImageDraw.Draw(im)
    stops = p["grad_stops"]
    
    # Smooth diagonal gradient
    for y in range(H):
        t = y / float(H)
        if t < 0.33:
            f = t / 0.33
            c_a, c_b = stops[0], stops[1]
        elif t < 0.66:
            f = (t - 0.33) / 0.33
            c_a, c_b = stops[1], stops[2]
        else:
            f = (t - 0.66) / 0.34
            c_a, c_b = stops[2], stops[3]
            
        r = int(c_a[0] * (1 - f) + c_b[0] * f)
        g = int(c_a[1] * (1 - f) + c_b[1] * f)
        b = int(c_a[2] * (1 - f) + c_b[2] * f)
        draw.line([(0, y), (W, y)], fill=(r, g, b, 255))
        
    # Ambient radial glow in center
    cx, cy = W // 2, 185
    glow_col = p["accent"]
    for rad in range(160, 40, -10):
        alpha = int(45 * (1 - rad / 160.0))
        draw.ellipse([cx - rad, cy - rad, cx + rad, cy + rad], fill=(glow_col[0], glow_col[1], glow_col[2], alpha))

    # High-tech grid
    for x in range(0, W, 40):
        draw.line([(x, 0), (x, H)], fill=(255, 255, 255, 14), width=1)
    for y in range(0, H, 40):
        draw.line([(0, y), (W, y)], fill=(255, 255, 255, 14), width=1)

    # Concentric orbital tech rings
    draw.ellipse([cx - 120, cy - 120, cx + 120, cy + 120], outline=(255, 255, 255, 45), width=2)
    draw.ellipse([cx - 85, cy - 85, cx + 85, cy + 85], outline=(255, 255, 255, 75), width=2)
    
    # Central cyber emblem shield
    em_size = 56
    draw.rounded_rectangle([cx - em_size, cy - em_size, cx + em_size, cy + em_size], radius=18,
                           fill=(15, 23, 42, 210), outline=(255, 255, 255, 140), width=2)

    # Microcontroller chip motif inside emblem
    core_w = 28
    draw.rounded_rectangle([cx - core_w, cy - core_w, cx + core_w, cy + core_w], radius=8,
                           fill=(glow_col[0], glow_col[1], glow_col[2], 180), outline=(255, 255, 255, 220), width=2)
    # Inner dot
    draw.ellipse([cx - 6, cy - 6, cx + 6, cy + 6], fill=(255, 255, 255, 255))
    
    # Circuit traces connecting out from core
    for ang in range(0, 360, 45):
        rad_ang = math.radians(ang)
        x1 = cx + math.cos(rad_ang) * (em_size + 4)
        y1 = cy + math.sin(rad_ang) * (em_size + 4)
        x2 = cx + math.cos(rad_ang) * (em_size + 30)
        y2 = cy + math.sin(rad_ang) * (em_size + 30)
        draw.line([(x1, y1), (x2, y2)], fill=(255, 255, 255, 110), width=2)
        draw.ellipse([x2 - 4, y2 - 4, x2 + 4, y2 + 4], fill=p["badge_color"] + (220,))

    # Top Badge: Tag pill
    badge_text = p["badge"]
    bw, bh = 210, 34
    bx0, by0 = (W - bw) // 2, 28
    draw.rounded_rectangle([bx0, by0, bx0 + bw, by0 + bh], radius=17,
                           fill=(11, 18, 37, 220), outline=p["badge_color"] + (180,), width=2)
    # Status green dot inside badge
    draw.ellipse([bx0 + 16, by0 + 12, bx0 + 26, by0 + 22], fill=(16, 185, 129, 255))

    # Bottom Glass / Dark Info Banner
    banner_h = 135
    draw.rectangle([0, H - banner_h, W, H], fill=(11, 18, 37, 235))
    draw.line([(0, H - banner_h), (W, H - banner_h)], fill=(255, 255, 255, 35), width=1)
    
    # Accent strip above banner
    draw.line([(0, H - banner_h), (W, H - banner_h)], fill=p["badge_color"] + (140,), width=2)

    # Fonts
    try:
        font_badge = ImageFont.truetype("arialbd.ttf", 12)
        font_title = ImageFont.truetype("arialbd.ttf", 25)
        font_sub = ImageFont.truetype("arial.ttf", 15)
        font_watermark = ImageFont.truetype("arialbd.ttf", 11)
    except Exception:
        font_badge = font_title = font_sub = font_watermark = ImageFont.load_default()

    # Draw Badge Text
    draw.text((bx0 + 36, by0 + 8), badge_text, fill=p["badge_color"] + (255,), font=font_badge)

    # Draw Title & Subtitle in banner
    draw.text((W // 2, H - 95), p["title"], fill=(255, 255, 255, 255), font=font_title, anchor="mm")
    draw.text((W // 2, H - 60), p["subtitle"], fill=(203, 213, 225, 230), font=font_sub, anchor="mm")
    
    # Watermark tag
    draw.text((W // 2, H - 26), "SKILL ORBIT INDIA · STUDENT INNOVATION LAB", fill=(148, 163, 184, 180), font=font_watermark, anchor="mm")

    target_path = os.path.join(output_dir, p["filename"])
    im.convert("RGB").save(target_path, "PNG", quality=95)
    print("Generated:", target_path)

print("All 6 showcase project images generated with high aesthetics!")
