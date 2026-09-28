import os
import glob
import json
from telegram import Update
from telegram.ext import ContextTypes

# Configuración (debe coincidir con MasterBot.py)
OWNER_ID = 8535723817
VAULT_DIR = "vault"
SPOTIFY_DIR = "cookies_spotify"
AMAZON_DIR = "cookies_amazon"
YOUTUBE_DIR = "cookies_youtube"

async def guardar_cookie_telegram(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Guarda automáticamente las cookies subidas por el Owner en las carpetas correspondientes.
    Detecta el servicio por el nombre del archivo.
    """
    user_id = update.effective_user.id
    
    # Solo el Owner puede subir cookies
    if user_id != OWNER_ID:
        await update.message.reply_html("<code>[!] ACCESO DENEGADO: Solo el Owner puede subir cookies.</code>")
        return
    
    if not update.message.document:
        return
    
    doc = update.message.document
    filename = doc.file_name.lower()
    
    # Detectar servicio por nombre de archivo
    if "netflix" in filename or "vault" in filename:
        target_dir = VAULT_DIR
        service = "NETFLIX"
    elif "spotify" in filename or "sp_dc" in filename:
        target_dir = SPOTIFY_DIR
        service = "SPOTIFY"
    elif "amazon" in filename or "prime" in filename:
        target_dir = AMAZON_DIR
        service = "AMAZON"
    elif "youtube" in filename or "yt" in filename:
        target_dir = YOUTUBE_DIR
        service = "YOUTUBE"
    else:
        # Si no se detecta, guardar en vault por defecto
        target_dir = VAULT_DIR
        service = "DESCONOCIDO"
    
    # Crear carpeta si no existe
    os.makedirs(target_dir, exist_ok=True)
    
    # Descargar archivo
    file = await context.bot.get_file(doc.file_id)
    file_path = os.path.join(target_dir, doc.file_name)
    await file.download_to_drive(file_path)
    
    # Confirmar al Owner
    await update.message.reply_html(
        f"<code>[✔] COOKIE GUARDADA\n"
        f"[>] SERVICIO: {service}\n"
        f"[>] ARCHIVO: {doc.file_name}\n"
        f"[>] RUTA: {file_path}</code>"
    )
