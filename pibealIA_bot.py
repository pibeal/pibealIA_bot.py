import os
import requests
import json
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, filters

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
# CONFIG MEMORIA
# =========================

MAX_HISTORY = 20

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
# IA PRO (MEMORIA + RESUMEN)
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
- Usas formato con emojis cuando ayuda
- Mantienes contexto de la conversación
"""

    # 🔥 RESUMEN AUTOMÁTICO
    if len(history) > 15:
        try:
            resumen_prompt = [
                {"role": "system", "content": "Resume esta conversación en puntos clave claros y cortos"}
            ] + history

            r = requests.post(url, headers=headers, json={
                "model": GROQ_MODELS_TEXT[0],
                "messages": resumen_prompt
            }, timeout=60)

            resumen = r.json()["choices"][0]["message"]["content"]

            history.clear()
            history.append({
                "role": "system",
                "content": f"Resumen previo: {resumen}"
            })
        except:
            pass

    messages = [{"role": "system", "content": system_prompt}]
    messages += history
    messages.append({"role": "user", "content": pregunta})

    for modelo in GROQ_MODELS_TEXT:
        try:
            r = requests.post(url, headers=headers, json={
                "model": modelo,
                "messages": messages
            }, timeout=60)

            r.raise_for_status()
            return r.json()["choices"][0]["message"]["content"]

        except Exception as e:
            print(f"ERROR IA: {e}")
            continue

    return "⚠️ Error en IA"

# =========================
# IMÁGENES
# =========================

def generar_imagen(prompt: str) -> str:
    url = "https://api.groq.com/openai/v1/images/generations"
    headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}

    for modelo in GROQ_MODELS_IMAGE:
        try:
            r = requests.post(url, headers=headers, json={
                "model": modelo,
                "prompt": prompt,
                "size": "1024x1024"
            }, timeout=60)

            r.raise_for_status()
            return r.json()["data"][0]["url"]

        except Exception as e:
            print(f"ERROR IMAGEN: {e}")
            continue

    return None

# =========================
# HANDLER
# =========================

async def responder(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    user_id = str(update.message.from_user.id)

    if "history" not in context.user_data:
        context.user_data["history"] = load_memory(user_id)

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
            await update.message.reply_photo(img)
        else:
            await update.message.reply_text("⚠️ No se pudo generar la imagen")
        return

    # GUARDAR USER
    context.user_data["history"].append({
        "role": "user",
        "content": texto
    })

    # IA
    respuesta = preguntar_ia(user_id, texto, context.user_data["history"])

    # GUARDAR BOT
    context.user_data["history"].append({
        "role": "assistant",
        "content": respuesta
    })

    # LIMITE
    if len(context.user_data["history"]) > MAX_HISTORY:
        context.user_data["history"] = context.user_data["history"][-MAX_HISTORY:]

    save_memory(user_id, context.user_data["history"])

    # RESPUESTA PRO
    respuesta_final = f"🤖 *Pibeal IA PRO*\n\n{respuesta}"

    await update.message.reply_text(respuesta_final, parse_mode=ParseMode.MARKDOWN)

# =========================
# BOT
# =========================

bot_app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
bot_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, responder))

# =========================
# FASTAPI
# =========================

@asynccontextmanager
async def lifespan(app: FastAPI):
    await bot_app.initialize()
    await bot_app.bot.set_webhook(f"{WEBHOOK_URL}/webhook")
    print("✅ Bot PRO corriendo...")
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


       
