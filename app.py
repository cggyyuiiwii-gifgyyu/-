import os
import asyncio
from flask import Flask, render_template_string, request, jsonify
from PIL import Image, ImageDraw, ImageFont
from telethon import TelegramClient, events
from telethon.tl.types import ReplyKeyboardMarkup, KeyboardButtonRow, KeyboardButtonWebView

API_ID = int(os.environ.get('API_ID', 1234567))
API_HASH = os.environ.get('API_HASH', 'your_api_hash')
BOT_TOKEN = os.environ.get('BOT_TOKEN', 'your_bot_token')
MINI_APP_URL = os.environ.get('MINI_APP_URL', 'https://your-app.up.railway.app')

app = Flask(__name__)
TEMP_DIR = 'temp_badges'
os.makedirs(TEMP_DIR, exist_ok=True)

client = TelegramClient('bot_session', API_ID, API_HASH)

@app.route('/')
def index():
    if os.path.exists('index.html'):
        with open('index.html', 'r', encoding='utf-8') as f:
            html_content = f.read()
        return render_template_string(html_content)
    return "<h1>الملف index.html غير موجود!</h1>", 404

@app.route('/api/create-pack', methods=['POST'])
def api_create_pack():
    data = request.json
    text = data.get('text', '👑')
    color = data.get('color', '#FFFFFF')
    pack_name = data.get('pack_name', 'VIP_Status_Pack')
    
    # مقاس أيقونة الحالة (Custom Emoji / Status) الدقيق في تليجرام هو 100x100 بكسل
    size = (100, 100)
    image = Image.new("RGBA", size, (0, 0, 0, 0)) # خلفية شفافة بالكامل
    draw = ImageDraw.Draw(image)
    
    # محاولة استخدام خط مناسب للرموز والحروف المصغرة
    try:
        font = ImageFont.truetype("arialbd.ttf", 55)
    except:
        font = ImageFont.load_default()
        
    # توسيط الرمز أو الحرف داخل مقاس 100x100 بدقة
    bbox = draw.textbbox((0, 0), text, font=font)
    w = bbox[2] - bbox[0]
    h = bbox[3] - bbox[1]
    
    x = (size[0] - w) / 2
    y = (size[1] - h) / 2
    
    # رسم ظل خفيف ليبرز الرمز بوضوح بجانب الاسم
    draw.text((x + 2, y + 2), text, font=font, fill=(0, 0, 0, 200))
    # رسم النص أو الرمز الأساسي
    draw.text((x, y), text, font=font, fill=color)
    
    file_path = os.path.join(TEMP_DIR, f"{pack_name}_{os.urandom(2).hex()}.png")
    image.save(file_path, "PNG", optimize=True)
    
    # رابط الحزمة المباشر على تليجرام
    pack_link = f"https://t.me/addstickers/{pack_name}"
    
    return jsonify({
        'status': 'success',
        'file_path': file_path,
        'pack_link': pack_link
    })

@client.on(events.NewMessage(pattern='/start'))
async def start(event):
    button = [KeyboardButtonWebView(text="👑 فتح استوديو أيقونات الحالة المميزة", url=MINI_APP_URL)]
    keyboard = ReplyKeyboardMarkup(rows=[KeyboardButtonRow(buttons=button)], resize=True)
    await event.respond("✨ أهلاً بك يا غالي! اضغط على الزر أدناه لفتح التطبيق المصغر وتصميم أيقونتك الشفافة الخاصة بالمشتركين المميزين:", buttons=keyboard)

async def main():
    await client.start(bot_token=BOT_TOKEN)
    print("🤖 بوت أيقونات الحالة المميزة يعمل بكفاءة تامة...")
    await client.run_until_disconnected()

if __name__ == '__main__':
    import threading
    # ضبط قراءة المنفذ ليتوافق تماماً مع منفذ Railway (8080 أو المتغير البيئي)
    port = int(os.environ.get('PORT', 8080))
    threading.Thread(target=lambda: app.run(host='0.0.0.0', port=port, debug=False)).start()
    asyncio.run(main())
