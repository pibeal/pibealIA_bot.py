import os
import base64
import requests
import imageio
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, ContextTypes, filters
from groq import Groq

# =========================
# VARIABLES
# =========================

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
HF_TOKEN = os.getenv("HF_TOKEN")  # Hugging Face API token gratuito

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
# FUNCIONES IMAGEN / GIF
# =========================

def generar_imagen(prompt):
    """
    Genera una imagen usando Hugging Face API gratuita (Stable Diffusion 2).
    """
    url = "https://api-inference.huggingface.co/models/stabilityai/stable-diffusion-2"
    headers = {"Authorization": f"Bearer {HF_TOKEN}"}
    data = {"inputs": prompt}

    response = requests.post(url, headers=headers, json=data)

    if response.status_code == 200:
        try:
            result = response.json()
            imagen_bytes = base64.b64decode(result[0]["generated_image_base64"])
            archivo = "imagen.png"
            with open(archivo, "wb") as f:
                f.write(imagen_bytes)
            return archivo
        except Exception as e:
            print("Error decodificando imagen:", e)
            return None
    else:
        print("Error API Hugging Face:", response.status_code, response.text)
        return None

def generar_gif(lista_imagenes, archivo="video.gif"):
    """
    Genera un GIF animado a partir de varias imágenes locales.
    """
    frames = []
    for img_path in lista_imagenes:
        frames.append(imageio.imread(img_path))
    imageio.mimsave(archivo, frames, duration=0.7)
    return archivo

# =========================
# TELEGRAM
# =========================

async def responder(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    mensaje = update.message.text

    await update.message.chat.send_action("typing")

    # Comando /imagen
    if mensaje.startswith("/imagen"):
        prompt = mensaje.replace("/imagen ", "")
        archivo = generar_imagen(prompt)
        if archivo:
            await update.message.reply_photo(photo=open(archivo, "rb"))
        else:
            await update.message.reply_text("❌ No se pudo generar la imagen.")
        return

    # Comando /gif (simula un video con varias imágenes)
    if mensaje.startswith("/gif"):
        prompts = mensaje.replace("/gif ", "").split("|")  # Separar prompts por "|"
        archivos = []
        for p in prompts:
            img = generar_imagen(p.strip())
            if img:
                archivos.append(img)
        if archivos:
            gif = generar_gif(archivos)
            await update.message.reply_document(document=open(gif, "rb"))
        else:
            await update.message.reply_text("❌ No se pudieron generar las imágenes para el GIF.")
        return

    # Respuesta normal de IA
    respuesta = preguntar_ia(user_id, mensaje)
    await update.message.reply_text(respuesta)

# =========================
# INICIAR BOT
# =========================

if __name__ == "__main__":
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, responder))

    print("🤖 BOT IA + Imagen/GIF ACTIVO")
    app.run_polling(drop_pending_updates=True, timeout=30)
