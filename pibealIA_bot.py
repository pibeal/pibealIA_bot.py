import os
import requests
from io import BytesIO
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, filters
from PIL import Image

# =========================
# VARIABLES DE ENTORNO
# =========================
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")

GROQ_MODELS_TEXT = os.getenv(
    "GROQ_MODELS_TEXT",
    "llama-3.3-70b-versatile,llama-3.1-70b-versatile,llama3-8b-8192,llama3-70b8192"
).split(",")

GROQ_MODELS_IMAGE = os.getenv(
    "GROQ_MODELS_IMAGE",
    "llama-3.3-70b-versatile,llama-3.1-70b-versatile"
).split(",")

if not TELEGRAM_TOKEN or not GROQ_API_KEY or not WEBHOOK_URL:
    raise ValueError("⚠️ Debes definir TELEGRAM_TOKEN, GROQ_API_KEY y WEBHOOK_URL")

# =========================
# FUNCIÓN PARA TEXTO
# =========================
def preguntar_ia(pregunta: str) -> str:
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}

    for modelo in GROQ_MODELS_TEXT:
        data = {
            "model": modelo,
            "messages": [
                {"role": "system", "content": "Eres Pibeal IA, ayudas con programación, tecnología, conversación y creatividad."},
                {"role": "user", "content": pregunta}
            ]
        }
        try:
            r = requests.post(url, headers=headers, json=data, timeout=60)
            r.raise_for_status()
            js = r.json()
            return js["choices"][0]["message"]["content"]
        except Exception as e:
            print(f"ERROR IA texto con modelo {modelo}: {e}")
            continue
    return "⚠️ La IA no pudo responder. Ningún modelo de texto funcionó."

# =========================
# FUNCIÓN PARA GENERAR IMAGEN
# =========================
def generar_imagen(prompt: str) -> str:
    url = "https://api.groq.com/openai/v1/images/generations"
    headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}

    for modelo in GROQ_MODELS_IMAGE:
        data = {
            "model": modelo,
            "prompt": prompt,
            "size": "1024x1024",
            "response_format": "url"
        }
        try:
            r = requests.post(url, headers=headers, json=data, timeout=60)
            r.raise_for_status()
            js = r.json()
            return js["data"][0]["url"]
        except Exception as e:
            print(f"ERROR IA imagen con modelo {modelo}: {e}")
            continue
    return None

# =========================
# FUNCIÓN PARA GENERAR GIF
# =========================
def generar_gif(prompt: str, frames: int = 3) -> BytesIO:
    images = []
    for i in range(frames):
        img_url = generar_imagen(f"{prompt} (frame {i+1})")
        if img_url:
            resp = requests.get(img_url)
            image = Image.open(BytesIO(resp.content)).convert("RGBA")
            images.append(image)
    if not images:
        return None

    # Guardar en un BytesIO como GIF animado
    gif_bytes = BytesIO()
    images[0].save(
        gif_bytes,
        format="GIF",
        save_all=True,
        append_images=images[1:],
        duration=800,
        loop=0,
        transparency=0,
        disposal=2
    )
    gif_bytes.seek(0)
    return gif_bytes

# =========================
# HANDLER TELEGRAM
# =========================
async def responder(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    texto = update.message.text.strip()

    # Saludos
    if texto.lower() in ["hola", "buenas", "hey", "inicio", "start"]:
        await update.message.reply_text(
            "👋 Hola, soy **Pibeal IA** 🤖\n\n"
            "Escríbeme algo o prueba los comandos:\n"
            "/imagen <texto> → Genera imagen\n"
            "/gif <texto> → Genera GIF animado"
        )
        return

    # Comando de imagen
    if texto.startswith("/imagen "):
        prompt = texto[len("/imagen "):].strip()
        if not prompt:
            await update.message.reply_text("Escribe un texto para generar la imagen: /imagen <texto>")
            return
        await update.message.reply_text("🎨 Generando imagen, espera unos segundos...")
        url_imagen = generar_imagen(prompt)
        if url_imagen:
            await update.message.reply_photo(url_imagen)
        else:
            await update.message.reply_text("⚠️ No se pudo generar la imagen. Intenta otro prompt.")
        return

    # Comando GIF
    if texto.startswith("/gif "):
        prompt = texto[len("/gif "):].strip()
        if not prompt:
            await update.message.reply_text("Escribe un texto para generar el GIF: /gif <texto>")
            return
        await update.message.reply_text("🎬 Generando GIF animado, espera unos segundos...")
        gif_bytes = generar_gif(prompt, frames=3)
        if gif_bytes:
            await update.message.reply_document(document=gif_bytes, filename="animacion.gif")
        else:
            await update.message.reply_text("⚠️ No se pudo generar el GIF. Intenta otro prompt.")
        return

    # Texto normal
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
    await bot_app.initialize()
    await bot_app.bot.set_webhook(f"{WEBHOOK_URL}/webhook")
    print("✅ Webhook configurado en:", f"{WEBHOOK_URL}/webhook")
    yield
    await bot_app.shutdown()
    await bot_app.stop()

app = FastAPI(lifespan=lifespan)

@app.post("/webhook")
async def webhook(req: Request):
    data = await req.json()
    update = Update.de_json(data, bot_app.bot)
    await bot_app.process_update(update)
    return {"ok": True}




   







