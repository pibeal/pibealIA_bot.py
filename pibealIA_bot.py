import os
import requests
import tempfile
import imageio
from gtts import gTTS
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, MessageHandler, CallbackQueryHandler, CommandHandler, ContextTypes, filters

# =========================
# VARIABLES DE ENTORNO
# =========================
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")  # Para Whisper STT
# Opcional: GROQ_API_KEY, HF_TOKEN, NEWSAPI_KEY

memoria_ia = {}
elecciones_imagen = {}
elecciones_video = {}

# =========================
# FUNCIONES IA
# =========================
def responder_ia(user_id, mensaje):
    if user_id not in memoria_ia:
        memoria_ia[user_id] = []
    memoria_ia[user_id].append({"role":"user","content":mensaje})
    respuesta = f"IA responde a: {mensaje}"
    memoria_ia[user_id].append({"role":"assistant","content":respuesta})
    return respuesta

# =========================
# STT con Whisper
# =========================
def audio_a_texto(path_audio):
    url = "https://api.openai.com/v1/audio/transcriptions"
    headers = {"Authorization": f"Bearer {OPENAI_API_KEY}"}
    files = {"file": open(path_audio,"rb")}
    data = {"model":"whisper-1"}
    r = requests.post(url, headers=headers, files=files, data=data)
    if r.status_code == 200:
        return r.json()["text"]
    return None

# =========================
# TTS
# =========================
def generar_voz(texto):
    tts = gTTS(text=texto, lang="es")
    tmp = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
    tts.save(tmp.name)
    return tmp.name

# =========================
# POLLINATIONS
# =========================
def generar_imagen_pollinations(prompt, estilo=None):
    if estilo:
        prompt = f"{prompt}, estilo {estilo}"
    return f"https://image.pollinations.ai/prompt/{prompt}"

def generar_varias_imagenes(prompt, estilo=None, cantidad=5):
    urls = []
    for i in range(cantidad):
        urls.append(generar_imagen_pollinations(f"{prompt} variante {i+1}", estilo))
    return urls

def generar_video_pollinations(urls, fps=3):
    temp_dir = tempfile.mkdtemp()
    archivos = []
    for i, url in enumerate(urls):
        nombre = os.path.join(temp_dir, f"img_{i}.png")
        r = requests.get(url)
        if r.status_code == 200:
            with open(nombre, "wb") as f:
                f.write(r.content)
            archivos.append(nombre)
    if archivos:
        video_path = os.path.join(temp_dir, "video.mp4")
        frames = [imageio.imread(a) for a in archivos]
        imageio.mimsave(video_path, frames, fps=fps, codec="libx264")
        return video_path
    return None

# =========================
# TELEGRAM HANDLERS
# =========================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    mensaje = (
        "🤖 Bot IA + Voz + Pollinations DEFINITIVO\n\n"
        "Escribe texto o envía tu voz.\n"
        "Comandos opcionales:\n"
        "/imagen <descripción> | <estilo opcional>\n"
        "/logo <descripción> | <estilo opcional>\n"
        "/video <prompt1>|<prompt2>|..."
    )
    await update.message.reply_text(mensaje)

async def generar_imagen(update: Update, prompt, estilo=None):
    urls = generar_varias_imagenes(prompt, estilo, cantidad=5)
    elecciones_imagen[update.message.from_user.id] = urls
    botones = [[InlineKeyboardButton(f"Opción {i+1}", callback_data=f"seleccion|{i}")] for i in range(len(urls))]
    markup = InlineKeyboardMarkup(botones)
    await update.message.reply_text("Selecciona la imagen que más te guste:", reply_markup=markup)

async def imagen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("❌ Escribe la descripción")
        return
    texto = " ".join(context.args)
    partes = texto.split("|")
    prompt = partes[0].strip()
    estilo = partes[1].strip() if len(partes) > 1 else None
    await generar_imagen(update, prompt, estilo)

async def logo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("❌ Escribe la descripción")
        return
    texto = " ".join(context.args)
    partes = texto.split("|")
    prompt = partes[0].strip()
    estilo = partes[1].strip() if len(partes) > 1 else None
    await generar_imagen(update, prompt, estilo)

async def video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("❌ Escribe al menos un prompt")
        return
    prompts = " ".join(context.args).split("|")
    urls = []
    for p in prompts:
        urls.extend(generar_varias_imagenes(p.strip(), cantidad=2))
    archivo = generar_video_pollinations(urls, fps=3)
    if archivo:
        await update.message.reply_document(document=open(archivo, "rb"))
    else:
        await update.message.reply_text("❌ No se pudieron generar las imágenes para el video.")

async def botones(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    if data.startswith("seleccion"):
        _, index_str = data.split("|")
        index = int(index_str)
        user_id = query.from_user.id
        if user_id not in elecciones_imagen:
            await query.edit_message_text("❌ No hay imágenes para seleccionar")
            return
        url = elecciones_imagen[user_id][index]
        r = requests.get(url)
        if r.status_code == 200:
            with tempfile.NamedTemporaryFile(suffix=".png") as tmp:
                tmp.write(r.content)
                tmp.flush()
                await query.message.reply_photo(photo=open(tmp.name,"rb"))
        await query.edit_message_text("✅ Imagen seleccionada")

# =========================
# MENSAJES NORMALES / AUDIO
# =========================
async def mensaje_normal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    # Audio
    if update.message.voice:
        file_id = update.message.voice.file_id
        audio_file = await context.bot.get_file(file_id)
        tmp_audio = tempfile.NamedTemporaryFile(suffix=".ogg", delete=False)
        await audio_file.download_to_drive(tmp_audio.name)
        texto = audio_a_texto(tmp_audio.name)
        if not texto:
            await update.message.reply_text("❌ No se pudo reconocer el audio")
            return
    else:
        texto = update.message.text

    # IA
    respuesta = responder_ia(user_id, texto)

    # Texto
    await update.message.reply_text(respuesta)

    # Voz
    archivo_voz = generar_voz(respuesta)
    await update.message.reply_voice(voice=open(archivo_voz,"rb"))

# =========================
# INICIALIZAR BOT
# =========================
if __name__ == "__main__":
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("imagen", imagen))
    app.add_handler(CommandHandler("logo", logo))
    app.add_handler(CommandHandler("video", video))
    app.add_handler(CallbackQueryHandler(botones))
    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, mensaje_normal))

    print("🤖 Bot voz + texto + Pollinations listo")
    app.run_polling()
   
    



