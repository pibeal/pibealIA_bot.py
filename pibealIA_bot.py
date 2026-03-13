import os
import requests
from fastapi import FastAPI, Request
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, filters

# =========================
# VARIABLES DE ENTORNO
# =========================

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")

# =========================
# IA GROQ
# =========================

def preguntar_ia(pregunta):

    url = "https://api.groq.com/openai/v1/chat/completions"

    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }

    data = {
        "model": "llama-3.1-70b-versatile",
        "messages": [
            {
                "role": "system",
                "content": "Eres una IA llamada Pibeal IA. Ayudas con programación, tecnología, preguntas generales y conversación."
            },
            {
                "role": "user",
                "content": pregunta
            }
        ]
    }

    try:

        r = requests.post(url, headers=headers, json=data, timeout=30)
        js = r.json()

        return js["choices"][0]["message"]["content"]

    except Exception as e:

        print("ERROR IA:", e)
        return "⚠️ La IA tuvo un problema temporal."

# =========================
# MENSAJE TELEGRAM
# =========================

async def responder(update: Update, context: ContextTypes.DEFAULT_TYPE):

    texto = update.message.text.lower()

    if texto in ["hola", "buenas", "hey", "inicio", "start"]:

        mensaje = "👋 Hola, soy **Pibeal IA** 🤖\n\n¿En qué puedo ayudarte hoy?"

        await update.message.reply_text(mensaje)

        return

    respuesta = preguntar_ia(texto)

    await update.message.reply_text(respuesta)

# =========================
# BOT
# =========================

bot = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

bot.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, responder))

# =========================
# FASTAPI
# =========================

app = FastAPI()

@app.post("/webhook")
async def webhook(req: Request):

    data = await req.json()

    update = Update.de_json(data, bot.bot)

    await bot.process_update(update)

    return {"ok": True}

# =========================
# STARTUP
# =========================

@app.on_event("startup")
async def startup():

    await bot.initialize()
    await bot.start()

    await bot.bot.set_webhook(f"{WEBHOOK_URL}/webhook")


  

   






  




   







