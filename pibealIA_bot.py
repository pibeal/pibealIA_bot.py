import os
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, ContextTypes, filters
from groq import Groq

# =========================
# VARIABLES
# =========================

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# =========================
# CLIENTE IA
# =========================

client = Groq(api_key=GROQ_API_KEY)

# memoria simple
memoria = {}

# =========================
# IA
# =========================

def preguntar_ia(user_id, mensaje):

    if user_id not in memoria:
        memoria[user_id] = []

    memoria[user_id].append({"role": "user", "content": mensaje})

    respuesta = client.chat.completions.create(
        model="llama3-70b-8192",
        messages=memoria[user_id]
    )

    texto = respuesta.choices[0].message.content

    memoria[user_id].append({"role": "assistant", "content": texto})

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





