import os
import requests
import sqlite3
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
import uvicorn

from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes


# =====================
# VARIABLES
# =====================

TOKEN=os.getenv("TELEGRAM_TOKEN")
WEBHOOK_URL=os.getenv("WEBHOOK_URL")

GROQ_API_KEY=os.getenv("GROQ_API_KEY")
NEWS_API_KEY=os.getenv("NEWS_API_KEY")
REPLICATE_API_KEY=os.getenv("REPLICATE_API_KEY")


# =====================
# BASE DE DATOS
# =====================

conn=sqlite3.connect("memoria.db",check_same_thread=False)
cursor=conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS memoria(
user_id TEXT,
mensaje TEXT
)
""")

conn.commit()


# =====================
# MEMORIA
# =====================

def guardar_memoria(user,texto):

    cursor.execute(
        "INSERT INTO memoria VALUES (?,?)",
        (user,texto)
    )

    conn.commit()


def obtener_memoria(user):

    cursor.execute(
        "SELECT mensaje FROM memoria WHERE user_id=? ORDER BY rowid DESC LIMIT 8",
        (user,)
    )

    data=cursor.fetchall()

    historial=""

    for m in data:
        historial+=m[0]+"\n"

    return historial


# =====================
# IA
# =====================

def responder_ia(user,texto):

    memoria=obtener_memoria(user)

    prompt=f"""
Eres un asistente llamado Pibeal IA.
Responde de forma clara.

Historial:
{memoria}

Usuario:
{texto}
"""

    url="https://api.groq.com/openai/v1/chat/completions"

    headers={
        "Authorization":f"Bearer {GROQ_API_KEY}",
        "Content-Type":"application/json"
    }

    data={
        "model":"llama3-8b-8192",
        "messages":[
            {"role":"user","content":prompt}
        ]
    }

    try:

r = requests.post(url, headers=headers, json=data, timeout=30)

js = r.json()

if "choices" not in js:
    return f"Error IA:\n{js}"

respuesta = js["choices"][0]["message"]["content"]

guardar_memoria(user, texto)

return respuesta


# =====================
# NOTICIAS
# =====================

def noticias(q):

    url=f"https://newsapi.org/v2/everything?q={q}&language=es&pageSize=5&apiKey={NEWS_API_KEY}"

    r=requests.get(url)

    data=r.json()

    if "articles" not in data:
        return "No pude obtener noticias."

    texto=""

    for n in data["articles"][:5]:

        texto+=f"📰 {n['title']}\n{n['url']}\n\n"

    return texto


# =====================
# CRYPTO
# =====================

def precio_crypto(moneda):

    url=f"https://api.coingecko.com/api/v3/simple/price?ids={moneda}&vs_currencies=usd"

    r=requests.get(url)

    data=r.json()

    if moneda not in data:
        return None

    precio=data[moneda]["usd"]

    return f"{moneda.upper()} vale ${precio}"


# =====================
# IMAGEN
# =====================

def generar_imagen(prompt):

    url="https://api.replicate.com/v1/predictions"

    headers={
        "Authorization":f"Token {REPLICATE_API_KEY}",
        "Content-Type":"application/json"
    }

    data={
        "version":"stability-ai/sdxl",
        "input":{"prompt":prompt}
    }

    try:

        requests.post(url,headers=headers,json=data)

        return "🖼 Generando imagen..."

    except:

        return "No pude generar la imagen."


# =====================
# DETECCION INTENCION
# =====================

def detectar_intencion(texto):

    t=texto.lower()

    if "imagen" in t or "dibuja" in t:
        return "imagen"

    if "noticia" in t:
        return "noticias"

    if "precio" in t or "vale" in t or "bitcoin" in t:
        return "crypto"

    if "codigo" in t or "error" in t:
        return "codigo"

    return "chat"


# =====================
# TELEGRAM
# =====================

bot=ApplicationBuilder().token(TOKEN).build()


async def chat(update:Update,context:ContextTypes.DEFAULT_TYPE):

    texto=update.message.text
    user=str(update.message.from_user.id)


    if texto.lower() in ["hola","hello","hi","buenas"]:

        await update.message.reply_text(
            "Soy Pibeal IA en que puedo ayudarte hoy"
        )

        return


    tipo=detectar_intencion(texto)


    if tipo=="imagen":

        res=generar_imagen(texto)

        await update.message.reply_text(res)

        return


    if tipo=="noticias":

        res=noticias(texto)

        await update.message.reply_text(res)

        return


    if tipo=="crypto":

        for coin in ["bitcoin","ethereum","solana"]:

            if coin in texto.lower():

                res=precio_crypto(coin)

                if res:
                    await update.message.reply_text(res)
                    return


    if tipo=="codigo":

        analisis=responder_ia(user,"Analiza este código:\n"+texto)

        await update.message.reply_text(analisis)

        return


    respuesta=responder_ia(user,texto)

    await update.message.reply_text(respuesta)


bot.add_handler(MessageHandler(filters.TEXT,chat))


# =====================
# FASTAPI
# =====================

@asynccontextmanager
async def lifespan(api:FastAPI):

    await bot.initialize()
    await bot.start()

    await bot.bot.set_webhook(f"{WEBHOOK_URL}/webhook")

    yield


api=FastAPI(lifespan=lifespan)


@api.post("/webhook")
async def webhook(req:Request):

    data=await req.json()

    update=Update.de_json(data,bot.bot)

    await bot.process_update(update)

    return {"ok":True}


# =====================
# SERVER
# =====================

if __name__=="__main__":

    uvicorn.run(
        api,
        host="0.0.0.0",
        port=int(os.environ.get("PORT",8080))
    )


   






  




   







