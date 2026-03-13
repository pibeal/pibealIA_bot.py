import os
import requests
from groq import Groq
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
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
# IA GROQ
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
# START
# =========================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    texto = """
🤖 BOT IA ACTIVO

Comandos:

/imagen prompt
Ejemplo:
/imagen gato astronauta

También puedes:
🎤 mandar audio
💬 escribir preguntas
"""

    await update.message.reply_text(texto)


# =========================
# IA TEXTO
# =========================

async def chat(update: Update, context: ContextTypes.DEFAULT_TYPE):

    mensaje = update.message.text

    await update.message.reply_text("🤖 pensando...")

    respuesta = responder_ia(mensaje)

    await update.message.reply_text(respuesta)


# =========================
# GENERAR IMAGEN
# =========================

async def imagen(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if not context.args:
        await update.message.reply_text("Usa: /imagen descripcion")
        return

    prompt = " ".join(context.args)

    url = f"https://image.pollinations.ai/prompt/{prompt}"

    await update.message.reply_photo(url)


# =========================
# AUDIO → TEXTO
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
# MAIN
# =========================

if __name__ == "__main__":

    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("imagen", imagen))

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, chat))
    app.add_handler(MessageHandler(filters.VOICE, audio))

    print("BOT ONLINE")

    app.run_polling()



   






