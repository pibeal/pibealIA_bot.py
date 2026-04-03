import os, requests, sqlite3, tempfile, re, base64
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, filters
from gtts import gTTS

# =========================
# CONFIG
# =========================
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")

if not TELEGRAM_TOKEN or not GROQ_API_KEY or not WEBHOOK_URL:
    raise ValueError("Faltan variables de entorno")

MODELO_TEXTO = "llama-3.3-70b-versatile"
MAX_HISTORY = 10

# =========================
# DB (MEMORIA)
# =========================
def init_db():
    conn = sqlite3.connect("bot.db")
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS mensajes 
                      (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                       user_id TEXT, role TEXT, content TEXT)''')
    conn.commit()
    conn.close()

def save_to_db(user_id, role, content):
    try:
        conn = sqlite3.connect("bot.db")
        cursor = conn.cursor()
        cursor.execute("INSERT INTO mensajes (user_id, role, content) VALUES (?, ?, ?)",
                       (user_id, role, str(content)))
        conn.commit()
        conn.close()
    except Exception as e:
        print("DB error:", e)

def get_history(user_id):
    try:
        conn = sqlite3.connect("bot.db")
        cursor = conn.cursor()
        cursor.execute("SELECT role, content FROM mensajes WHERE user_id=? ORDER BY id DESC LIMIT ?",
                       (user_id, MAX_HISTORY))
        rows = cursor.fetchall()
        conn.close()
        return [{"role": r, "content": c} for r, c in reversed(rows)]
    except Exception as e:
        print("History error:", e)
        return []

def clear_history(user_id):
    try:
        conn = sqlite3.connect("bot.db")
        cursor = conn.cursor()
        cursor.execute("DELETE FROM mensajes WHERE user_id=?", (user_id,))
        conn.commit()
        conn.close()
    except Exception as e:
        print("Clear error:", e)

init_db()

# =========================
# IA TEXTO
# =========================
def preguntar_ia(user_id: str, pregunta: str) -> str:
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}

    messages = [{"role": "system", "content": "Eres Pibeal IA PRO."}]
    messages += get_history(user_id)
    messages.append({"role": "user", "content": pregunta})

    try:
        payload = {"model": MODELO_TEXTO, "messages": messages}
        r = requests.post(url, headers=headers, json=payload, timeout=25)

        if r.status_code == 200:
            return r.json()["choices"][0]["message"]["content"]
        else:
            print("Groq error:", r.text)

    except Exception as e:
        print("IA error:", e)

    return "⚠️ Error con la IA."

# =========================
# TRANSCRIPCIÓN AUDIO
# =========================
def transcribir_audio(file_path):
    try:
        url = "https://api.groq.com/openai/v1/audio/transcriptions"
        headers = {"Authorization": f"Bearer {GROQ_API_KEY}"}

        with open(file_path, "rb") as f:
            files = {
                "file": (file_path, f),
                "model": (None, "whisper-large-v3")
            }

            r = requests.post(url, headers=headers, files=files)

        if r.status_code == 200:
            return r.json()["text"]
        else:
            print("Error transcripción:", r.text)

    except Exception as e:
        print("Audio error:", e)

    return None

# =========================
# AUDIO RESPUESTA
# =========================
def texto_a_voz(texto: str):
    try:
        texto_limpio = re.sub(r"[*_`~]", "", texto)[:300]

        temp = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
        temp.close()

        tts = gTTS(texto_limpio, lang="es")
        tts.save(temp.name)

        return temp.name

    except Exception as e:
        print("TTS error:", e)
        return None

# =========================
# TELEGRAM
# =========================
async def responder(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return

    user_id = str(update.message.from_user.id)

    # RESET
    if update.message.text and update.message.text.lower() in ["/reset", "/start"]:
        clear_history(user_id)
        await update.message.reply_text("🧹 Memoria reiniciada.")
        return

    # =========================
    # AUDIO ENTRANTE
    # =========================
    if update.message.voice:
        await update.message.reply_text("🎧 Escuchando...")

        file = await update.message.voice.get_file()

        with tempfile.NamedTemporaryFile(delete=False, suffix=".ogg") as f:
            await file.download_to_drive(f.name)
            audio_path = f.name

        texto_audio = transcribir_audio(audio_path)
        os.remove(audio_path)

        if not texto_audio:
            await update.message.reply_text("❌ No entendí el audio.")
            return

        await update.message.reply_text(f"📝 {texto_audio}")

        save_to_db(user_id, "user", texto_audio)

        res = preguntar_ia(user_id, texto_audio)

        save_to_db(user_id, "assistant", res)

        await update.message.reply_text(res)

        # RESPUESTA CON AUDIO
        audio = texto_a_voz(res)
        if audio:
            try:
                if os.path.exists(audio) and os.path.getsize(audio) > 0:
                    with open(audio, "rb") as f:
                        await update.message.reply_voice(voice=f)
            except Exception as e:
                print("Audio error:", e)
            finally:
                try:
                    os.remove(audio)
                except:
                    pass

        return

    # =========================
    # TEXTO
    # =========================
    if update.message.text:
        texto = update.message.text.strip()

        save_to_db(user_id, "user", texto)

        res = preguntar_ia(user_id, texto)

        save_to_db(user_id, "assistant", res)

        await update.message.reply_text(res)

        # AUDIO RESPUESTA
        audio = texto_a_voz(res)
        if audio:
            try:
                if os.path.exists(audio) and os.path.getsize(audio) > 0:
                    with open(audio, "rb") as f:
                        await update.message.reply_voice(voice=f)
            except Exception as e:
                print("Audio error:", e)
            finally:
                try:
                    os.remove(audio)
                except:
                    pass

# =========================
# FASTAPI
# =========================
bot_app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
bot_app.add_handler(MessageHandler(filters.ALL, responder))

@asynccontextmanager
async def lifespan(app: FastAPI):
    await bot_app.initialize()
    await bot_app.start()
    await bot_app.bot.set_webhook(f"{WEBHOOK_URL}/webhook")
    print("✅ BOT FINAL ACTIVO (voz + memoria)")
    yield
    await bot_app.shutdown()

app = FastAPI(lifespan=lifespan)

@app.post("/webhook")
async def webhook(req: Request):
    try:
        data = await req.json()
        update = Update.de_json(data, bot_app.bot)
        await bot_app.process_update(update)
    except Exception as e:
        print("Webhook error:", e)

    return {"ok": True}
