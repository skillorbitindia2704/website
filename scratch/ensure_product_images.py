import os
from PIL import Image, ImageDraw, ImageFont

uploads_dir = os.path.join(os.getcwd(), "static", "uploads", "products")
os.makedirs(uploads_dir, exist_ok=True)

files = [
    ("a610a1b75f264794ab71f6a43599d20f_ChatGPT_Image_Sep_7_2026_12_53_48_PM.webp", "Arduino UNO R3", "#00878F", "ATmega328P Microcontroller"),
    ("e3047cb121d64f81b7d58589e16ce1a4_ChatGPT_Image_Sep_17_2026_12_53_35_PM.webp", "ESP32 DevKit", "#E7352C", "Wi-Fi & Bluetooth Dual Core"),
    ("d51026a1a4c94592ba087cf020223c69_ChatGPT_Image_Sep_17_2026_12_23_20_PM.webp", "Arduino Nano", "#00878F", "Compact Microcontroller Board"),
    ("b88685f4badc428f9d048db1a4eb64bb_ChatGPT_Image_Sep_9_2026_11_11_25_AM.webp", "Arduino Uno Rev3", "#00979D", "Robotics & IoT Starter Board"),
]

for filename, title, accent, subtitle in files:
    filepath = os.path.join(uploads_dir, filename)
    if os.path.exists(filepath):
        continue
    img = Image.new("RGB", (600, 450), color="#0F172A")
    draw = ImageDraw.Draw(img)

    # Draw PCB grid
    for x in range(0, 600, 30):
        draw.line([(x, 0), (x, 450)], fill="#1E293B", width=1)
    for y in range(0, 450, 30):
        draw.line([(y, 0), (y, 450)], fill="#1E293B", width=1)

    # Draw PCB Board
    draw.rounded_rectangle([60, 50, 540, 400], radius=16, fill="#132338", outline=accent, width=3)

    # Header pin connectors
    for y in range(80, 370, 22):
        draw.rectangle([50, y, 62, y + 10], fill="#F59E0B")
        draw.rectangle([538, y, 550, y + 10], fill="#F59E0B")

    # Central Microchip
    draw.rounded_rectangle([200, 140, 400, 290], radius=10, fill="#1E293B", outline="#475569", width=2)
    draw.rounded_rectangle([230, 160, 370, 270], radius=8, fill="#0F172A", outline=accent, width=2)

    # Chip pins
    for x in range(240, 360, 20):
        draw.rectangle([x, 130, x + 8, 140], fill="#CBD5E1")
        draw.rectangle([x, 290, x + 8, 300], fill="#CBD5E1")
    for y in range(170, 260, 20):
        draw.rectangle([190, y, 200, y + 8], fill="#CBD5E1")
        draw.rectangle([400, y, 410, y + 8], fill="#CBD5E1")

    # Power LEDs
    draw.ellipse([90, 80, 102, 92], fill="#22C55E")
    draw.ellipse([115, 80, 127, 92], fill="#3B82F6")

    # Text
    draw.text((300, 205), title, fill="#FFFFFF", anchor="mm")
    draw.text((300, 230), subtitle, fill="#94A3B8", anchor="mm")
    draw.text((300, 350), "SKILL ORBIT INDIA · HARDWARE LAB", fill="#64748B", anchor="mm")

    img.save(filepath, "WEBP", quality=90)
    print(f"Generated {filepath}")

print("All sample product images generated successfully.")
