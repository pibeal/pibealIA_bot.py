import os
import requests
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters
from groq import Groq
from moviepy.editor import ImageClip, concatenate_videoclips, vfx
from io import BytesIO

# =========================
# VARIABLES
# =========================
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
HF_API_TOKEN = os.getenv("HF_TOKEN")  # Hugging Face token gratis
HF_API_URL = "https://api-inference.huggingface.co/models/runwayml/stable-diffusion-v1-5"

# =========================
# CLIENTE IA
# =========================
client = Groq(api_key=GROQ_API_KEY)
memoria = {}

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
# FUNCIONES HUGGING FACE API
# =========================
def generar_imagen_api(prompt):
    headers = {"Authorization": f"Bearer {HF_API_TOKEN}"}
    payload = {"inputs": prompt}
    response = requests.post(HF_API_URL, headers=headers, json=payload, timeout=60)
    if response.status_code == 200:
        return BytesIO(response.content)
    else:
        raise Exception(f"Error Hugging Face: {response.status_code} {response.text}")

# =========================
# TELEGRAM RESPONDER
# =========================
async def responder(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    mensaje = update.message.text
    await update.message.chat.send_action("typing")
    respuesta = preguntar_ia(user_id, mensaje)
    await update.message.reply_text(respuesta)

# =========================
# COMANDO /imagen
# =========================
async def imagen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    prompt = " ".join(context.args)
    if not prompt:
        await update.message.reply_text("Escribe un prompt: /imagen <texto>")
        return

    await update.message.reply_text("🎨 Generando imagen... ⏳")
    try:
        imagen_io = generar_imagen_api(prompt)
        await update.message.reply_photo(photo=imagen_io)
    except Exception as e:
        await update.message.reply_text(f"Error generando imagen: {e}")

# =========================
# COMANDO /video con animación profesional
# =========================
async def video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    prompt = " ".join(context.args)
    if not prompt:
        await update.message.reply_text("Escribe un prompt: /video <texto>")
        return

    await update.message.reply_text("🎬 Generando video animado... ⏳")
    try:
        # Generar 3 imágenes
        frames = [generar_imagen_api(prompt) for _ in range(3)]
        clips = []

        for frame_io in frames:
            clip = ImageClip(frame_io).set_duration(2)  # 2 segundos por frame
            # Zoom lento tipo Ken Burns
            clip = clip.fx(vfx.zoom_in, final_scale=1.1)
            clips.append(clip)

        # Concatenar clips y hacer transición suave
        video_path = "video_animado.mp4"
        final_clip = concatenate_videoclips(clips, method="compose")
        final_clip.write_videofile(video_path, fps=24)
        await update.message.reply_video(video=open(video_path, "rb"))

    except Exception as e:
        await update.message.reply_text(f"Error generando video: {e}")

# =========================
# COMANDO /start
# =========================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 BOT IA CREATIVO PROFESIONAL ACTIVO\n\n"
        "Usa /imagen <texto> para generar imágenes.\n"
        "Usa /video <texto> para generar videos cortos animados.\n"
        "O escribe un mensaje normal para que te responda con IA."
    )

# =========================
# INICIAR BOT
# =========================
if __name__ == "__main__":
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("imagen", imagen))
    app.add_handler(CommandHandler("video", video))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, responder))
    print("🤖 BOT IA PROFESIONAL ACTIVO")
    app.run_polling(drop_pending_updates=True, timeout=30)








