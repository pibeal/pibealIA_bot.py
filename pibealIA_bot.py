import os
import requests
import json
import tempfile
import re
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, filters

# =========================
# VARIABLES
# =========================

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")
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
Experto en programación, trading, criptomonedas y tecnología.
Respondes claro, útil y directo.
"""

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
            }, timeout=30)

            r.raise_for_status()
            js = r.json()

            if not js.get("choices"):
                continue

            return js["choices"][0]["message"]["content"]

        except:
            continue

    return "⚠️ Error en IA"

# =========================
# DOBLE IA
# =========================

def mejorar_respuesta(user_id, respuesta_base):
    try:
        return preguntar_ia(
            user_id,
            f"Mejora esta respuesta y hazla más clara y profesional:\n\n{respuesta_base}",
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
        
        r = requests.get(url, timeout=30)
        if r.status_code == 200:
            return r.content
        return None
    except:
        return None

# =========================
# VOZ (JARVIS 🔥)
# =========================

def texto_a_voz(texto: str):
    try:
        # limpiar texto
        texto = re.sub(r"[*_`~]", "", texto)
        texto = re.sub(r"[^\w\s,.!?áéíóúÁÉÍÓÚñÑ]", "", texto)
        texto = re.sub(r"\s+", " ", texto).strip()

        url = "https://api.elevenlabs.io/v1/text-to-speech/EXAVITQu4vr4xnSDxMaL"

        headers = {
            "xi-api-key": ELEVENLABS_API_KEY,
            "Content-Type": "application/json"
        }

        data = {
            "text": texto,
            "model_id": "eleven_multilingual_v2",
            "voice_settings": {
                "stability": 0.4,
                "similarity_boost": 0.9
            }
        }

        response = requests.post(url, json=data, headers=headers)

        if response.status_code != 200:
            print("Error ElevenLabs:", response.text)
            return None

        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
        temp_file.write(response.content)

        return temp_file.name

    except Exception as e:
        print("Error voz:", e)
        return None

# =========================
# AUDIO → TEXTO
# =========================

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

    if not isinstance(context.user_data.get("history"), list):
        context.user_data["history"] = load_memory(user_id)

    # 🎤 AUDIO
    if update.message.voice:
        await update.message.chat.send_action(action="record_voice")

        file = await update.message.voice.get_file()
        temp_audio = tempfile.NamedTemporaryFile(delete=False, suffix=".ogg")
        await file.download_to_drive(temp_audio.name)

        texto_usuario = voz_a_texto(temp_audio.name)

        if not texto_usuario or len(texto_usuario.strip()) < 2:
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

    # TEXTO
    if not update.message.text:
        return

    texto = update.message.text.strip()

    await update.message.chat.send_action(action="typing")

    if texto.lower() in ["hola", "buenas", "hey", "inicio", "start"]:
        await update.message.reply_text("👋 Soy Pibeal IA 🤖 ¿En qué puedo ayudarte?")
        return

    if texto.lower().startswith("/imagen "):
        prompt = texto[len("/imagen "):].strip()
        await update.message.reply_text("🎨 Generando imagen...")

        img = generar_imagen(prompt)

        if img:
            await update.message.reply_photo(photo=img)
        else:
            await update.message.reply_text("⚠️ Error generando imagen")

        return

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
    print("✅ Bot PRO+ con voz real corriendo")
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


