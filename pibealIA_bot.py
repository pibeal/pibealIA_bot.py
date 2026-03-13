import os
import requests
import sqlite3
import asyncio

from fastapi import FastAPI, Request
import uvicorn

from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    ContextTypes,
    MessageHandler,
    CommandHandler,
    filters
)

# =========================
# VARIABLES
# =========================

TOKEN = os.getenv("TELEGRAM_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
NEWS_API_KEY = os.getenv("NEWS_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")

# =========================
# BASE DE DATOS MEMORIA
# =========================

conn = sqlite3.connect("memoria.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS memoria(
user_id INTEGER,
mensaje TEXT
)
""")

conn.commit()

# =========================
# FASTAPI
# =========================

api = FastAPI()

# =========================
# IA GROQ
# =========================

def responder_ia(user_id, texto):

    cursor.execute(
        "SELECT mensaje FROM memoria WHERE user_id=? ORDER BY rowid DESC LIMIT 6",
        (user_id,)
    )

    historial = cursor.fetchall()

    messages = []

    for h in historial[::-1]:
        messages.append({"role":"user","content":h[0]})

    messages.append({"role":"user","content":texto})

    url = "https://api.groq.com/openai/v1/chat/completions"

    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }

    data = {
        "model":"llama3-70b-8192",
        "messages":messages
    }

    r = requests.post(url, headers=headers, json=data)

    respuesta = r.json()["choices"][0]["message"]["content"]

    cursor.execute(
        "INSERT INTO memoria VALUES (?,?)",
        (user_id, texto)
    )

    conn.commit()

    return respuesta

# =========================
# NOTICIAS
# =========================

def obtener_noticias(query):

    url = f"https://newsapi.org/v2/everything?q={query}&language=es&pageSize=5&apiKey={NEWS_API_KEY}"

    r = requests.get(url)

    data = r.json()

    texto=""

    for n in data["articles"][:5]:

        texto += f"📰 {n['title']}\n{n['url']}\n\n"

    return texto

# =========================
# VIDEO IA
# =========================

async def generar_video(update,prompt):

    url=f"https://image.pollinations.ai/prompt/{prompt}"

    await update.message.reply_text(
        f"🎬 Generando video IA...\nEscena: {prompt}"
    )

    await update.message.reply_video(url)

# =========================
# IMAGEN
# =========================

async def generar_imagen(update,prompt):

    url=f"https://image.pollinations.ai/prompt/{prompt}"

    await update.message.reply_photo(url)

# =========================
# ANALISIS DE CODIGO
# =========================

def analizar_codigo(codigo):

    prompt=f"""
Analiza este codigo y explica:

- que hace
- errores posibles
- mejoras

codigo:

{codigo}
"""

    return responder_ia(0,prompt)

# =========================
# START
# =========================

async def start(update:Update,context:ContextTypes.DEFAULT_TYPE):

    await update.message.reply_text(
"""
🤖 BOT IA PRO ONLINE

Funciones:

noticias tecnologia
genera imagen robot
genera video ciudad futurista

puedes enviarme:

💻 codigo
🎤 audio
💬 preguntas normales
"""
)

# =========================
# AUDIO
# =========================

async def audio(update:Update,context:ContextTypes.DEFAULT_TYPE):

    file=await update.message.voice.get_file()

    path="audio.ogg"

    await file.download_to_drive(path)

    url="https://api.openai.com/v1/audio/transcriptions"

    headers={
        "Authorization":f"Bearer {OPENAI_API_KEY}"
    }

    files={"file":open(path,"rb")}
    data={"model":"whisper-1"}

    r=requests.post(url,headers=headers,files=files,data=data)

    texto=r.json()["text"]

    respuesta=responder_ia(update.message.from_user.id,texto)

    await update.message.reply_text(respuesta)

# =========================
# CHAT PRINCIPAL
# =========================

async def chat(update:Update,context:ContextTypes.DEFAULT_TYPE):

    texto=update.message.text.lower()

    user_id=update.message.from_user.id

    if "noticia" in texto:

        tema=texto.replace("noticias","").replace("noticia","").strip()

        if tema=="":
            tema="tecnologia"

        await update.message.reply_text(
            obtener_noticias(tema)
        )

        return

    if "imagen" in texto:

        prompt=texto.replace("imagen","").replace("genera","")

        await generar_imagen(update,prompt)

        return

    if "video" in texto:

        prompt=texto.replace("video","").replace("genera","")

        await generar_video(update,prompt)

        return

    if "```" in texto or "import " in texto:

        analisis=analizar_codigo(texto)

        await update.message.reply_text(analisis)

        return

    respuesta=responder_ia(user_id,texto)

    await update.message.reply_text(respuesta)

# =========================
# TELEGRAM
# =========================

app=ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start",start))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND,chat))
app.add_handler(MessageHandler(filters.VOICE,audio))

# =========================
# WEBHOOK
# =========================

@api.post("/webhook")
async def webhook(request:Request):

    data=await request.json()

    update=Update.de_json(data,app.bot)

    await app.process_update(update)

    return {"ok":True}

# =========================
# ROOT
# =========================

@api.get("/")
def root():

    return {"status":"BOT ONLINE"}

# =========================
# MAIN
# =========================

async def main():

    await app.initialize()

    await app.bot.set_webhook(f"{WEBHOOK_URL}/webhook")

if __name__=="__main__":

    asyncio.run(main())

    uvicorn.run(
        api,
        host="0.0.0.0",
        port=int(os.environ.get("PORT",8080))
    )





   







