import os
import requests
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, filters

# =========================
# VARIABLES DE ENTORNO
# =========================

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.1-70b-versatile")  # fallback automático

if not TELEGRAM_TOKEN or not GROQ_API_KEY or not WEBHOOK_URL:
    raise ValueError("⚠️ Asegúrate de definir TELEGRAM_TOKEN, GROQ_API_KEY y WEBHOOK_URL")

# =========================
# FUNCIÓN IA GROQ
# =========================

def preguntar_ia(pregunta: str) -> str:
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }
    data = {
        "model": GROQ_MODEL,
        "messages": [
            {"role": "system", "content": "Eres Pibeal IA, ayudas con programación, tecnología y conversación."},
            {"role": "user", "content": pregunta}
        ]
    }
    try:
        r = requests.post(url, headers=headers, json=data, timeout=60)
        r.raise_for_status()
        js = r.json()
        return js["choices"][0]["message"]["content"]
    except requests.exceptions.HTTPError as e:
        print("ERROR IA:", e, r.text)
        return f"⚠️ La IA tuvo un problema con la solicitud a Groq (modelo: {GROQ_MODEL})."
    except Exception as e:
        print("ERROR IA:", e)
        return "⚠️ La IA tuvo un problema temporal."

# =========================
# HANDLER TELEGRAM
# =========================

async def responder(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    texto = update.message.text.lower()

    if texto in ["hola", "buenas", "hey", "inicio", "start"]:
        await update.message.reply_text("👋 Hola, soy **Pibeal IA** 🤖\n\n¿En qué puedo ayudarte hoy?")
        return

    respuesta = preguntar_ia(texto)
    await update.message.reply_text(respuesta)

# =========================
# BOT TELEGRAM
# =========================

bot_app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
bot_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, responder))

# =========================
# FASTAPI CON LIFESPAN
# =========================

@asynccontextmanager
async def lifespan(app: FastAPI):
    # STARTUP
    await bot_app.initialize()
    await bot_app.bot.set_webhook(f"{WEBHOOK_URL}/webhook")
    print("✅ Webhook configurado en:", f"{WEBHOOK_URL}/webhook")
    yield
    # SHUTDOWN
    await bot_app.shutdown()
    await bot_app.stop()

app = FastAPI(lifespan=lifespan)

@app.post("/webhook")
async def webhook(req: Request):
    data = await req.json()
    update = Update.de_json(data, bot_app.bot)
    await bot_app.process_update(update)
    return {"ok": True}
  




   







