import os
import requests
import json
import tempfile
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, filters
from gtts import gTTS

# =========================
# VARIABLES
# =========================

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")

GROQ_MODELS_TEXT = [
    "llama-3.3-70b-versatile",
    "llama-3.1-70b-versatile",
    "mixtral-8x7b-32768"
]

MAX_HISTORY = 20

# =========================
# MEMORIA
# =========================

def save_memory(user_id, history):
    try:
        with open(f"memory_{user_id}.json", "w") as f:
            json.dump(history, f)
    except:
        pass

def load_memory(user_id):
    try:
        with open(f"memory_{user_id}.json", "r") as f:
            return json.load(f)
    except:
        return []

# =========================
# IA BASE
# =========================

def preguntar_ia(user_id: str, pregunta: str, history: list) -> str:
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }

    system_prompt = """
Eres Pibeal IA PRO 🤖

- Experto en programación, trading, criptomonedas y tecnología
- Respondes claro, directo y estructurado
- Das respuestas útiles y accionables
"""

    # 🔥 RESUMEN AUTOMÁTICO
    if len(history) > 15:
        try:
            resumen_prompt = [{"role": "system", "content": "Resume esta conversación en puntos clave"}] + history

            r = requests.post(url, headers=headers, json={
                "model": GROQ_MODELS_TEXT[0],
                "messages": resumen_prompt,
                "temperature": 0.3
            }, timeout=60)

            resumen = r.json()["choices"][0]["message"]["content"]

            history.clear()
            history.append({"role": "system", "content": f"Resumen previo: {resumen}"})
        except:
            pass

    messages = [{"role": "system", "content": system_prompt}]
    messages += history
    messages.append({"role": "user", "content": pregunta})

    for modelo in GROQ_MODELS_TEXT:
        try:
            r = requests.post(url, headers=headers, json={
                "model": modelo,
                "messages": messages,
                "temperature": 0.7,
                "max_tokens": 800
            }, timeout=60)

            r.raise_for_status()
            return r.json()["choices"][0]["message"]["content"]

        except:
            continue

    return "⚠️ Error IA"

# =========================
# DOBLE IA
# =========================

def mejorar_respuesta(user_id, respuesta_base):
    try:
        return preguntar_ia(
            user_id,
            f"Mejora esta respuesta, hazla más clara, profesional y estructurada:\n\n{respuesta_base}",
            []
        )
    except:
        return respuesta_base

# =========================
# IMÁGENES
# =========================

def generar_imagen(prompt: str):
    try:
        prompt = f"high quality, detailed, 4k: {prompt}"
        url = f"https://image.pollinations.ai/prompt/{prompt.replace(' ', '%20')}"
        img_data = requests.get(url, timeout=60).content
        return img_data
    except:
        return None

# =========================
# VOZ
# =========================

def texto_a_voz(texto: str):
    try:
        tts = gTTS(texto, lang="es")
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
        tts.save(temp_file.name)
        return temp_file.name
    except:
        return None

def voz_a_texto(file_path):
    try:
        url = "https://api.groq.com/openai/v1/audio/transcriptions"
        headers = {"Authorization": f"Bearer {GROQ_API_KEY}"}

        with open(file_path, "rb") as f:
            r = requests.post(url, headers=headers, files={
                "file": f,
                "model": (None, "whisper-large-v3")
            })

        return r.json()["text"]
    except:
        return None

# =========================
# HANDLER
# =========================

async def responder(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return

    user_id = str(update.message.from_user.id)

    if "history" not in context.user_data:
        context.user_data["history"] = load_memory(user_id)

    # =====================
    # 🎤 AUDIO
    # =====================
    if update.message.voice:
        file = await update.message.voice.get_file()

        temp_audio = tempfile.NamedTemporaryFile(delete=False, suffix=".ogg")
        await file.download_to_drive(temp_audio.name)

        await update.message.reply_text("🎧 Escuchando...")

        texto_usuario = voz_a_texto(temp_audio.name)

        if not texto_usuario:
            await update.message.reply_text("⚠️ No entendí el audio")
            return

        context.user_data["history"].append({"role": "user", "content": texto_usuario})

        respuesta = preguntar_ia(user_id, texto_usuario, context.user_data["history"])

        if len(texto_usuario) > 20:
            respuesta = mejorar_respuesta(user_id, respuesta)

        audio_path = texto_a_voz(respuesta)

        if audio_path:
            with open(audio_path, "rb") as audio:
                await update.message.reply_voice(audio)
        else:
            await update.message.reply_text(respuesta)

        return

    # =====================
    # TEXTO
    # =====================
    if not update.message.text:
        return

    texto = update.message.text.strip()

    # SALUDO
    if texto.lower() in ["hola", "buenas", "hey", "inicio", "start"]:
        await update.message.reply_text("👋 Soy Pibeal IA 🤖 ¿En qué puedo ayudarte?")
        return

    # IMAGEN
    if texto.lower().startswith("/imagen "):
        prompt = texto[len("/imagen "):].strip()
        await update.message.reply_text("🎨 Generando imagen...")

        img = generar_imagen(prompt)

        if img:
            await update.message.reply_photo(photo=img)
        else:
            await update.message.reply_text("⚠️ Error generando imagen")

        return

    # GUARDAR USER
    context.user_data["history"].append({"role": "user", "content": texto})

    respuesta = preguntar_ia(user_id, texto, context.user_data["history"])

    if len(texto) > 20:
        respuesta = mejorar_respuesta(user_id, respuesta)

    context.user_data["history"].append({"role": "assistant", "content": respuesta})

    if len(context.user_data["history"]) > MAX_HISTORY:
        context.user_data["history"] = context.user_data["history"][-MAX_HISTORY:]

    save_memory(user_id, context.user_data["history"])

    respuesta_final = f"🤖 *Pibeal IA PRO*\n\n{respuesta}"

    await update.message.reply_text(respuesta_final, parse_mode=ParseMode.MARKDOWN)

# =========================
# BOT
# =========================

bot_app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
bot_app.add_handler(MessageHandler(filters.ALL, responder))

# =========================
# FASTAPI
# =========================

@asynccontextmanager
async def lifespan(app: FastAPI):
    await bot_app.initialize()
    await bot_app.bot.set_webhook(f"{WEBHOOK_URL}/webhook")
    print("✅ Bot PRO+ con voz corriendo")
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
  

