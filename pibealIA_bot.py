import os
import requests
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, CommandHandler, ContextTypes, filters
from groq import Groq

# =========================
# VARIABLES
# =========================

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
HF_TOKEN = os.getenv("HF_TOKEN")  # Hugging Face API token

# =========================
# CLIENTE IA
# =========================

client = Groq(api_key=GROQ_API_KEY)

# Memoria simple por usuario
memoria = {}

# =========================
# FUNCIONES IA
# =========================

def preguntar_ia(user_id, mensaje):
    if user_id not in memoria:
        memoria[user_id] = []

    memoria[user_id].append({"role": "user", "content": mensaje})

    respuesta = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=memoria[user_id]
    )

    texto = respuesta.choices[0].message.content
    memoria[user_id].append({"role": "assistant", "content": texto})
    return texto

# =========================
# FUNCIONES IMAGEN / VIDEO
# =========================

def generar_imagen(prompt):
    """
    Genera imagen usando Hugging Face API.
    """
    url = "https://api-inference.huggingface.co/models/hogiahien/counterfeit-v30-edited"
    headers = {"Authorization": f"Bearer {HF_TOKEN}"}
    data = {"inputs": prompt}
    response = requests.post(url, headers=headers, json=data)
    if response.status_code == 200:
        imagen_bytes = response.content
        archivo = "imagen.png"
        with open(archivo, "wb") as f:
            f.write(imagen_bytes)
        return archivo
    else:
        return None

def generar_video(prompt):
    """
    Genera video simple (placeholder) usando Hugging Face text-to-video API.
    Puedes cambiar el modelo por uno disponible en HF.
    """
    url = "https://api-inference.huggingface.co/models/hogiahien/video-diffusion"
    headers = {"Authorization": f"Bearer {HF_TOKEN}"}
    data = {"inputs": prompt}
    response = requests.post(url, headers=headers, json=data)
    if response.status_code == 200:
        video_bytes = response.content
        archivo = "video.mp4"
        with open(archivo, "wb") as f:
            f.write(video_bytes)
        return archivo
    else:
        return None

# =========================
# TELEGRAM
# =========================

async def responder(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    mensaje = update.message.text

    await update.message.chat.send_action("typing")

    # Comandos especiales
    if mensaje.startswith("/imagen"):
        prompt = mensaje.replace("/imagen ", "")
        archivo = generar_imagen(prompt)
        if archivo:
            await update.message.reply_photo(photo=open(archivo, "rb"))
        else:
            await update.message.reply_text("❌ Error generando la imagen.")
        return

    if mensaje.startswith("/video"):
        prompt = mensaje.replace("/video ", "")
        archivo = generar_video(prompt)
        if archivo:
            await update.message.reply_video(video=open(archivo, "rb"))
        else:
            await update.message.reply_text("❌ Error generando el video.")
        return

    # Respuesta IA normal
    respuesta = preguntar_ia(user_id, mensaje)
    await update.message.reply_text(respuesta)

# =========================
# INICIAR BOT
# =========================

if __name__ == "__main__":
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, responder))

    print("🤖 BOT IA + Imagen/Video ACTIVO")
    app.run_polling(drop_pending_updates=True, timeout=30)




