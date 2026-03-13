import os
import requests
import time

from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    MessageHandler,
    CommandHandler,
    ContextTypes,
    filters
)

# =========================
# VARIABLES
# =========================

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
NEWS_API_KEY = os.getenv("NEWS_API_KEY")

memoria = {}

# =========================
# IA (Groq API directa)
# =========================

def responder_ia(user_id, mensaje):

    url = "https://api.groq.com/openai/v1/chat/completions"

    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }

    if user_id not in memoria:
        memoria[user_id] = []

    memoria[user_id].append({"role": "user", "content": mensaje})

    data = {
        "model": "llama3-70b-8192",
        "messages": memoria[user_id][-6:]
    }

    try:

        r = requests.post(url, headers=headers, json=data, timeout=30)

        if r.status_code != 200:
            return "⚠️ Error al consultar la IA."

        respuesta = r.json()

        texto = respuesta["choices"][0]["message"]["content"]

        memoria[user_id].append({"role": "assistant", "content": texto})

        return texto

    except Exception:
        return "⚠️ La IA está ocupada, intenta nuevamente."


# =========================
# NOTICIAS
# =========================

def obtener_noticias(query=""):

    if query == "":
        url = f"https://newsapi.org/v2/top-headlines?language=es&pageSize=5&apiKey={NEWS_API_KEY}"
    else:
        url = f"https://newsapi.org/v2/everything?q={query}&language=es&pageSize=5&apiKey={NEWS_API_KEY}"

    try:

        r = requests.get(url)

        data = r.json()

        if "articles" not in data:
            return "No pude obtener noticias."

        noticias = ""

        for n in data["articles"][:5]:

            noticias += f"📰 {n['title']}\n{n['url']}\n\n"

        return noticias

    except:
        return "Error obteniendo noticias."


# =========================
# START
# =========================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    texto = """
🤖 BOT IA ACTIVO

Puedes preguntarme cualquier cosa.

Ejemplos:

noticias tecnologia
noticias crypto
genera imagen robot futurista
explicame python

También puedes enviar 🎤 audio.
"""

    await update.message.reply_text(texto)


# =========================
# IMAGEN
# =========================

async def generar_imagen(update, prompt):

    url = f"https://image.pollinations.ai/prompt/{prompt}"

    await update.message.reply_photo(url)


# =========================
# AUDIO
# =========================

async def audio(update: Update, context: ContextTypes.DEFAULT_TYPE):

    file = await update.message.voice.get_file()

    ruta = "audio.ogg"

    await file.download_to_drive(ruta)

    url = "https://api.openai.com/v1/audio/transcriptions"

    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}"
    }

    files = {
        "file": open(ruta, "rb")
    }

    data = {
        "model": "whisper-1"
    }

    r = requests.post(url, headers=headers, files=files, data=data)

    texto = r.json()["text"]

    respuesta = responder_ia(update.message.from_user.id, texto)

    await update.message.reply_text(respuesta)


# =========================
# CHAT PRINCIPAL
# =========================

async def chat(update: Update, context: ContextTypes.DEFAULT_TYPE):

    user_id = update.message.from_user.id
    mensaje = update.message.text.lower()

    # NOTICIAS
    if "noticia" in mensaje or "news" in mensaje:

        tema = mensaje.replace("noticias", "").replace("noticia", "").replace("news", "").strip()

        noticias = obtener_noticias(tema)

        await update.message.reply_text(noticias)

        return

    # IMAGEN
    if "imagen" in mensaje:

        prompt = mensaje.replace("imagen", "").replace("genera", "").strip()

        await generar_imagen(update, prompt)

        return

    # IA NORMAL
    await update.message.reply_text("🤖 pensando...")

    respuesta = responder_ia(user_id, mensaje)

    await update.message.reply_text(respuesta)


# =========================
# MAIN
# =========================

if __name__ == "__main__":

    requests.get(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/deleteWebhook")

    time.sleep(5)

    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, chat))
    app.add_handler(MessageHandler(filters.VOICE, audio))

    print("BOT ONLINE")

    app.run_polling(
        allowed_updates=Update.ALL_TYPES,
        drop_pending_updates=True
    )


   









