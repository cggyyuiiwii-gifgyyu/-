import os
import asyncio
import re
import requests
from flask import Flask, render_template_string, request, jsonify
from PIL import Image, ImageDraw, ImageFont
from telethon import TelegramClient, events
from telethon.tl.types import ReplyInlineMarkup, KeyboardButtonRow, KeyboardButtonWebView

API_ID = int(os.environ.get('API_ID', 1234567))
API_HASH = os.environ.get('API_HASH', 'your_api_hash')
BOT_TOKEN = os.environ.get('BOT_TOKEN', 'your_bot_token')
MINI_APP_URL = "https://daring-encouragement-production-3257.up.railway.app"
DEV_ID = 5126968608  # معرف المطور الأساسي

app = Flask(__name__)
TEMP_DIR = 'temp_badges'
os.makedirs(TEMP_DIR, exist_ok=True)

client = TelegramClient('bot_session', API_ID, API_HASH)

stats_data = {
    'total_packs': 0,
    'active_users': set()
}

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
    raw_title = data.get('pack_name', 'VIP Status Pack')
    user_id = data.get('user_id', DEV_ID)
    action_type = data.get('action_type', 'new')
    target_pack = data.get('target_pack', '')

    clean_title = re.sub(r'[^a-zA-Z0-9]', '', raw_title).lower()
    if not clean_title:
        clean_title = "vipsticker"
        
    safe_name = target_pack if (action_type == 'add' and target_pack) else f"{clean_title}_{user_id}_by_bot"
    
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
    
    file_path = os.path.join(TEMP_DIR, f"{safe_name}_{os.urandom(2).hex()}.png")
    image.save(file_path, "PNG", optimize=True)
    
    if not os.path.exists(file_path) or os.path.getsize(file_path) == 0:
        return jsonify({'status': 'error', 'error': 'فشل حفظ ملف الصورة محلياً'})

    if action_type == 'add':
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/addStickerToSet"
        with open(file_path, 'rb') as sticker_file:
            files = {'png_sticker': (os.path.basename(file_path), sticker_file, 'image/png')}
            payload = {
                'user_id': user_id,
                'name': safe_name,
                'emoji_list': ['👑']
            }
            response = requests.post(url, data=payload, files=files)
            res_json = response.json()
    else:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/createNewStickerSet"
        with open(file_path, 'rb') as sticker_file:
            files = {'png_sticker': (os.path.basename(file_path), sticker_file, 'image/png')}
            payload = {
                'user_id': user_id,
                'name': safe_name,
                'title': raw_title,
                'sticker_format': 'static',
                'emojis': '👑'
            }
            response = requests.post(url, data=payload, files=files)
            res_json = response.json()
            
            if not res_json.get('ok'):
                safe_name = f"pack{user_id}{os.urandom(3).hex()}bybot"
                payload['name'] = safe_name
                with open(file_path, 'rb') as retry_file:
                    retry_files = {'png_sticker': (os.path.basename(file_path), retry_file, 'image/png')}
                    response = requests.post(url, data=payload, files=retry_files)
                    res_json = response.json()
    
    if res_json.get('ok'):
        stats_data['total_packs'] += 1
        pack_link = f"https://t.me/addstickers/{safe_name}"
        return jsonify({'status': 'success', 'pack_link': pack_link, 'pack_name': safe_name})
    else:
        return jsonify({'status': 'error', 'error': res_json.get('description', 'خطأ غير معروف من تليجرام')})

@client.on(events.NewMessage(pattern='/start'))
async def start(event):
    sender = await event.get_sender()
    user_id = sender.id
    stats_data['active_users'].add(user_id)
    
    # زر شفاف احترافي لفتح التطبيق المصغر حصراً بدون تداخل
    button_webapp = KeyboardButtonWebView(text="👑 فتح استوديو أيقونات الحالة المميزة", url=MINI_APP_URL)
    keyboard = ReplyInlineMarkup(rows=[KeyboardButtonRow(buttons=[button_webapp])])
    
    welcome_text = "✨ أهلاً بك يا غالي في استوديو الأيقونات والحزم الشفافة بدقة 100x100!\nاضغط على الزر أدناه لفتح التطبيق وتصميم وتصدير حزمك مباشرة لتليجرام:"
    
    if user_id == DEV_ID:
        welcome_text += "\n\n🛠 **مرحباً بك يا مطورنا!** يمكنك إرسال كلمة `لوحة الأدمن` لعرض الإحصائيات."
        
    await event.respond(welcome_text, buttons=keyboard)

@client.on(events.NewMessage(pattern='لوحة الأدمن'))
async def dev_panel(event):
    if event.sender_id != DEV_ID:
        return
    
    panel_text = (
        "🛠 **لوحة تحكم الأدمن المركزية (المطور):**\n\n"
        f"• معرف المطور (ID): `{DEV_ID}`\n"
        f"• إجمالي الحزم المصنوعة: `{stats_data['total_packs']}`\n"
        f"• المستخدمين النشطين: `{len(stats_data['active_users'])}`\n"
        "• حالة النظام: `يعمل بكفاءة وسلاسة تامة 100%`"
    )
    await event.respond(panel_text)

async def main():
    await client.start(bot_token=BOT_TOKEN)
    print("🤖 بوت استوديو الملصقات يعمل بكفاءة تامة...")
    await client.run_until_disconnected()

if __name__ == '__main__':
    import threading
    port = int(os.environ.get('PORT', 8080))
    
    flask_thread = threading.Thread(target=lambda: app.run(host='0.0.0.0', port=port, debug=False))
    flask_thread.daemon = True
    flask_thread.start()
    
    asyncio.run(main())
