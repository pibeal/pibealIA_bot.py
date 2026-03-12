import os
import google.generativeai as genai
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, ContextTypes, filters

# =========================
# CONFIGURACION
# =========================

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

genai.configure(api_key=GEMINI_API_KEY)

model = genai.GenerativeModel("gemini-1.5-flash")

# =========================
# MEMORIA DE CONVERSACION
# =========================

memoria = {}

# =========================
# FUNCION IA
# =========================

def preguntar_ia(user_id, mensaje):

    if user_id not in memoria:
        memoria[user_id] = []

    memoria[user_id].append(f"Usuario: {mensaje}")

    contexto = "\n".join(memoria[user_id][-10:])

    prompt = f"""
Eres un asistente inteligente dentro de Telegram.

Debes:
- responder preguntas
- ayudar con programación
- explicar conceptos
- resolver problemas

Conversación:
{contexto}

Responde de forma clara y útil.
"""

    respuesta = model.generate_content(prompt)

    texto = respuesta.text

    memoria[user_id].append(f"Bot: {texto}")

    return texto

# =========================
# MENSAJES
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

print("🤖 BOT IA INICIADO")

app.run_polling()
