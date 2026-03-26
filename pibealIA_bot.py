import os
import requests
import json
import tempfile
import re
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from telegram import Update
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
# IA
# =========================

def preguntar_ia(user_id: str, pregunta: str, history: list) -> str:
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }

    messages = [{"role": "system", "content": "Eres Pibeal IA PRO, respondes claro y útil."}]
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

            if js.get("choices"):
                return js["choices"][0]["message"]["content"]

        except:
            continue

    return "Error en IA"

# =========================
# MEJORAR RESPUESTA
# =========================

def mejorar_respuesta(user_id, respuesta):
    try:
        return preguntar_ia(user_id, f"Mejora esta respuesta:\n{respuesta}", [])
    except:
        return respuesta

# =========================
# IMAGEN
# =========================

def generar_imagen(prompt: str):
    try:
        url = f"https://image.pollinations.ai/prompt/{prompt.replace(' ', '%20')}"
        r = requests.get(url, timeout=30)
        return r.content if r.status_code == 200 else None
    except:
        return None

# =========================
# LIMPIAR TEXTO (CLAVE 🔥)
# =========================

def limpiar_texto_para_voz(texto: str) -> str:
    texto = re.sub(r"[*_`~]", "", texto)
    texto = re.sub(r"[^\w\s,.!?áéíóúÁÉÍÓÚñÑ]", "", texto)
    texto = re.sub(r"\s+", " ", texto).strip()
    texto = texto.replace(".", ". ")
    return texto

# =========================
# VOZ
# =========================

def texto_a_voz(texto: str):
    try:
        texto = limpiar_texto_para_voz(texto)

        tts = gTTS(texto, lang="es")
        temp = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
        tts.save(temp.name)

        return temp.name
    except:
        return None

# =========================
# AUDIO → TEXTO
# =========================

def voz_a_texto(path):
    try:
        url = "https://api.groq.com/openai/v1/audio/transcriptions"
        headers = {"Authorization": f"Bearer {GROQ_API_KEY}"}

        with open(path, "rb") as f:
            r = requests.post(url, headers=headers, files={
                "file": f,
                "model": (None, "whisper-large-v3")
            })

        return r.json().get("text")
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

    # 🎤 AUDIO
    if update.message.voice:
        await update.message.reply_text("🎧 Escuchando...")

        file = await update.message.voice.get_file()
        temp_audio = tempfile.NamedTemporaryFile(delete=False, suffix=".ogg")
        await file.download_to_drive(temp_audio.name)

        texto_usuario = voz_a_texto(temp_audio.name)

        if not texto_usuario or len(texto_usuario.strip()) < 2:
            await update.message.reply_text("No entendí el audio")
            return

        context.user_data["history"].append({"role": "user", "content": texto_usuario})

        respuesta = preguntar_ia(user_id, texto_usuario, context.user_data["history"])

        if len(texto_usuario) > 20:
            respuesta = mejorar_respuesta(user_id, respuesta)

        audio = texto_a_voz(respuesta)

        if audio:
            with open(audio, "rb") as a:
                await update.message.reply_voice(a)
        else:
            await update.message.reply_text(respuesta)

        return

    # TEXTO
    if not update.message.text:
        return

    texto = update.message.text.strip()

    if texto.lower() in ["hola", "buenas", "start"]:
        await update.message.reply_text("Soy Pibeal IA ¿En qué puedo ayudarte?")
        return

    if texto.startswith("/imagen "):
        prompt = texto.replace("/imagen ", "")
        await update.message.reply_text("Generando imagen...")

        img = generar_imagen(prompt)
        if img:
            await update.message.reply_photo(img)
        else:
            await update.message.reply_text("Error generando imagen")
        return

    context.user_data["history"].append({"role": "user", "content": texto})

    respuesta = preguntar_ia(user_id, texto, context.user_data["history"])

    if len(texto) > 20:
        respuesta = mejorar_respuesta(user_id, respuesta)

    context.user_data["history"].append({"role": "assistant", "content": respuesta})

    save_memory(user_id, context.user_data["history"])

    await update.message.reply_text(respuesta)

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

   
