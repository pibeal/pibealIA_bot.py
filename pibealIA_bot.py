import os, requests, sqlite3, json, tempfile, re
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, filters
from gtts import gTTS

# =========================
# CONFIGURACIÓN
# =========================
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")

# Modelos específicos de Groq
MODELO_TEXTO = "llama-3.3-70b-versatile"
MODELO_VISION = "llama-3.2-11b-vision-preview"
MAX_HISTORY = 10 

# =========================
# BASE DE DATOS (SQLITE)
# =========================
def init_db():
    conn = sqlite3.connect("bot_pibeal.db")
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS mensajes 
                      (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                       user_id TEXT, role TEXT, content TEXT)''')
    conn.commit()
    conn.close()

def save_to_db(user_id, role, content):
    conn = sqlite3.connect("bot_pibeal.db")
    cursor = conn.cursor()
    cursor.execute("INSERT INTO mensajes (user_id, role, content) VALUES (?, ?, ?)", (user_id, role, content))
    conn.commit()
    conn.close()

def get_history(user_id):
    conn = sqlite3.connect("bot_pibeal.db")
    cursor = conn.cursor()
    cursor.execute("SELECT role, content FROM mensajes WHERE user_id = ? ORDER BY id DESC LIMIT ?", (user_id, MAX_HISTORY))
    rows = cursor.fetchall()
    conn.close()
    return [{"role": r, "content": c} for r, c in reversed(rows)]

def clear_history(user_id):
    conn = sqlite3.connect("bot_pibeal.db")
    cursor = conn.cursor()
    cursor.execute("DELETE FROM mensajes WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()

init_db()

# =========================
# LÓGICA DE IA (TEXTO Y VISIÓN)
# =========================
def preguntar_ia(user_id: str, pregunta: str, image_url: str = None) -> str:
    url = "https://groq.com"
    headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
    
    # Si hay imagen, usamos el modelo de Visión
    modelo = MODELO_VISION if image_url else MODELO_TEXTO
    
    # Construir contenido del mensaje
    content =
    if image_url:
        content.append({"type": "image_url", "image_url": {"url": image_url}})

    messages = [{"role": "system", "content": "Eres Pibeal IA PRO. Responde claro y breve. Si es código, usa bloques markdown."}]
    messages += get_history(user_id)
    messages.append({"role": "user", "content": content})

    try:
        r = requests.post(url, headers=headers, json={"model": modelo, "messages": messages, "temperature": 0.5}, timeout=25)
        if r.status_code == 200:
            return r.json()["choices"][0]["message"]["content"]
    except Exception as e:
        print(f"Error IA: {e}")
    return "⚠️ Hubo un error. Intenta con algo más corto o usa /reset."

# =========================
# UTILIDADES (IMAGEN, VOZ, AUDIO)
# =========================
def generar_imagen_art(prompt: str):
    url = f"https://pollinations.ai{prompt.replace(' ', '%20')}"
    r = requests.get(url, timeout=20)
    return r.content if r.status_code == 200 else None

def texto_a_voz(texto: str):
    try:
        texto_limpio = re.sub(r"[*_`~]", "", texto)[:400]
        tts = gTTS(texto_limpio, lang="es")
        temp = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
        tts.save(temp.name)
        return temp.name
    except: return None

# =========================
# HANDLER TELEGRAM
# =========================
async def responder(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message: return
    user_id = str(update.message.from_user.id)

    # 1. COMANDO RESET
    if update.message.text and update.message.text.lower() in ["/reset", "/start", "reiniciar"]:
        clear_history(user_id)
        await update.message.reply_text("🧹 Memoria borrada. ¡Dime qué necesitas!")
        return

    # 2. PROCESAR IMAGEN (VISIÓN)
    if update.message.photo:
        await update.message.reply_text("👀 Analizando imagen...")
        photo_file = await update.message.photo[-1].get_file()
        # Nota: Groq Visión prefiere URLs directas o Base64. Aquí usamos la URL temporal de Telegram.
        res = preguntar_ia(user_id, "Describe esta imagen o analiza el código que ves.", photo_file.file_path)
        save_to_db(user_id, "user", "[Envió una imagen]")
        save_to_db(user_id, "assistant", res)
        await update.message.reply_text(res)
        return

    # 3. PROCESAR TEXTO
    if update.message.text:
        texto = update.message.text.strip()
        
        # Generación de imágenes (DALL-E style)
        if texto.startswith("/imagen "):
            prompt = texto.replace("/imagen ", "")
            await update.message.reply_text("🎨 Pintando...")
            img = generar_imagen_art(prompt)
            if img: await update.message.reply_photo(img)
            else: await update.message.reply_text("Error al generar imagen.")
            return

        # IA de Texto normal
        if len(texto) > 10000:
            await update.message.reply_text("⚠️ Texto muy largo. Por favor, sé más breve.")
            return

        res = preguntar_ia(user_id, texto)
        save_to_db(user_id, "user", texto)
        save_to_db(user_id, "assistant", res)
        await update.message.reply_text(res)

# =========================
# SERVIDOR FASTAPI
# =========================
bot_app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
bot_app.add_handler(MessageHandler(filters.ALL, responder))

@asynccontextmanager
async def lifespan(app: FastAPI):
    await bot_app.initialize()
    await bot_app.bot.set_webhook(f"{WEBHOOK_URL}/webhook")
    yield
    await bot_app.shutdown()

app = FastAPI(lifespan=lifespan)

@app.post("/webhook")
async def webhook(req: Request):
    data = await req.json()
    update = Update.de_json(data, bot_app.bot)
    await bot_app.process_update(update)
    return {"ok": True}

    
