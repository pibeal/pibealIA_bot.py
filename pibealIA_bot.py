import os
import requests
from flask import Flask, request

from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    ContextTypes,
    MessageHandler,
    CommandHandler,
    filters
)

# =========================
# VARIABLES
# =========================

TOKEN = os.getenv("TELEGRAM_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
NEWS_API_KEY = os.getenv("NEWS_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

WEBHOOK_URL = os.getenv("WEBHOOK_URL")

# =========================
# APP WEB
# =========================

flask_app = Flask(__name__)

# =========================
# IA
# =========================

memoria = {}

def ia_respuesta(user_id, texto):

    url = "https://api.groq.com/openai/v1/chat/completions"

    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }

    if user_id not in memoria:
        memoria[user_id] = []

    memoria[user_id].append({"role":"user","content":texto})

    data = {
        "model": "llama3-70b-8192",
        "messages": memoria[user_id][-6:]
    }

    r = requests.post(url, headers=headers, json=data)

    respuesta = r.json()["choices"][0]["message"]["content"]

    memoria[user_id].append({"role":"assistant","content":respuesta})

    return respuesta


# =========================
# NOTICIAS
# =========================

def noticias(query):

    url = f"https://newsapi.org/v2/everything?q={query}&language=es&pageSize=5&apiKey={NEWS_API_KEY}"

    r = requests.get(url)

    data = r.json()

    texto = ""

    for n in data["articles"][:5]:

        texto += f"📰 {n['title']}\n{n['url']}\n\n"

    return texto


# =========================
# START
# =========================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    await update.message.reply_text(
"""
🤖 BOT IA PRO ACTIVO

Puedes preguntarme cualquier cosa.

Ejemplos:

noticias tecnologia
noticias bitcoin
genera imagen robot futurista
explicame python

También puedes enviarme audio 🎤
"""
)


# =========================
# IMAGEN
# =========================

async def imagen(update, prompt):

    url = f"https://image.pollinations.ai/prompt/{prompt}"

    await update.message.reply_photo(url)


# =========================
# AUDIO
# =========================

async def audio(update: Update, context: ContextTypes.DEFAULT_TYPE):

    file = await update.message.voice.get_file()

    path = "audio.ogg"

    await file.download_to_drive(path)

    url = "https://api.openai.com/v1/audio/transcriptions"

    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}"
    }

    files = {"file": open(path,"rb")}
    data = {"model":"whisper-1"}

    r = requests.post(url, headers=headers, files=files, data=data)

    texto = r.json()["text"]

    respuesta = ia_respuesta(update.message.from_user.id, texto)

    await update.message.reply_text(respuesta)


# =========================
# CHAT
# =========================

async def chat(update: Update, context: ContextTypes.DEFAULT_TYPE):

    texto = update.message.text.lower()

    user_id = update.message.from_user.id

    if "noticia" in texto:

        tema = texto.replace("noticias","").replace("noticia","").strip()

        if tema == "":
            tema = "tecnologia"

        await update.message.reply_text(noticias(tema))

        return

    if "imagen" in texto or "genera" in texto:

        prompt = texto.replace("imagen","").replace("genera","").strip()

        await imagen(update,prompt)

        return

    respuesta = ia_respuesta(user_id, texto)

    await update.message.reply_text(respuesta)


# =========================
# TELEGRAM APP
# =========================

app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, chat))
app.add_handler(MessageHandler(filters.VOICE, audio))


# =========================
# WEBHOOK
# =========================

@flask_app.route("/", methods=["GET"])
def home():
    return "BOT ONLINE"


@flask_app.route("/webhook", methods=["POST"])
async def webhook():

    update = Update.de_json(request.get_json(force=True), app.bot)

    await app.process_update(update)

    return "ok"


# =========================
# MAIN
# =========================

if __name__ == "__main__":

    requests.get(f"https://api.telegram.org/bot{TOKEN}/deleteWebhook")

    requests.get(
        f"https://api.telegram.org/bot{TOKEN}/setWebhook?url={WEBHOOK_URL}/webhook"
    )

    flask_app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))



   







