import os
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, ContextTypes, filters
from google import genai

# =========================
# VARIABLES
# =========================

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

# =========================
# CLIENTE GEMINI
# =========================

client = genai.Client(api_key=GOOGLE_API_KEY)

# memoria simple
memoria = {}

# =========================
# IA
# =========================

def preguntar_ia(user_id, mensaje):

    if user_id not in memoria:
        memoria[user_id] = []

    memoria[user_id].append(f"Usuario: {mensaje}")

    contexto = "\n".join(memoria[user_id][-10:])

    prompt = f"""
Eres un asistente inteligente dentro de Telegram.

Conversación:
{contexto}

Responde claro y útil.
"""

    respuesta = client.models.generate_content(
        model="gemini-2.0-flash",
        contents=prompt
    )

    texto = respuesta.text

    memoria[user_id].append(f"Bot: {texto}")

    return texto

# =========================
# TELEGRAM
# =========================

async def responder(update: Update, context: ContextTypes.DEFAULT_TYPE):

    user_id = update.message.from_user.id
    mensaje = update.message.text

    await update.message.chat.send_action("typing")

    respuesta = preguntar_ia(user_id, mensaje)

    await update.message.reply_text(respuesta)

# =========================
# INICIAR BOT
# =========================

app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, responder))

print("🤖 BOT IA ACTIVO")

app.run_polling(drop_pending_updates=True)



