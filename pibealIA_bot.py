import os
import requests
from groq import Groq

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

client = Groq(api_key=GROQ_API_KEY)

# =========================
# IA
# =========================

def responder_ia(mensaje):

    chat = client.chat.completions.create(
        model="llama3-70b-8192",
        messages=[
            {"role": "user", "content": mensaje}
        ]
    )

    return chat.choices[0].message.content


# =========================
# NOTICIAS
# =========================

def obtener_noticias(query=""):

    if query == "":
        url = f"https://newsapi.org/v2/top-headlines?language=es&pageSize=5&apiKey={NEWS_API_KEY}"
    else:
        url = f"https://newsapi.org/v2/everything?q={query}&language=es&pageSize=5&apiKey={NEWS_API_KEY}"

    r = requests.get(url)
    data = r.json()

    noticias = ""

    if "articles" not in data:
        return "No pude obtener noticias ahora."

    for n in data["articles"][:5]:

        titulo = n["title"]
        link = n["url"]

        noticias += f"📰 {titulo}\n{link}\n\n"

    return noticias


# =========================
# START
# =========================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    texto = """
🤖 BOT IA ACTIVO

Puedes preguntarme lo que quieras.

Ejemplos:

noticias tecnologia  
noticias crypto  
genera imagen de robot futurista  
explicame python  

También puedes mandar 🎤 audio.
"""

    await update.message.reply_text(texto)


# =========================
# IMAGEN
# =========================

async def imagen(update: Update, prompt):

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

    respuesta = responder_ia(texto)

    await update.message.reply_text(respuesta)


# =========================
# CHAT PRINCIPAL
# =========================

async def chat(update: Update, context: ContextTypes.DEFAULT_TYPE):

    mensaje = update.message.text.lower()

    # NOTICIAS
    if "noticia" in mensaje or "news" in mensaje:

        palabras = mensaje.replace("noticias", "").replace("noticia", "").replace("news", "").strip()

        noticias = obtener_noticias(palabras)

        await update.message.reply_text(noticias)

        return

    # IMAGEN
    if "imagen" in mensaje or "genera imagen" in mensaje:

        prompt = mensaje.replace("imagen", "").replace("genera imagen", "").strip()

        await imagen(update, prompt)

        return

    # IA NORMAL
    await update.message.reply_text("🤖 pensando...")

    respuesta = responder_ia(mensaje)

    await update.message.reply_text(respuesta)


# =========================
# MAIN
# =========================

if __name__ == "__main__":

    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start))

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, chat))
    app.add_handler(MessageHandler(filters.VOICE, audio))

    print("BOT ONLINE")

    app.run_polling()




   







