import os
import requests
import sqlite3

from fastapi import FastAPI, Request
import uvicorn

from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes


# =========================
# VARIABLES
# =========================

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
NEWS_API_KEY = os.getenv("NEWS_API_KEY")
REPLICATE_API_KEY = os.getenv("REPLICATE_API_KEY")


# =========================
# BASE DE DATOS (memoria)
# =========================

conn = sqlite3.connect("memoria.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS memoria(
user_id TEXT,
mensaje TEXT
)
""")

conn.commit()


# =========================
# GUARDAR MEMORIA
# =========================

def guardar_memoria(user_id, texto):

    cursor.execute(
        "INSERT INTO memoria VALUES (?,?)",
        (user_id, texto)
    )

    conn.commit()


# =========================
# OBTENER MEMORIA
# =========================

def obtener_memoria(user_id):

    cursor.execute(
        "SELECT mensaje FROM memoria WHERE user_id=? ORDER BY rowid DESC LIMIT 5",
        (user_id,)
    )

    data = cursor.fetchall()

    texto = ""

    for m in data:
        texto += m[0] + "\n"

    return texto


# =========================
# IA
# =========================

def responder_ia(user_id, texto):

    memoria = obtener_memoria(user_id)

    prompt = f"""
Historial:
{memoria}

Usuario:
{texto}
"""

    url = "https://api.groq.com/openai/v1/chat/completions"

    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }

    data = {
        "model": "llama3-70b-8192",
        "messages": [
            {"role": "user", "content": prompt}
        ]
    }

    try:

        r = requests.post(url, headers=headers, json=data, timeout=30)

        js = r.json()

        if "choices" not in js:
            return "⚠️ Error en IA"

        respuesta = js["choices"][0]["message"]["content"]

        guardar_memoria(user_id, texto)

        return respuesta

    except:

        return "⚠️ La IA no respondió."


# =========================
# NOTICIAS
# =========================

def obtener_noticias(query):

    url = f"https://newsapi.org/v2/everything?q={query}&language=es&pageSize=5&apiKey={NEWS_API_KEY}"

    r = requests.get(url)

    data = r.json()

    if "articles" not in data:

        return "⚠️ No se pudieron obtener noticias"

    texto = ""

    for n in data["articles"][:5]:

        titulo = n.get("title", "")
        link = n.get("url", "")

        texto += f"📰 {titulo}\n{link}\n\n"

    return texto


# =========================
# GENERAR IMAGEN
# =========================

def generar_imagen(prompt):

    url = "https://api.replicate.com/v1/predictions"

    headers = {
        "Authorization": f"Token {REPLICATE_API_KEY}",
        "Content-Type": "application/json"
    }

    data = {
        "version": "stability-ai/sdxl",
        "input": {
            "prompt": prompt
        }
    }

    try:

        r = requests.post(url, headers=headers, json=data)

        return "🖼 Imagen generándose..."

    except:

        return "⚠️ Error generando imagen"


# =========================
# ANALISIS CODIGO
# =========================

def analizar_codigo(codigo):

    prompt = f"""
Analiza este código y explica errores:

{codigo}
"""

    return responder_ia("analisis", prompt)


# =========================
# TELEGRAM
# =========================

app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()


async def chat(update: Update, context: ContextTypes.DEFAULT_TYPE):

    texto = update.message.text
    user_id = str(update.message.from_user.id)

    if texto.startswith("/noticias"):

        q = texto.replace("/noticias", "").strip()

        noticias = obtener_noticias(q)

        await update.message.reply_text(noticias)

        return

    if texto.startswith("/imagen"):

        prompt = texto.replace("/imagen", "")

        msg = generar_imagen(prompt)

        await update.message.reply_text(msg)

        return

    if texto.startswith("/codigo"):

        codigo = texto.replace("/codigo", "")

        analisis = analizar_codigo(codigo)

        await update.message.reply_text(analisis)

        return

    respuesta = responder_ia(user_id, texto)

    await update.message.reply_text(respuesta)


app.add_handler(MessageHandler(filters.TEXT, chat))


# =========================
# FASTAPI
# =========================

api = FastAPI()


@api.on_event("startup")
async def startup():

    await app.initialize()
    await app.start()

    await app.bot.set_webhook(f"{WEBHOOK_URL}/webhook")


@api.post("/webhook")
async def webhook(req: Request):

    data = await req.json()

    update = Update.de_json(data, app.bot)

    await app.process_update(update)

    return {"ok": True}


# =========================
# SERVER
# =========================

if __name__ == "__main__":

    uvicorn.run(
        api,
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 8080))
    )

  

  




   







