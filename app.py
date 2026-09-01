import os
import asyncio
from flask import Flask, render_template_string, request, jsonify
from PIL import Image, ImageDraw, ImageFont
from telethon import TelegramClient, events
from telethon.tl.types import ReplyInlineMarkup, KeyboardButtonRow, KeyboardButtonWebView

API_ID = int(os.environ.get('API_ID', 1234567))
API_HASH = os.environ.get('API_HASH', 'your_api_hash')
BOT_TOKEN = os.environ.get('BOT_TOKEN', 'your_bot_token')
MINI_APP_URL = "https://daring-encouragement-production-3257.up.railway.app"
DEV_ID = 5126968608  # معرف المطور الخاص بك

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
    pack_title = data.get('pack_name', 'VIP Status Pack')
    user_id = data.get('user_id', DEV_ID)
    
    safe_name = f"vip_badge_{user_id}_{os.urandom(2).hex()}_by_bot"
    
    size = (100, 100)
    image = Image.new("RGBA", size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    
    try:
        font = ImageFont.truetype("arialbd.ttf", 55)
    except:
        font = ImageFont.load_default()
        
    bbox = draw.textbbox((0, 0), text, font=font)
    w = bbox[2] - bbox[0]
    h = bbox[3] - bbox[1]
    
    x = (size[0] - w) / 2
    y = (size[1] - h) / 2
    
    draw.text((x + 2, y + 2), text, font=font, fill=(0, 0, 0, 200))
    draw.text((x, y), text, font=font, fill=color)
    
    file_path = os.path.join(TEMP_DIR, f"{safe_name}.png")
    image.save(file_path, "PNG", optimize=True)
    
    import requests
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/createNewStickerSet"
    
    with open(file_path, 'rb') as sticker_file:
        files = {'png_sticker': sticker_file}
        payload = {
            'user_id': user_id,
            'name': safe_name,
            'title': pack_title,
            'sticker_format': 'static',
            'emojis': '👑'
        }
        response = requests.post(url, data=payload, files=files)
        res_json = response.json()
    
    if res_json.get('ok'):
        pack_link = f"https://t.me/addstickers/{safe_name}"
        return jsonify({'status': 'success', 'pack_link': pack_link})
    else:
        alt_name = f"badge_{user_id}_{os.urandom(3).hex()}_by_bot"
        payload['name'] = alt_name
        with open(file_path, 'rb') as sticker_file:
            files = {'png_sticker': sticker_file}
            response = requests.post(url, data=payload, files=files)
            res_json = response.json()
            
        if res_json.get('ok'):
            pack_link = f"https://t.me/addstickers/{alt_name}"
            return jsonify({'status': 'success', 'pack_link': pack_link})
        else:
            return jsonify({'status': 'error', 'error': res_json.get('description', 'خطأ غير معروف')})

@client.on(events.NewMessage(pattern='/start'))
async def start(event):
    # زر التطبيق المصغر فقط لتجنب أي تعارض في الأزرار
    button_webapp = KeyboardButtonWebView(text="👑 فتح استوديو أيقونات الحالة المميزة", url=MINI_APP_URL)
    keyboard = ReplyInlineMarkup(rows=[KeyboardButtonRow(buttons=[button_webapp])])
    
    await event.respond(
        "✨ أهلاً بك يا غالي في استوديو الأيقونات المميزة!\nاضغط على الزر أدناه لفتح التطبيق وتصميم حزمة ملصقاتك الشفافة بدقة 100x100:", 
        buttons=keyboard
    )

@client.on(events.NewMessage(pattern='لوحة المطور'))
async def dev_panel(event):
    if event.sender_id != DEV_ID:
        return
    await event.respond("🛠 **أهلاً بك يا مطورنا في لوحة التحكم المركزية:**\n- الحالة: النظام يعمل بكفاءة تامة على ريلواي 🚀")

async def main():
    await client.start(bot_token=BOT_TOKEN)
    print("🤖 بوت أيقونات الحالة المميزة يعمل بكفاءة تامة...")
    await client.run_until_disconnected()

if __name__ == '__main__':
    import threading
    port = int(os.environ.get('PORT', 8080))
    
    flask_thread = threading.Thread(target=lambda: app.run(host='0.0.0.0', port=port, debug=False))
    flask_thread.daemon = True
    flask_thread.start()
    
    asyncio.run(main())
