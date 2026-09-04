import asyncio
import logging
import math
import os
import random
import string
import time
import secrets
from pathlib import Path

import psycopg2
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

logging.basicConfig(level=logging.ERROR)

TOKEN = os.getenv("BOT_TOKEN", "").strip()
ADMIN_ID = 5126968608
ADMIN_USERNAME = "@toe7e"

OFFICIAL_CHANNEL = "@StarMineer"

def get_db_connection():
    return psycopg2.connect(
        dbname="postgres",
        user="postgres.uwzcegdsutfxfahcicyh",
        password=os.getenv("DB_PASSWORD", "Mustafa1982Mustafa"),
        host="aws-0-ap-southeast-1.pooler.supabase.com",
        port=5432
    )

def convert_arabic_digits(text: str) -> str:
    if not text:
        return ""
    arabic_digits = "٠١٢٣٤٥٦٧٨٩"
    for i, d in enumerate(arabic_digits):
        text = text.replace(d, str(i))
    return text.strip()

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id BIGINT PRIMARY KEY,
            first_name TEXT,
            username TEXT,
            points INTEGER DEFAULT 0,
            energy INTEGER DEFAULT 500,
            last_energy_reset BIGINT DEFAULT 0,
            last_spin BIGINT DEFAULT 0,
            last_mine BIGINT DEFAULT 0,
            referrals INTEGER DEFAULT 0,
            referred_by BIGINT DEFAULT 0,
            ref_rewarded INTEGER DEFAULT 0,
            captcha_verified INTEGER DEFAULT 0,
            is_banned INTEGER DEFAULT 0,
            mine_count INTEGER DEFAULT 0,
            gang_id INTEGER DEFAULT 0,
            shield_until BIGINT DEFAULT 0,
            last_shield_buy BIGINT DEFAULT 0
        )
    ''')

    cursor.execute("UPDATE users SET points=COALESCE(points,0), energy=COALESCE(energy,500), last_energy_reset=COALESCE(last_energy_reset,%s), last_spin=COALESCE(last_spin,0), last_mine=COALESCE(last_mine,0), referrals=COALESCE(referrals,0), referred_by=COALESCE(referred_by,0), ref_rewarded=COALESCE(ref_rewarded,0), captcha_verified=COALESCE(captcha_verified,0), is_banned=COALESCE(is_banned,0), mine_count=COALESCE(mine_count,0), gang_id=COALESCE(gang_id,0), shield_until=COALESCE(shield_until,0), last_shield_buy=COALESCE(last_shield_buy,0)", (int(time.time()),))

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value INTEGER DEFAULT 0
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS fixed_channels (
            id SERIAL PRIMARY KEY,
            target TEXT UNIQUE
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS gift_codes (
            code TEXT PRIMARY KEY,
            points INTEGER,
            uses_left INTEGER DEFAULT 1
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS gift_code_uses (
            code TEXT,
            user_id BIGINT,
            PRIMARY KEY (code, user_id)
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS point_links (
            link_id TEXT PRIMARY KEY,
            points INTEGER,
            max_uses INTEGER,
            uses_count INTEGER DEFAULT 0,
            creator_id BIGINT DEFAULT 0
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS point_link_uses (
            link_id TEXT,
            user_id BIGINT,
            PRIMARY KEY (link_id, user_id)
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS redeem_codes (
            code TEXT PRIMARY KEY,
            user_id BIGINT,
            item_type TEXT,
            item_value TEXT,
            status TEXT DEFAULT 'PENDING'
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS dynamic_forced_channels (
            id SERIAL PRIMARY KEY,
            target TEXT,
            target_count INTEGER,
            current_count INTEGER DEFAULT 0
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_forced_joins (
            user_id BIGINT,
            channel_id INTEGER,
            PRIMARY KEY (user_id, channel_id)
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS gangs (
            gang_id SERIAL PRIMARY KEY,
            name TEXT UNIQUE,
            leader_id BIGINT,
            balance INTEGER DEFAULT 0,
            members_count INTEGER DEFAULT 1
        )
    ''')

    conn.commit()

    defaults = [
        ('discount', 0),
        ('store_disabled', 0),
        ('maintenance_mode', 0),
        ('price_star_15', 15000),
        ('price_star_25', 25000),
        ('gangs_disabled', 0),
        ('security_disabled', 0),
        ('transfer_disabled', 0),
        ('referral_reward_points', 500)
    ]
    for key, val in defaults:
        cursor.execute("INSERT INTO settings (key, value) VALUES (%s, %s) ON CONFLICT (key) DO NOTHING", (key, val))

    fixed_chs = ['@rrs2r', '@StarMineer', '@StarMineeerBot']
    for ch in fixed_chs:
        cursor.execute("INSERT INTO fixed_channels (target) VALUES (%s) ON CONFLICT (target) DO NOTHING", (ch,))

    conn.commit()
    cursor.close()
    conn.close()

def generate_code(prefix="STAR-"):
    return prefix + "".join(random.choices(string.ascii_uppercase + string.digits, k=6))

def get_setting(key: str) -> int:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT value FROM settings WHERE key = %s", (key,))
    row = cursor.fetchone()
    cursor.close()
    conn.close()
    return row[0] if row else 0

def set_setting(key: str, value: int):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO settings (key, value) VALUES (%s, %s) ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value", (key, value))
    conn.commit()
    cursor.close()
    conn.close()

def get_fixed_channels():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, target FROM fixed_channels")
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    return rows

def get_active_dynamic_channels():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, target, target_count, current_count FROM dynamic_forced_channels")
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    return rows

def get_user(user_id: int, first_name: str = "", username: str = ""):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT COALESCE(points,0), COALESCE(energy,500), COALESCE(last_energy_reset,%s), COALESCE(last_spin,0), COALESCE(referrals,0), COALESCE(is_banned,0), COALESCE(last_mine,0), COALESCE(referred_by,0), COALESCE(ref_rewarded,0), COALESCE(captcha_verified,0), COALESCE(mine_count,0), COALESCE(gang_id,0), COALESCE(shield_until,0) FROM users WHERE user_id = %s",
        (int(time.time()), user_id)
    )
    row = cursor.fetchone()
    if not row:
        cursor.execute(
            "INSERT INTO users (user_id, first_name, username, points, energy, last_energy_reset, last_spin, last_mine, referrals, referred_by, ref_rewarded, captcha_verified, is_banned, mine_count, gang_id, shield_until, last_shield_buy) VALUES (%s,%s,%s,0,500,%s,0,0,0,0,0,0,0,0,0,0,0)",
            (user_id, first_name, username, int(time.time()))
        )
        conn.commit()
        row = (0, 500, int(time.time()), 0, 0, 0, 0, 0, 0, 0, 0, 0, 0)
    else:
        cursor.execute("UPDATE users SET first_name=%s, username=%s, points=COALESCE(points,0), energy=COALESCE(energy,500), last_energy_reset=COALESCE(last_energy_reset,%s), last_spin=COALESCE(last_spin,0), last_mine=COALESCE(last_mine,0), referrals=COALESCE(referrals,0), referred_by=COALESCE(referred_by,0), ref_rewarded=COALESCE(ref_rewarded,0), captcha_verified=COALESCE(captcha_verified,0), is_banned=COALESCE(is_banned,0), mine_count=COALESCE(mine_count,0), gang_id=COALESCE(gang_id,0), shield_until=COALESCE(shield_until,0) WHERE user_id=%s", (first_name, username, int(time.time()), user_id))
        conn.commit()

    cursor.close()
    conn.close()
    
    return {
        "points": row[0], "energy": row[1], "last_spin": row[3],
        "referrals": row[4], "is_banned": row[5], "last_mine": row[6],
        "referred_by": row[7], "ref_rewarded": row[8], "captcha_verified": row[9],
        "mine_count": row[10], "gang_id": row[11], "shield_until": row[12]
    }

def update_points(user_id: int, pts: int):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET points = points + %s WHERE user_id = %s", (pts, user_id))
    conn.commit()
    cursor.close()
    conn.close()

def send_captcha(context: ContextTypes.DEFAULT_TYPE, user_id: int):
    n1 = random.randint(1, 9)
    n2 = random.randint(1, 9)
    correct = n1 + n2
    context.user_data['captcha_answer'] = correct
    return f"🤖 اختبار التحقق البشري (الكابتشا):\n\nكم حاصل جمع: {n1} + {n2} ؟\nأرسل الناتج كـ رقم في المحادثة لتأكيد حسابك."

async def check_subscription(user_id: int, context: ContextTypes.DEFAULT_TYPE) -> bool:
    if user_id == ADMIN_ID:
        return True

    channels_to_check = []
    for _, ch in get_fixed_channels():
        ch_clean = ch.split('/')[-1]
        channels_to_check.append(f"@{ch_clean}" if not ch_clean.startswith("@") else ch_clean)

    dyn_channels = get_active_dynamic_channels()
    for ch_item in dyn_channels:
        ch_clean = ch_item[1].split('/')[-1]
        channels_to_check.append(f"@{ch_clean}" if not ch_clean.startswith("@") else ch_clean)

    async def check_single(ch_id: str) -> bool:
        try:
            member = await context.bot.get_chat_member(chat_id=ch_id, user_id=user_id)
            return member.status in ["member", "administrator", "creator"]
        except Exception:
            return True

    results = await asyncio.gather(*(check_single(ch) for ch in channels_to_check))
    return all(results)

async def get_sub_keyboard(context: ContextTypes.DEFAULT_TYPE):
    buttons = []
    for _, ch in get_fixed_channels():
        ch_clean = ch.split('/')[-1]
        ch_id = f"@{ch_clean}" if not ch_clean.startswith("@") else ch_clean
        title = "📢 قناة رسمية"
        try:
            chat = await context.bot.get_chat(ch_id)
            if chat.title:
                title = f"📢 {chat.title}"
        except Exception:
            pass
        url = ch if ch.startswith("http") else f"https://t.me/{ch_clean.replace('@', '')}"
        buttons.append([InlineKeyboardButton(title, url=url)])

    dyn_channels = get_active_dynamic_channels()
    for ch_item in dyn_channels:
        ch_target = ch_item[1]
        ch_clean = ch_target.split('/')[-1]
        ch_id = f"@{ch_clean}" if not ch_clean.startswith("@") else ch_clean
        btn_title = "⭐ قناة ممولة"
        try:
            chat = await context.bot.get_chat(ch_id)
            if chat.title:
                btn_title = f"⭐ {chat.title}"
        except Exception:
            pass
        url = ch_target if ch_target.startswith("http") else f"https://t.me/{ch_clean.replace('@', '')}"
        buttons.append([InlineKeyboardButton(btn_title, url=url)])

    buttons.append([InlineKeyboardButton("✅ تحقّق من الاشتراك", callback_data="check_forced_sub")])
    return InlineKeyboardMarkup(buttons)

def get_main_keyboard(user_id: int):
    buttons = [
        [
            InlineKeyboardButton("🎡 عجلة الحظ", callback_data="btn_spin"),
            InlineKeyboardButton("⭐ متجر النجوم", callback_data="btn_store")
        ],
        [
            InlineKeyboardButton("🔄 تحويل نقاط", callback_data="btn_transfer_menu"),
            InlineKeyboardButton("👥 دعوة الأصدقاء", callback_data="btn_ref")
        ],
        [
            InlineKeyboardButton("🎁 كود النقاط", callback_data="btn_redeem_gift")
        ],
        [
            InlineKeyboardButton("🏆 توب الإحالات", callback_data="btn_top_ref"),
            InlineKeyboardButton("📊 حسابي", callback_data="btn_profile")
        ],
        [
            InlineKeyboardButton("📖 التعليمات", callback_data="btn_instructions")
        ]
    ]
    if user_id == ADMIN_ID:
        buttons.append([InlineKeyboardButton("👑 لوحة الأدمن", callback_data="admin_panel")])
    return InlineKeyboardMarkup(buttons)

def record_dynamic_forced_joins(user_id: int):
    dyn_channels = get_active_dynamic_channels()
    conn = get_db_connection()
    cursor = conn.cursor()
    for ch_item in dyn_channels:
        ch_id, ch_target, target_count, current_count = ch_item
        cursor.execute(
            "INSERT INTO user_forced_joins (user_id, channel_id) VALUES (%s, %s) ON CONFLICT (user_id, channel_id) DO NOTHING",
            (user_id, ch_id)
        )
        cursor.execute(
            "UPDATE dynamic_forced_channels SET current_count = current_count + 1 WHERE id = %s AND NOT EXISTS (SELECT 1 FROM user_forced_joins WHERE user_id = %s AND channel_id = %s)",
            (ch_id, user_id, ch_id)
        )
    conn.commit()
    cursor.close()
    conn.close()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_user or not update.message:
        return
    context.user_data['admin_action'] = None
    context.user_data['user_action'] = None

    user = update.effective_user
    username_str = f"@{user.username}" if user.username else "بدون معرف"

    if get_setting("maintenance_mode") == 1 and user.id != ADMIN_ID:
        await update.message.reply_text("🛠️ البوت حالياً في وضع الصيانة والتحديث!\nيرجى المحاولة لاحقاً.")
        return

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM users WHERE user_id = %s", (user.id,))
    is_new_user = cursor.fetchone() is None
    cursor.close()
    conn.close()

    ref_id = 0
    if context.args and context.args[0].isdigit():
        temp_ref = int(context.args[0])
        if temp_ref != user.id:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT COALESCE(referred_by,0), COALESCE(ref_rewarded,0) FROM users WHERE user_id = %s", (user.id,))
            current_ref = cursor.fetchone()
            cursor.execute("SELECT 1 FROM users WHERE user_id = %s", (temp_ref,))
            referrer_exists = cursor.fetchone() is not None
            cursor.close()
            conn.close()
            if referrer_exists and (not current_ref or (int(current_ref[0] or 0) == 0 and int(current_ref[1] or 0) == 0)):
                ref_id = temp_ref

    u_data = get_user(user.id, user.first_name, username_str)

    if ref_id > 0:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE users SET referred_by = %s WHERE user_id = %s AND COALESCE(referred_by, 0) = 0 AND COALESCE(ref_rewarded, 0) = 0",
            (ref_id, user.id),
        )
        conn.commit()
        cursor.close()
        conn.close()

    if is_new_user and user.id != ADMIN_ID:
        try:
            admin_notice = (
                f"👤 عضو جديد انضم للبوت!\n\n"
                f"🔹 الاسم: {user.first_name}\n"
                f"🔹 المعرف: {username_str}\n"
                f"🆔 الآيدي: {user.id}"
            )
            await context.bot.send_message(chat_id=ADMIN_ID, text=admin_notice)
        except Exception:
            pass

    is_subbed = await check_subscription(user.id, context)
    if not is_subbed:
        msg_sub = f"⚠️ عذراً {user.first_name}!\n\nلاستخدام البوت، يجب الانضمام للقنوات الإجبارية أدناه 👇"
        kb = await get_sub_keyboard(context)
        await update.message.reply_text(msg_sub, reply_markup=kb)
        return

    if context.args:
        arg = context.args[0]
        if arg.startswith("link_tr_") and get_setting("transfer_disabled") == 1 and user.id != ADMIN_ID:
            await update.message.reply_text("⛔ تحويل النقاط متوقف حالياً من قبل الإدارة.")
            return

        if arg.startswith("link_") or arg.startswith("link_tr_"):
            link_id = arg
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT points, max_uses, uses_count, creator_id FROM point_links WHERE link_id = %s", (link_id,))
            link_data = cursor.fetchone()

            if link_data:
                pts, max_u, uses_c, creator_id = link_data
                cursor.execute("SELECT 1 FROM point_link_uses WHERE link_id = %s AND user_id = %s", (link_id, user.id))
                already_used = cursor.fetchone()

                if already_used:
                    await update.message.reply_text("❌ لقد حصلت على النقاط من هذا الرابط سابقاً!")
                elif uses_c >= max_u:
                    await update.message.reply_text("❌ عذراً، هذا الرابط اكتمل الحد الأقصى لمستخدميه!")
                else:
                    cursor.execute("INSERT INTO point_link_uses (link_id, user_id) VALUES (%s, %s)", (link_id, user.id))
                    cursor.execute("UPDATE point_links SET uses_count = uses_count + 1 WHERE link_id = %s", (link_id,))
                    conn.commit()
                    update_points(user.id, pts)
                    await update.message.reply_text(f"🎉 مبروك! حصلت على +{pts} نقطة من الرابط!")

                    admin_notice = (
                        f"🔔 إشعار استخدام رابط نقاط!\n\n"
                        f"👤 المستخدم: {user.first_name} ({username_str})\n"
                        f"🆔 الآيدي: {user.id}\n"
                        f"🪙 النقاط المحصلة: {pts} نقطة\n"
                        f"🔗 معرف الرابط: {link_id}"
                    )
                    try:
                        await context.bot.send_message(chat_id=ADMIN_ID, text=admin_notice)
                    except Exception:
                        pass

                    if creator_id > 0 and creator_id != user.id and creator_id != ADMIN_ID:
                        try:
                            transfer_notice = (
                                f"🔔 إشعار تحويل نقاط!\n\n"
                                f"قام المستخدم {user.first_name} ({username_str}) بفتح رابط التحويل الخاص بك واستلم النقاط بنجاح! ✨"
                            )
                            await context.bot.send_message(chat_id=creator_id, text=transfer_notice)
                        except Exception:
                            pass
            cursor.close()
            conn.close()

    if u_data['is_banned']:
        await update.message.reply_text("🚫 عذراً، حسابك محظور من استخدام البوت!")
        return

    record_dynamic_forced_joins(user.id)

    if not u_data['captcha_verified'] and user.id != ADMIN_ID:
        captcha_msg = send_captcha(context, user.id)
        await update.message.reply_text(captcha_msg)
        return

    discount = get_setting("discount")
    discount_txt = f"\n🔥 تخفيضات المتجر: {discount}% خصم!" if discount > 0 else ""

    msg = (
        f"🚀 مرحباً بك في بوت الخدمات والنجوم 🌟\n\n"
        f"👤 المستخدم: {user.first_name}\n"
        f"🪙 رصيدك: {u_data['points']} نقطة{discount_txt}\n\n"
        "اختر ما تحب من الأزرار أدناه 👇"
    )
    await update.message.reply_text(msg, reply_markup=get_main_keyboard(user.id))

async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query or not query.from_user or not query.message:
        return
    user_id = query.from_user.id
    data = query.data

    if get_setting("maintenance_mode") == 1 and user_id != ADMIN_ID:
        await query.answer("🛠️ البوت حالياً في وضع الصيانة!", show_alert=True)
        return

    if data == "check_forced_sub":
        is_sub = await check_subscription(user_id, context)
        if is_sub:
            record_dynamic_forced_joins(user_id)
            u_data = get_user(user_id, query.from_user.first_name)
            if not u_data['captcha_verified'] and user_id != ADMIN_ID:
                await query.answer("✅ تم الاشتراك! حل اختبار الكابتشا الآن.", show_alert=True)
                captcha_msg = send_captcha(context, user_id)
                await query.message.reply_text(captcha_msg)
                return

            await query.answer("✅ تم التأكد من اشتراكك بنجاح!", show_alert=True)
            msg = f"🚀 أهلاً بك مجدداً {query.from_user.first_name}!\nرصيدك الحالي: {u_data['points']} نقطة."
            await query.message.edit_text(msg, reply_markup=get_main_keyboard(user_id))
        else:
            await query.answer("❌ لم تشترك في جميع القنوات بعد!", show_alert=True)
        return

    if not await check_subscription(user_id, context):
        await query.answer("⚠️ يجب الاشتراك بالقنوات الإجبارية أولاً!", show_alert=True)
        kb = await get_sub_keyboard(context)
        await query.message.reply_text("⚠️ يرجى الانضمام للقنوات الإجبارية لاستخدام البوت:", reply_markup=kb)
        return

    u_data = get_user(user_id, query.from_user.first_name)

    if u_data['is_banned']:
        await query.answer("🚫 حسابك محظور!", show_alert=True)
        return

    if not u_data['captcha_verified'] and user_id != ADMIN_ID:
        await query.answer("⚠️ يرجى حل الكابتشا في المحادثة أولاً!", show_alert=True)
        return

    if data == "btn_transfer_menu":
        if get_setting("transfer_disabled") == 1 and user_id != ADMIN_ID:
            await query.answer("⛔ تحويل النقاط متوقف حالياً من قبل الإدارة.", show_alert=True)
            return
        await query.answer()
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🆔 تحويل مباشر عبر الآيدي", callback_data="btn_tr_id")],
            [InlineKeyboardButton("🔗 إنشاء رابط تحويل", callback_data="btn_tr_link")],
            [InlineKeyboardButton("⬅️ العودة للرئيسية", callback_data="btn_main_menu")]
        ])
        msg = (
            "🔄 قسم تحويل النقاط:\n\n"
            "اختر طريقة التحويل المناسبة لك:\n"
            "1️⃣ التحويل المباشر: إرسال نقاط فورية إلى حساب شخص عبر ID.\n"
            "2️⃣ رابط التحويل: إنشاء رابط حصري بالنقاط يفتحه المستلم.\n\n"
            "⚠️ ملاحظة: خصم 10% فقط لكل عملية تحويل."
        )
        await query.message.reply_text(msg, reply_markup=kb)

    elif data == "btn_tr_id":
        if get_setting("transfer_disabled") == 1 and user_id != ADMIN_ID:
            await query.answer("⛔ تحويل النقاط متوقف حالياً من قبل الإدارة.", show_alert=True)
            return
        await query.answer()
        context.user_data['user_action'] = 'transfer_by_id'
        msg = (
            "🆔 تحويل نقاط مباشر عبر الآيدي:\n\n"
            "أرسل البيانات بالصيغة التالية:\n"
            "الآيدي|عدد النقاط\n\n"
            "مثال:\n"
            "5126968608|1000"
        )
        await query.message.reply_text(msg)

    elif data == "btn_tr_link":
        if get_setting("transfer_disabled") == 1 and user_id != ADMIN_ID:
            await query.answer("⛔ تحويل النقاط متوقف حالياً من قبل الإدارة.", show_alert=True)
            return
        await query.answer()
        context.user_data['user_action'] = 'create_transfer_link'
        msg = (
            "🔗 إنشاء رابط تحويل نقاط:\n\n"
            "أرسل عدد النقاط المراد تحويلها الآن في المحادثة 👇\n"
            f"💰 رصيدك المتاح: {u_data['points']} نقطة"
        )
        await query.message.reply_text(msg)

    elif data == "btn_main_menu":
        await query.answer()
        msg = (
            f"🚀 مرحباً بك في بوت الخدمات والنجوم 🌟\n\n"
            f"👤 المستخدم: {query.from_user.first_name}\n"
            f"🪙 رصيدك: {u_data['points']} نقطة\n\n"
            "اختر ما تحب من الأزرار أدناه 👇"
        )
        await query.message.reply_text(msg, reply_markup=get_main_keyboard(user_id))

    elif data == "btn_instructions":
        await query.answer()
        inst_text = (
            "📖 دليل وتعليمات استخدام البوت الشامل 🌟\n\n"
            "1️⃣ عجلة الحظ:\n"
            "• جرب حظك كل 12 ساعة واربح نقاط مجانية.\n\n"
            "2️⃣ متجر النجوم:\n"
            "• استبدل نقاطك بنجوم تلغرام بكل سهولة.\n\n"
            "3️⃣ التحويل ودعوة الأصدقاء:\n"
            "• حول النقاط لأصدقآئك أو ادعهم لربح مكافآت فورية."
        )
        kb_dev = InlineKeyboardMarkup([[InlineKeyboardButton("👨‍💻 التواصل مع المطور", url=f"https://t.me/{ADMIN_USERNAME.replace('@', '')}")]])
        await query.message.reply_text(inst_text, reply_markup=kb_dev)

    elif data == "btn_profile":
        await query.answer()
        text = (
            "📊 معلومات حسابك الشاملة:\n\n"
            f"👤 الاسم: {query.from_user.first_name}\n"
            f"🆔 الآيدي: {user_id}\n"
            f"🪙 النقاط: {u_data['points']} نقطة\n"
            f"👥 عدد الدعوات: {u_data['referrals']} شخص\n"
            f"✅ التحقق البشري: مؤكد (الكابتشا)"
        )
        await query.message.reply_text(text, reply_markup=get_main_keyboard(user_id))

    elif data == "btn_store":
        await query.answer()
        is_disabled = get_setting("store_disabled")
        if is_disabled == 1 and user_id != ADMIN_ID:
            await query.message.reply_text("⛔ عذراً، الشراء متوقف حالياً للصيانة!")
            return

        p15_base = get_setting("price_star_15")
        p25_base = get_setting("price_star_25")
        discount = get_setting("discount")
        mult = (100 - discount) / 100

        c15 = int(p15_base * mult)
        c25 = int(p25_base * mult)
        disc_txt = f"\n🔥 تخفيض حالي: {discount}% خصم!" if discount > 0 else ""

        text = (
            f"⭐ متجر تحويل النقاط إلى نجوم تلغرام:{disc_txt}\n\n"
            f"1️⃣ 15 نجمة = {c15} نقطة\n"
            f"2️⃣ 25 نجمة = {c25} نقطة\n\n"
            f"💰 رصيدك الحالي: {u_data['points']} نقطة"
        )
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton(f"طلب 15 نجمة ⭐ ({c15} نقطة)", callback_data=f"buy_star_15_{c15}")],
            [InlineKeyboardButton(f"طلب 25 نجمة ⭐ ({c25} نقطة)", callback_data=f"buy_star_25_{c25}")],
        ])
        await query.message.reply_text(text, reply_markup=kb)

    elif data.startswith("buy_star_"):
        await query.answer()
        is_disabled = get_setting("store_disabled")
        if is_disabled == 1 and user_id != ADMIN_ID:
            await query.message.reply_text("⛔ عذراً، الشراء متوقف حالياً من قبل الإدارة!")
            return

        try:
            parts = data.split("_")
            stars_amount = parts[2]
            cost = int(parts[3])

            if u_data['points'] < cost:
                await query.message.reply_text(f"❌ رصيدك لا يكفي! تحتاج إلى {cost} نقطة لشراء {stars_amount} نجمة.")
                return

            update_points(user_id, -cost)
            code = generate_code()

            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("INSERT INTO redeem_codes (code, user_id, item_type, item_value, status) VALUES (%s, %s, 'star', %s, 'PENDING')", (code, user_id, str(stars_amount)))
            conn.commit()
            cursor.close()
            conn.close()

            admin_order_kb = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("✅ قبول وتسليم", callback_data=f"approve_buy_{code}"),
                    InlineKeyboardButton("❌ رفض وتراجع", callback_data=f"reject_buy_{code}")
                ]
            ])

            uname = f"@{query.from_user.username}" if query.from_user.username else "بدون معرف"
            admin_order_notice = (
                f"🚨 طلب شراء نجوم جديد!\n\n"
                f"👤 المستخدم: {query.from_user.first_name} ({uname})\n"
                f"🆔 الآيدي: {user_id}\n"
                f"⭐ الكمية: {stars_amount} نجمة\n"
                f"🪙 المبلغ المخصوم: {cost} نقطة\n"
                f"🔑 كود الطلب: {code}"
            )

            await context.bot.send_message(chat_id=ADMIN_ID, text=admin_order_notice, reply_markup=admin_order_kb)

            user_msg = (
                f"🎉 تم إرسال طلب الشراء للتحقق!\n\n"
                f"⭐ الكمية المطلوبة: {stars_amount} نجمة\n"
                f"🔑 كود الشراء: {code}\n\n"
                f"⏳ طلبك قيد المراجعة، وسيتم إشعارك والنشر بالقناة فور التسليم!"
            )
            await query.message.reply_text(user_msg)

        except Exception as e:
            logging.error(f"Error in buy_star: {e}")
            await query.message.reply_text("❌ حدث خطأ أثناء معالجة الطلب، يرجى التواصل مع الدعم.")

    elif data.startswith("approve_buy_") and user_id == ADMIN_ID:
        code = data.split("_")[2]
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT user_id, item_value, status FROM redeem_codes WHERE code = %s FOR UPDATE", (code,))
        row = cursor.fetchone()

        if not row:
            await query.answer("❌ هذا الطلب غير موجود!", show_alert=True)
            cursor.close()
            conn.close()
            return

        if row[2] != 'PENDING':
            await query.answer("❌ هذا الطلب تم اتخاذ إجراء فيه مسبقاً!", show_alert=True)
            cursor.close()
            conn.close()
            return

        cursor.execute("UPDATE redeem_codes SET status = 'COMPLETED' WHERE code = %s", (code,))
        conn.commit()
        cursor.close()
        conn.close()

        buyer_id, stars_val = row[0], row[1]

        await query.answer("✅ تم قبول طلب الشراء والتسليم بنجاح!", show_alert=True)
        try:
            await query.message.edit_text(f"{query.message.text}\n\n✅ الحالة: تم التسليم بنجاح بواسطة الأدمن!", reply_markup=None)
        except Exception:
            pass

        try:
            await context.bot.send_message(chat_id=buyer_id, text=f"🎉 مبروك! تم تسليم طلب النجوم الخاص بك ({stars_val} نجمة) بنجاح! ⭐")
        except Exception:
            pass

        try:
            pub_proof = (
                f"✅ إثبات عملية استبدال ناجحة!\n\n"
                f"👤 آيدي المشتري: {buyer_id}\n"
                f"⭐ النجوم المستلمة: {stars_val} نجمة\n"
                f"🔑 كود العملية: {code}\n\n"
                f"🤖 استبدل نقاطك الآن عبر البوت الرسمي:\n"
                f"https://t.me/{(await context.bot.get_me()).username}"
            )
            await context.bot.send_message(chat_id=OFFICIAL_CHANNEL, text=pub_proof)
        except Exception:
            pass

    elif data.startswith("reject_buy_") and user_id == ADMIN_ID:
        code = data.split("_")[2]
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT user_id, item_value, status FROM redeem_codes WHERE code = %s FOR UPDATE", (code,))
        row = cursor.fetchone()

        if not row:
            await query.answer("❌ هذا الطلب غير موجود!", show_alert=True)
            cursor.close()
            conn.close()
            return

        if row[2] != 'PENDING':
            await query.answer("❌ هذا الطلب تم اتخاذ إجراء فيه مسبقاً!", show_alert=True)
            cursor.close()
            conn.close()
            return

        cursor.execute("UPDATE redeem_codes SET status = 'REJECTED' WHERE code = %s", (code,))
        conn.commit()
        cursor.close()
        conn.close()

        buyer_id, stars_val = row[0], row[1]
        p15_base = get_setting("price_star_15")
        p25_base = get_setting("price_star_25")
        discount = get_setting("discount")
        mult = (100 - discount) / 100
        
        cost = int(p15_base * mult) if str(stars_val) == "15" else int(p25_base * mult)

        update_points(buyer_id, cost)

        await query.answer("❌ تم رفض الطلب وإعادة النقاط للمستخدم بنجاح!", show_alert=True)
        try:
            await query.message.edit_text(f"{query.message.text}\n\n❌ الحالة: تم الرفض وإعادة النقاط للمستخدم.", reply_markup=None)
        except Exception:
            pass

        try:
            await context.bot.send_message(chat_id=buyer_id, text=f"⚠️ تم رفض طلب الشراء الخاص بك ({stars_val} نجمة) وتم إعادة نقاطك لحسابك.")
        except Exception:
            pass

    elif data == "btn_ref":
        await query.answer()
        bot_user = (await context.bot.get_me()).username
        ref_link = f"https://t.me/{bot_user}?start={user_id}"
        reward_pts = get_setting("referral_reward_points")
        msg = (
            "👥 برنامج دعوة الأصدقاء الحقيقيين:\n\n"
            f"شارك الرابط واحصل على +{reward_pts} نقطة فور تأكيد صديقك للكابتشا!\n\n"
            f"🔗 رابطك الخاص:\n{ref_link}"
        )
        await query.message.reply_text(msg)

    elif data == "btn_spin":
        await query.answer()
        current_time = int(time.time())
        cooldown = 43200

        if current_time - u_data['last_spin'] < cooldown:
            rem = cooldown - (current_time - u_data['last_spin'])
            hours = rem // 3600
            mins = (rem % 3600) // 60
            await query.message.reply_text(f"⏳ عجلة الحظ غير متاحة!\nعد بعد: {hours} ساعة و {mins} دقيقة.")
            return

        prizes = [100, 250, 500, 1000]
        win = random.choice(prizes)
        update_points(user_id, win)

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET last_spin = %s WHERE user_id = %s", (current_time, user_id))
        conn.commit()
        cursor.close()
        conn.close()

        await query.message.reply_text(f"🎡 مبروك! ربحت {win} نقطة مجانية!")

    elif data == "btn_top_ref":
        await query.answer()
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT first_name, username, referrals FROM users WHERE referrals > 0 ORDER BY referrals DESC LIMIT 10")
        top_refs = cursor.fetchall()
        cursor.close()
        conn.close()

        if not top_refs:
            await query.message.reply_text("🏆 توب الإحالات:\n\nلا يوجد مستخدمون قاموا بدعوة أصدقاء حتى الآن!")
            return

        medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
        msg = "🏆 قائمة أعلى 10 مستخدمين دعوة للأصدقاء (تحديث تلقائي):\n\n"
        
        for i, u in enumerate(top_refs):
            fname, uname, refs = u
            medal = medals[i] if i < len(medals) else f"{i+1}."
            uname_txt = f"({uname})" if uname and uname != "بدون معرف" else ""
            msg += f"{medal} {fname} {uname_txt} 👈 {refs} إحالة\n"

        await query.message.reply_text(msg)

    elif data == "btn_redeem_gift":
        await query.answer()
        context.user_data['user_action'] = 'use_gift_code'
        await query.message.reply_text("🎁 أدخل كود النقاط الخاص بك الآن في المحادثة:")

    elif data == "admin_panel" and user_id == ADMIN_ID:
        await query.answer()
        store_status = get_setting("store_disabled")
        maint_status = get_setting("maintenance_mode")
        transfer_status = get_setting("transfer_disabled")

        store_btn_txt = "🔴 إيقاف الشراء" if store_status == 0 else "🟢 تفعيل الشراء"
        maint_btn_txt = "🛠️ تفعيل الصيانة" if maint_status == 0 else "🟢 إيقاف الصيانة"
        transfer_btn_txt = "🔴 إيقاف التحويل" if transfer_status == 0 else "🟢 تفعيل التحويل"

        kb = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("👥 جميع المستخدمين", callback_data="admin_view_users"),
                InlineKeyboardButton("🔍 استعلام / خصم نقاط", callback_data="admin_user_pts_menu")
            ],
            [
                InlineKeyboardButton("📢 إذاعة للجميع", callback_data="admin_broadcast"),
                InlineKeyboardButton("📢 إدارة القنوات الإجبارية", callback_data="admin_manage_channels")
            ],
            [
                InlineKeyboardButton("🎁 إضافة نقاط", callback_data="admin_give_pts_menu"),
                InlineKeyboardButton("🎫 إنشاء كود نقاط", callback_data="admin_create_code")
            ],
            [
                InlineKeyboardButton("🔗 إنشاء رابط نقاط", callback_data="admin_create_point_link"),
                InlineKeyboardButton("🏷️ تسعير النجوم", callback_data="admin_set_star_prices")
            ],
            [
                InlineKeyboardButton("👥 تعديل سعر الإحالة", callback_data="admin_set_ref_reward"),
                InlineKeyboardButton("🏷️ إعداد التخفيضات", callback_data="admin_discount")
            ],
            [
                InlineKeyboardButton("🚫 حظر / فك حظر", callback_data="admin_ban_menu"),
                InlineKeyboardButton("📊 إحصائيات البوت", callback_data="admin_stats")
            ],
            [
                InlineKeyboardButton("📋 تفاصيل الإحالات", callback_data="admin_referrals"),
                InlineKeyboardButton(transfer_btn_txt, callback_data="admin_toggle_transfer")
            ],
            [
                InlineKeyboardButton(store_btn_txt, callback_data="admin_toggle_store"),
                InlineKeyboardButton(maint_btn_txt, callback_data="admin_toggle_maint")
            ]
        ])
        disc = get_setting("discount")
        ref_reward = get_setting("referral_reward_points")
        status_txt = "مفعل 🟢" if store_status == 0 else "معطل 🔴"
        m_txt = "يعمل 🟢" if maint_status == 0 else "صيانة 🛠️"
        p15 = get_setting("price_star_15")
        p25 = get_setting("price_star_25")
        
        await query.message.reply_text(
            f"👑 لوحة تحكم الأدمن الشاملة:\n\n"
            f"👥 نقاط الإحالة الحالية: {ref_reward} نقطة\n"
            f"🏷️ التخفيض: {disc}%\n"
            f"🛒 المتجر: {status_txt}\n"
            f"🛠️ حالة البوت: {m_txt}\n"
            f"🔄 التحويل: {'متوقف 🔴' if transfer_status == 1 else 'مفعل 🟢'}\n"
            f"⭐ سعر 15 نجمة: {p15} نقطة\n"
            f"⭐ سعر 25 نجمة: {p25} نقطة",
            reply_markup=kb
        )

    elif data == "admin_set_ref_reward" and user_id == ADMIN_ID:
        await query.answer()
        context.user_data['admin_action'] = 'set_ref_reward'
        curr_reward = get_setting("referral_reward_points")
        await query.message.reply_text(
            f"👥 تعديل سعر مكافأة الإحالة:\n\n"
            f"المكافأة الحالية لكل إحالة: {curr_reward} نقطة\n\n"
            "أرسل القيمة الجديدة كـ رقم صحيح الآن 👇"
        )

    elif data == "admin_toggle_transfer" and user_id == ADMIN_ID:
        curr = get_setting("transfer_disabled")
        new_val = 1 if curr == 0 else 0
        set_setting("transfer_disabled", new_val)
        status = "متوقف 🔴" if new_val == 1 else "مفعل 🟢"
        await query.answer("✅ تم تحديث حالة التحويل!", show_alert=True)
        await query.message.reply_text(f"⚙️ حالة تحويل النقاط الآن: {status}\n\nعند الإيقاف، يبقى التحويل متاحاً للأدمن فقط (ID: {ADMIN_ID}).")

    elif data == "admin_referrals" and user_id == ADMIN_ID:
        await query.answer()
        context.user_data['admin_action'] = 'view_referrals'
        await query.message.reply_text("📋 تفاصيل الإحالات\n\nأرسل آيدي الشخص الذي تريد معرفة الأشخاص الذين دخلوا عن طريق إحالته:\n\nمثال: 5126968608")

    elif data == "admin_user_pts_menu" and user_id == ADMIN_ID:
        await query.answer()
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔍 معرفة نقاط مستخدم", callback_data="admin_check_pts")],
            [InlineKeyboardButton("➖ خصم نقاط من مستخدم", callback_data="admin_deduct_pts")],
            [InlineKeyboardButton("⬅️ العودة", callback_data="admin_panel")]
        ])
        await query.message.reply_text("🔍 إدارة نقاط ورصيد المستخدمين:", reply_markup=kb)

    elif data == "admin_check_pts" and user_id == ADMIN_ID:
        await query.answer()
        context.user_data['admin_action'] = 'check_user_pts'
        await query.message.reply_text("🔍 أدخل آيدي المستخدم لمعرفة نقاطه وحالته:")

    elif data == "admin_deduct_pts" and user_id == ADMIN_ID:
        await query.answer()
        context.user_data['admin_action'] = 'deduct_user_pts'
        await query.message.reply_text("➖ أدخل الآيدي وعدد النقاط المراد خصمها بالشكل:\nID|Points")

    elif data == "admin_toggle_maint" and user_id == ADMIN_ID:
        curr_maint = get_setting("maintenance_mode")
        new_maint = 1 if curr_maint == 0 else 0
        set_setting("maintenance_mode", new_maint)
        m_str = "تم تفعيل وضع الصيانة 🛠️" if new_maint == 1 else "تم إيقاف وضع الصيانة 🟢"
        await query.answer(m_str, show_alert=True)
        await query.message.reply_text(f"⚙️ تحديث الوضع: {m_str}")

    elif data == "admin_manage_channels" and user_id == ADMIN_ID:
        await query.answer()
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("➕ إضافة قناة رسمية ثابتة", callback_data="admin_add_fixed_ch")],
            [InlineKeyboardButton("🗑️ حذف قناة رسمية ثابتة", callback_data="admin_del_fixed_ch_menu")],
            [InlineKeyboardButton("⭐ إضافة تمويل / قناة ممولة", callback_data="admin_add_funding")],
            [InlineKeyboardButton("🗑️ حذف قناة ممولة", callback_data="admin_delete_funding_list")],
            [InlineKeyboardButton("⬅️ العودة للوحة الأدمن", callback_data="admin_panel")]
        ])
        await query.message.reply_text("📢 إدارة القنوات الإجبارية:", reply_markup=kb)

    elif data == "admin_add_fixed_ch" and user_id == ADMIN_ID:
        await query.answer()
        context.user_data['admin_action'] = 'add_fixed_ch'
        await query.message.reply_text("➕ أرسل معرف أو رابط القناة الرسمية المراد إضافتها:")

    elif data == "admin_del_fixed_ch_menu" and user_id == ADMIN_ID:
        await query.answer()
        fixed_ch = get_fixed_channels()
        if not fixed_ch:
            await query.message.reply_text("❌ لا توجد قنوات رسمية مضافة!")
            return
        
        buttons = []
        for ch_id, target in fixed_ch:
            buttons.append([InlineKeyboardButton(f"❌ حذف: {target}", callback_data=f"del_fixed_ch_{ch_id}")])
        buttons.append([InlineKeyboardButton("⬅️ العودة", callback_data="admin_manage_channels")])
        
        await query.message.reply_text("🗑️ اختر القناة المراد حذفها:", reply_markup=InlineKeyboardMarkup(buttons))

    elif data.startswith("del_fixed_ch_") and user_id == ADMIN_ID:
        ch_id = int(data.split("_")[3])
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM fixed_channels WHERE id = %s", (ch_id,))
        conn.commit()
        cursor.close()
        conn.close()
        await query.answer("✅ تم حذف القناة الرسمية بنجاح!", show_alert=True)
        await query.message.edit_text("✅ تم حذف القناة من الاشتراك الإجباري.")

    elif data == "admin_set_star_prices" and user_id == ADMIN_ID:
        await query.answer()
        context.user_data['admin_action'] = 'set_star_prices'
        p15 = get_setting("price_star_15")
        p25 = get_setting("price_star_25")
        
        msg = (
            "🏷️ تعديل أسعار النجوم:\n\n"
            f"• 15 نجمة = {p15} نقطة\n"
            f"• 25 نجمة = {p25} نقطة\n\n"
            "أرسل الأسعار بالشكل:\nسعر 15 نجمة|سعر 25 نجمة"
        )
        await query.message.reply_text(msg)

    elif data == "admin_view_users" and user_id == ADMIN_ID:
        await query.answer()
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT user_id, first_name, username, points, is_banned FROM users ORDER BY user_id ASC")
        users_list = cursor.fetchall()
        cursor.close()
        conn.close()

        if not users_list:
            await query.message.reply_text("❌ لا يوجد مستخدمين مسجلين حالياً.")
            return

        total = len(users_list)
        msg_chunk = f"👥 إجمالي المستخدمين المسجلين الكلي ({total}):\n\n"
        
        for idx, u in enumerate(users_list, 1):
            u_id, fname, uname, pts, banned = u
            status = "🚫" if banned == 1 else "✅"
            uname_txt = uname if uname else "بدون معرف"
            line = f"{idx}. {fname} ({uname_txt}) | {u_id} | 🪙 {pts} | {status}\n"
            
            if len(msg_chunk) + len(line) > 3800:
                await query.message.reply_text(msg_chunk)
                msg_chunk = ""

            msg_chunk += line

        if msg_chunk:
            await query.message.reply_text(msg_chunk)

    elif data == "admin_delete_funding_list" and user_id == ADMIN_ID:
        await query.answer()
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, target, target_count, current_count FROM dynamic_forced_channels")
        funded_channels = cursor.fetchall()
        cursor.close()
        conn.close()

        if not funded_channels:
            await query.message.reply_text("❌ لا توجد أي قنوات ممولة نشطة!")
            return

        buttons = []
        for ch in funded_channels:
            ch_id, target, target_count, current_count = ch
            btn_text = f"❌ حذف: {target} ({current_count}/{target_count})"
            buttons.append([InlineKeyboardButton(btn_text, callback_data=f"del_funding_{ch_id}")])

        kb = InlineKeyboardMarkup(buttons)
        await query.message.reply_text("🗑️ اضغط على أي قناة ممولة بالأسفل لإلغائها وحذفها:", reply_markup=kb)

    elif data.startswith("del_funding_") and user_id == ADMIN_ID:
        ch_id = int(data.split("_")[2])
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM dynamic_forced_channels WHERE id = %s", (ch_id,))
        cursor.execute("DELETE FROM user_forced_joins WHERE channel_id = %s", (ch_id,))
        conn.commit()
        cursor.close()
        conn.close()

        await query.answer("✅ تم حذف القناة الممولة!", show_alert=True)
        await query.message.edit_text("✅ تم إلغاء القناة الممولة وحذفها بنجاح.")

    elif data == "admin_create_point_link" and user_id == ADMIN_ID:
        await query.answer()
        context.user_data['admin_action'] = 'create_point_link'
        msg = "🔗 إنشاء رابط نقاط (للأدمن):\n\nأرسل البيانات بالصيغة:\nعدد النقاط|عدد الأشخاص"
        await query.message.reply_text(msg)

    elif data == "admin_add_funding" and user_id == ADMIN_ID:
        await query.answer()
        context.user_data['admin_action'] = 'add_funding'
        msg = "📢 إضافة قناة ممولة:\n\nأرسل البيانات بالشكل:\nالمعرف أو الرابط|عدد الاعضاء المطلوبة"
        await query.message.reply_text(msg)

    elif data == "admin_toggle_store" and user_id == ADMIN_ID:
        curr_status = get_setting("store_disabled")
        new_status = 1 if curr_status == 0 else 0
        set_setting("store_disabled", new_status)
        state_str = "تم إيقاف الشراء من المتجر 🔴" if new_status == 1 else "تم تفعيل الشراء في المتجر 🟢"
        await query.answer(state_str, show_alert=True)
        await query.message.reply_text(f"⚙️ تحديث المتجر: {state_str}")

    elif data == "admin_give_pts_menu" and user_id == ADMIN_ID:
        await query.answer()
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🌐 للجميع", callback_data="admin_give_pts_all")],
            [InlineKeyboardButton("👤 لمستخدم معين", callback_data="admin_give_pts_user")]
        ])
        await query.message.reply_text("🎁 حدد نوع توزيع النقاط:", reply_markup=kb)

    elif data == "admin_give_pts_all" and user_id == ADMIN_ID:
        await query.answer()
        context.user_data['admin_action'] = 'give_points_all'
        await query.message.reply_text("🎁 أدخل عدد النقاط لتوزيعها على الجميع:")

    elif data == "admin_give_pts_user" and user_id == ADMIN_ID:
        await query.answer()
        context.user_data['admin_action'] = 'give_points_user'
        await query.message.reply_text("👤 أدخل الآيدي وعدد النقاط بالشكل:\nID|Points")

    elif data == "admin_create_code" and user_id == ADMIN_ID:
        await query.answer()
        context.user_data['admin_action'] = 'create_gift_code'
        await query.message.reply_text("🎫 أرسل بيانات الكود بالشكل:\nعدد النقاط|عدد مرات الاستخدام")

    elif data == "admin_broadcast" and user_id == ADMIN_ID:
        await query.answer()
        context.user_data['admin_action'] = 'broadcast'
        await query.message.reply_text("📢 أرسل نص الإذاعة:")

    elif data == "admin_ban_menu" and user_id == ADMIN_ID:
        await query.answer()
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🚫 حظر مستخدم", callback_data="admin_ban")],
            [InlineKeyboardButton("✅ فك حظر مستخدم", callback_data="admin_unban")]
        ])
        await query.message.reply_text("🚫 قسم إدارة الحظر:", reply_markup=kb)

    elif data == "admin_ban" and user_id == ADMIN_ID:
        await query.answer()
        context.user_data['admin_action'] = 'ban_user'
        await query.message.reply_text("🚫 أدخل آيدي المستخدم المراد حظره:")

    elif data == "admin_unban" and user_id == ADMIN_ID:
        await query.answer()
        context.user_data['admin_action'] = 'unban_user'
        await query.message.reply_text("✅ أدخل آيدي المستخدم المراد فك حظره:")

    elif data == "admin_discount" and user_id == ADMIN_ID:
        await query.answer()
        context.user_data['admin_action'] = 'set_discount'
        await query.message.reply_text("🏷️ أدخل نسبة التخفيض (مثال: 20 لـ 20%):")

    elif data == "admin_stats" and user_id == ADMIN_ID:
        await query.answer()
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) FROM users")
        total_users = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM users WHERE captcha_verified = 1")
        verified_users = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM users WHERE is_banned = 1")
        banned_users = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM dynamic_forced_channels")
        total_funded = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM redeem_codes")
        total_redeems = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM redeem_codes WHERE status = 'COMPLETED'")
        completed_redeems = cursor.fetchone()[0]

        cursor.close()
        conn.close()

        msg_stats = (
            "📊 إحصائيات البوت الشاملة والدقيقة:\n\n"
            f"👥 إجمالي المستخدمين المسجلين الكلي: {total_users}\n"
            f"✅ المستخدمين النشطين (مؤكدين): {verified_users}\n"
            f"🚫 المستخدمين المحظورين: {banned_users}\n\n"
            f"📢 إجمالي القنوات الممولة: {total_funded}\n"
            f"⭐ إجمالي طلبات النجوم: {total_redeems}\n"
            f"🎉 طلبات تم تسليمها بنجاح: {completed_redeems}"
        )
        await query.message.reply_text(msg_stats)

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_user or not update.message:
        return
    user = update.effective_user
    user_id = user.id
    username_str = f"@{user.username}" if user.username else "بدون معرف"
    raw_text = update.message.text.strip()
    text = convert_arabic_digits(raw_text)

    if get_setting("maintenance_mode") == 1 and user_id != ADMIN_ID:
        await update.message.reply_text("🛠️ البوت حالياً في وضع الصيانة!")
        return

    if not await check_subscription(user_id, context):
        msg_sub = f"⚠️ عذراً {user.first_name}!\n\nيرجى الانضمام للقنوات الإجبارية أولاً:"
        kb = await get_sub_keyboard(context)
        await update.message.reply_text(msg_sub, reply_markup=kb)
        return

    u_data = get_user(user_id, user.first_name)

    if not u_data['captcha_verified'] and user_id != ADMIN_ID:
        expected = context.user_data.get('captcha_answer')

        if expected is not None and text.isdigit() and int(text) == expected:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("UPDATE users SET captcha_verified = 1 WHERE user_id = %s", (user_id,))
            conn.commit()

            cursor.execute("SELECT COALESCE(referred_by,0), COALESCE(ref_rewarded,0) FROM users WHERE user_id = %s", (user_id,))
            ref_row = cursor.fetchone()
            
            if ref_row and int(ref_row[0] or 0) > 0 and int(ref_row[1] or 0) == 0:
                ref_id = ref_row[0]
                reward_points = get_setting("referral_reward_points")
                cursor.execute("UPDATE users SET points = COALESCE(points,0) + %s, referrals = COALESCE(referrals,0) + 1 WHERE user_id = %s", (reward_points, ref_id))
                cursor.execute("UPDATE users SET ref_rewarded = 1 WHERE user_id = %s", (user_id,))
                conn.commit()

                ref_notify_msg = (
                    f"🎉 إشعار إحالة جديدة واستلام نقاط!\n\n"
                    f"قام المستخدم {user.first_name} ({username_str}) بالانضمام وتأكيد حسابه عبر رابطك! ✨\n\n"
                    f"💰 المكافأة: تم إضافة +{reward_points} نقطة إلى حسابك!"
                )
                try:
                    await context.bot.send_message(chat_id=ref_id, text=ref_notify_msg)
                except Exception:
                    pass

            cursor.close()
            conn.close()
            context.user_data['captcha_answer'] = None

            await update.message.reply_text("✅ إجابة صحيحة! تم تأكيد حسابك بنجاح.")
            
            msg = (
                f"🚀 مرحباً بك في بوت الخدمات والنجوم 🌟\n\n"
                f"👤 المستخدم: {user.first_name}\n"
                f"🪙 رصيدك: {u_data['points']} نقطة\n\n"
                "اختر ما تحب من الأزرار أدناه 👇"
            )
            await update.message.reply_text(msg, reply_markup=get_main_keyboard(user_id))
            return
        else:
            captcha_msg = send_captcha(context, user_id)
            await update.message.reply_text(f"❌ إجابة خاطئة! حاول مجدداً:\n\n{captcha_msg}")
            return

    user_action = context.user_data.get('user_action')
    if user_action:
        if user_action in ('transfer_by_id', 'create_transfer_link') and get_setting("transfer_disabled") == 1 and user_id != ADMIN_ID:
            context.user_data['user_action'] = None
            await update.message.reply_text("⛔ تحويل النقاط متوقف حالياً من قبل الإدارة.")
            return

        if user_action == 'transfer_by_id':
            try:
                parts = [p.strip() for p in raw_text.split('|')]
                if len(parts) != 2:
                    raise ValueError()

                target_id = int(convert_arabic_digits(parts[0]))
                raw_amount = int(convert_arabic_digits(parts[1]))

                if target_id == user_id:
                    await update.message.reply_text("❌ لا يمكنك تحويل النقاط لنفسك!")
                    return

                if raw_amount <= 0:
                    await update.message.reply_text("❌ المبلغ يجب أن يكون أكبر من 0!")
                    return

                if u_data['points'] < raw_amount:
                    await update.message.reply_text(f"❌ رصيدك غير كافي! رصيدك: {u_data['points']} نقطة.")
                    return

                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute("SELECT first_name FROM users WHERE user_id = %s", (target_id,))
                target_user = cursor.fetchone()
                cursor.close()
                conn.close()

                if not target_user:
                    await update.message.reply_text("❌ المستخدم المستلم غير مسجل في البوت!")
                    return

                fee = math.ceil(raw_amount * 0.10)
                net_amount = raw_amount - fee

                update_points(user_id, -raw_amount)
                update_points(target_id, net_amount)

                context.user_data['user_action'] = None

                await update.message.reply_text(
                    f"✅ تم تحويل النقاط بنجاح!\n\n"
                    f"👤 المستلم: {target_id}\n"
                    f"🪙 المبلغ المخصوم: {raw_amount} نقطة\n"
                    f"📉 العمولة المستقطعة: {fee} نقطة (10%)\n"
                    f"🎁 الصافي للمستلم: {net_amount} نقطة"
                )

                try:
                    tr_recv_msg = (
                        f"🔔 إشعار استلام نقاط!\n\n"
                        f"قام المستخدم {user.first_name} ({username_str}) بتحويل {net_amount} نقطة إلى حسابك بنجاح! ✨"
                    )
                    await context.bot.send_message(chat_id=target_id, text=tr_recv_msg)
                except Exception:
                    pass

                return
            except Exception:
                await update.message.reply_text("❌ صيغة خاطئة! أرسل بالشكل:\nالآيدي|عدد النقاط")
                return

        elif user_action == 'use_gift_code':
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT 1 FROM gift_code_uses WHERE code = %s AND user_id = %s", (raw_text, user_id))
            already_used = cursor.fetchone()

            if already_used:
                await update.message.reply_text("❌ لقد استخدمت هذا الكود سابقاً!")
                cursor.close()
                conn.close()
                context.user_data['user_action'] = None
                return

            cursor.execute("SELECT points, uses_left FROM gift_codes WHERE code = %s", (raw_text,))
            code_data = cursor.fetchone()

            if not code_data:
                await update.message.reply_text("❌ كود غير صالح أو غير موجود!")
            elif code_data[1] <= 0:
                await update.message.reply_text("❌ انتهت عدد مرات استخدام هذا الكود!")
            else:
                pts = code_data[0]
                cursor.execute("UPDATE gift_codes SET uses_left = uses_left - 1 WHERE code = %s", (raw_text,))
                cursor.execute("INSERT INTO gift_code_uses (code, user_id) VALUES (%s, %s)", (raw_text, user_id))
                conn.commit()
                update_points(user_id, pts)
                
                await update.message.reply_text(f"🎉 تم استخدام الكود بنجاح! تم إضافة +{pts} نقطة إلى رصيدك.")

                admin_notice = (
                    f"🎁 إشعار استخدام كود نقاط!\n\n"
                    f"👤 المستخدم: {user.first_name} ({username_str})\n"
                    f"🆔 الآيدي: {user.id}\n"
                    f"🎫 الكود المستعمل: {raw_text}\n"
                    f"🪙 النقاط المضافة: {pts} نقطة"
                )
                try:
                    await context.bot.send_message(chat_id=ADMIN_ID, text=admin_notice)
                except Exception:
                    pass

            cursor.close()
            conn.close()
            context.user_data['user_action'] = None
            return

        elif user_action == 'create_transfer_link':
            if not text.isdigit():
                await update.message.reply_text("❌ يرجى إرسال رقم صحيح بالنقاط!")
                return

            raw_amount = int(text)
            if raw_amount <= 0 or u_data['points'] < raw_amount:
                await update.message.reply_text(f"❌ رصيدك غير كافي أو المبلغ غير صالح! رصيدك: {u_data['points']} نقطة.")
                return

            fee = math.ceil(raw_amount * 0.10)
            net_amount = raw_amount - fee

            update_points(user_id, -raw_amount)

            link_id = "link_tr_" + generate_code("")
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("INSERT INTO point_links (link_id, points, max_uses, creator_id) VALUES (%s, %s, 1, %s)", (link_id, net_amount, user_id))
            conn.commit()
            cursor.close()
            conn.close()

            bot_username = (await context.bot.get_me()).username
            transfer_link = f"https://t.me/{bot_username}?start={link_id}"

            context.user_data['user_action'] = None

            msg_res = (
                f"✅ تم إنشاء رابط تحويل النقاط بنجاح!\n\n"
                f"🪙 المبلغ المخصوم: {raw_amount} نقطة\n"
                f"📉 العمولة: {fee} نقطة (10%)\n"
                f"🎁 الصافي للمستلم: {net_amount} نقطة\n\n"
                f"🔗 رابط التحويل الحصري:\n{transfer_link}"
            )
            await update.message.reply_text(msg_res)
            return

    admin_action = context.user_data.get('admin_action')
    if user_id != ADMIN_ID or not admin_action:
        return

    elif admin_action == 'set_ref_reward':
        if text.isdigit():
            new_val = int(text)
            set_setting("referral_reward_points", new_val)
            context.user_data['admin_action'] = None
            await update.message.reply_text(f"👥 تم تحديث مكافأة الإحالة بنجاح إلى {new_val} نقطة!")

    elif admin_action == 'check_user_pts':
        if text.isdigit():
            target_id = int(text)
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT first_name, username, points, referrals, is_banned FROM users WHERE user_id = %s", (target_id,))
            target_data = cursor.fetchone()
            cursor.close()
            conn.close()

            if not target_data:
                await update.message.reply_text("❌ هذا المستخدم غير مسجل بالبوت!")
            else:
                fname, uname, pts, refs, banned = target_data
                b_str = "محظور 🚫" if banned == 1 else "نشط 🟢"
                await update.message.reply_text(
                    f"🔍 بيانات المستخدم {target_id}:\n\n"
                    f"👤 الاسم: {fname}\n"
                    f"🔹 المعرف: {uname}\n"
                    f"🪙 النقاط: {pts} نقطة\n"
                    f"👥 الدعوات: {refs} شخص\n"
                    f"🚦 الحالة: {b_str}"
                )
            context.user_data['admin_action'] = None

    elif admin_action == 'deduct_user_pts':
        try:
            parts = [p.strip() for p in raw_text.split('|')]
            target_id, pts = int(convert_arabic_digits(parts[0])), int(convert_arabic_digits(parts[1]))
            update_points(target_id, -pts)
            context.user_data['admin_action'] = None
            await update.message.reply_text(f"➖ تم خصم {pts} نقطة من المستخدم {target_id} بنجاح!")
        except Exception:
            await update.message.reply_text("❌ صيغة خاطئة! أرسل بالشكل:\nID|Points")

    elif admin_action == 'add_fixed_ch':
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("INSERT INTO fixed_channels (target) VALUES (%s)", (raw_text,))
            conn.commit()
            await update.message.reply_text(f"✅ تمت إضافة القناة الرسمية بنجاح: {raw_text}")
        except Exception:
            await update.message.reply_text("❌ القناة مضافة بالفعل سابقاً!")
        cursor.close()
        conn.close()
        context.user_data['admin_action'] = None

    elif admin_action == 'view_referrals':
        try:
            referrer_id = int(convert_arabic_digits(raw_text.strip()))
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute(
                "SELECT user_id, first_name, username, points, captcha_verified, ref_rewarded FROM users WHERE referred_by = %s ORDER BY user_id DESC",
                (referrer_id,)
            )
            rows = cursor.fetchall()
            cursor.close()
            conn.close()
            context.user_data['admin_action'] = None
            if not rows:
                await update.message.reply_text(f"📋 لا توجد إحالات مسجلة للآيدي {referrer_id}.")
                return
            header = f"📋 تفاصيل إحالات المستخدم\n\n🆔 صاحب الإحالة: {referrer_id}\n👥 عدد الإحالات: {len(rows)}\n\n"
            chunks = []
            current = header
            for i, row in enumerate(rows, 1):
                uid, first_name, username, points, captcha_verified, ref_rewarded = row
                name = first_name or 'بدون اسم'
                uname = f"@{username}" if username else 'بدون معرف'
                status = '✅ فعل الحساب' if int(captcha_verified or 0) else '⏳ لم يفعل الحساب'
                reward = '💰 المكافأة صُرفت' if int(ref_rewarded or 0) else '⌛ المكافأة لم تُصرف'
                line = (
                    f"{i}) 👤 {name}\n"
                    f"   🆔 {uid} | {uname}\n"
                    f"   🪙 النقاط: {int(points or 0)}\n"
                    f"   📌 الحالة: {status}\n"
                    f"   {reward}\n\n"
                )

                if len(current) + len(line) > 3800:
                    chunks.append(current)
                    current = line
                else:
                    current += line
            if current:
                chunks.append(current)
            for chunk in chunks:
                await update.message.reply_text(chunk)
            return
        except Exception:
            context.user_data['admin_action'] = None
            await update.message.reply_text("❌ أرسل آيدي صحيحاً لمعرفة إحالاته.")
            return

    elif admin_action == 'set_star_prices':
        try:
            parts = [p.strip() for p in raw_text.split('|')]
            p15, p25 = int(convert_arabic_digits(parts[0])), int(convert_arabic_digits(parts[1]))
            set_setting("price_star_15", p15)
            set_setting("price_star_25", p25)
            context.user_data['admin_action'] = None
            await update.message.reply_text(f"🏷️ تم تحديث أسعار النجوم:\n• 15 نجمة: {p15}\n• 25 نجمة: {p25}")
        except Exception:
            await update.message.reply_text("❌ صيغة خاطئة! أرسل بالشكل:\nسعر 15 نجمة|سعر 25 نجمة")

    elif admin_action == 'create_point_link':
        try:
            parts = [p.strip() for p in raw_text.split('|')]
            if len(parts) != 2:
                raise ValueError()

            pts = int(convert_arabic_digits(parts[0]))
            uses = int(convert_arabic_digits(parts[1]))

            link_id = "link_" + generate_code("")
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("INSERT INTO point_links (link_id, points, max_uses, creator_id) VALUES (%s, %s, %s, %s)", (link_id, pts, uses, ADMIN_ID))
            conn.commit()
            cursor.close()
            conn.close()

            bot_username = (await context.bot.get_me()).username
            full_link = f"https://t.me/{bot_username}?start={link_id}"
            context.user_data['admin_action'] = None
            await update.message.reply_text(f"🎉 تم إنشاء رابط النقاط بنجاح!\n\n🪙 النقاط: {pts} | 👥 الأشخاص: {uses}\n🔗 الرابط:\n{full_link}")
        except Exception:
            await update.message.reply_text("❌ صيغة خاطئة! استخدم:\nعدد النقاط|عدد الأشخاص")

    elif admin_action == 'add_funding':
        try:
            parts = [p.strip() for p in raw_text.split('|')]
            target, target_count = parts[0], int(convert_arabic_digits(parts[1]))
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("INSERT INTO dynamic_forced_channels (target, target_count) VALUES (%s, %s)", (target, target_count))
            conn.commit()
            cursor.close()
            conn.close()
            context.user_data['admin_action'] = None
            await update.message.reply_text(f"📢 تمت إضافة القناة الممولة بنجاح!\n🔗 القناة: {target} | 👥 العدد: {target_count}")
        except Exception:
            await update.message.reply_text("❌ صيغة خاطئة! أرسل بالشكل:\nالمعرف أو الرابط|عدد الاعضاء المطلوبة")

    elif admin_action == 'create_gift_code':
        try:
            parts = [p.strip() for p in raw_text.split('|')]
            pts, uses = int(convert_arabic_digits(parts[0])), int(convert_arabic_digits(parts[1]))
            code = generate_code("GIFT-")
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("INSERT INTO gift_codes (code, points, uses_left) VALUES (%s, %s, %s)", (code, pts, uses))
            conn.commit()
            cursor.close()
            conn.close()

            bot_username = (await context.bot.get_me()).username
            context.user_data['admin_action'] = None
            
            channel_msg = (
                f"🎫 كود نقاط مجاني جديد!\n\n"
                f"🔑 الكود: {code}\n"
                f"🪙 النقاط: {pts} نقطة\n"
                f"👥 الاستخدامات: {uses} شخص\n\n"
                f"🤖 استخدم الكود داخل البوت:\nhttps://t.me/{bot_username}"
            )
            try:
                await context.bot.send_message(chat_id=OFFICIAL_CHANNEL, text=channel_msg)
            except Exception:
                pass

            await update.message.reply_text(f"🎫 تم إنشاء الكود ونشره بالقناة الرسمية!\n🔑 الكود: {code}")
        except Exception:
            await update.message.reply_text("❌ صيغة خاطئة! استخدم:\nعدد النقاط|عدد مرات الاستخدام")

    elif admin_action == 'broadcast':
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT user_id FROM users WHERE is_banned = 0")
        users = cursor.fetchall()
        cursor.close()
        conn.close()

        count = 0
        await update.message.reply_text("🔄 جاري إرسال الإذاعة...")
        for u in users:
            try:
                await context.bot.send_message(chat_id=u[0], text=raw_text)
                count += 1
                await asyncio.sleep(0.03)
            except Exception:
                pass

        context.user_data['admin_action'] = None
        await update.message.reply_text(f"✅ تمت الإذاعة لـ {count} مستخدم.")

    elif admin_action == 'give_points_all':
        if text.isdigit():
            pts = int(text)
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("UPDATE users SET points = points + %s", (pts,))
            conn.commit()
            cursor.close()
            conn.close()
            context.user_data['admin_action'] = None
            await update.message.reply_text(f"🎁 تم إضافة +{pts} نقطة لجميع المستخدمين بنجاح وتحديث أرصدتهم!")

    elif admin_action == 'give_points_user':
        try:
            parts = [p.strip() for p in raw_text.split('|')]
            target_id, pts = int(convert_arabic_digits(parts[0])), int(convert_arabic_digits(parts[1]))
            update_points(target_id, pts)
            context.user_data['admin_action'] = None
            
            try:
                await context.bot.send_message(chat_id=target_id, text=f"🎁 مبروك! أضاف لك المطور رصيداً جديداً قدره `+{pts}` نقطة في حسابك! ✨")
            except Exception:
                pass

            await update.message.reply_text(f"✅ تم إضافة +{pts} نقطة للمستخدم {target_id} بنجاح وتم إشعاره!")
        except Exception:
            await update.message.reply_text("❌ صيغة خاطئة! أرسل بالشكل:\nID|Points")

    elif admin_action == 'ban_user':
        if text.isdigit():
            target_id = int(text)
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("UPDATE users SET is_banned = 1 WHERE user_id = %s", (target_id,))
            conn.commit()
            cursor.close()
            conn.close()
            context.user_data['admin_action'] = None
            await update.message.reply_text(f"🚫 تم حظر المستخدم {target_id} بنجاح!")

    elif admin_action == 'unban_user':
        if text.isdigit():
            target_id = int(text)
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("UPDATE users SET is_banned = 0 WHERE user_id = %s", (target_id,))
            conn.commit()
            cursor.close()
            conn.close()
            context.user_data['admin_action'] = None
            await update.message.reply_text(f"✅ تم فك حظر المستخدم {target_id} بنجاح!")

    elif admin_action == 'set_discount':
        if text.isdigit():
            val = int(text)
            if 0 <= val <= 100:
                set_setting("discount", val)
                context.user_data['admin_action'] = None
                await update.message.reply_text(f"🏷️ تم ضبط التخفيض إلى {val}%!")

def main():
    if not TOKEN:
        raise RuntimeError("BOT_TOKEN environment variable is missing")

    init_db()

    app = ApplicationBuilder().token(TOKEN).concurrent_updates(True).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(callback_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    print("🚀 البوت يعمل بنجاح...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
