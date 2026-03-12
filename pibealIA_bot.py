import os
import requests
import imageio
import tempfile
from gtts import gTTS
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, MessageHandler, ContextTypes, filters

# =========================
# VARIABLES DE ENTORNO
# =========================
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")  # Opcional
HF_TOKEN = os.getenv("HF_TOKEN")          # Opcional
NEWSAPI_KEY = os.getenv("NEWSAPI_KEY")    # Opcional

# =========================
# MEMORIA Y ELECCIONES
# =========================
memoria_ia = {}
elecciones_imagen = {}  # {user_id: [urls]}
elecciones_video = {}   # {user_id: [urls seleccionadas]}

# =========================
# FUNCIONES IA
# =========================
def responder_ia(user_id, mensaje):
    if user_id not in memoria_ia:
        memoria_ia[user_id] = []

    memoria_ia[user_id].append({"role": "user", "content": mensaje})
    respuesta = None

    if GROQ_API_KEY:
        try:
            from groq import Groq
            client = Groq(api_key=GROQ_API_KEY)
            res = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=memoria_ia[user_id]
            )
            respuesta = res.choices[0].message.content
        except Exception as e:
            respuesta = f"Error Groq: {e}"
    elif HF_TOKEN:
        try:
            url = "https://api-inference.huggingface.co/models/gpt2"
            headers = {"Authorization": f"Bearer {HF_TOKEN}"}
            data = {"inputs": mensaje}
            r = requests.post(url, headers=headers, json=data)
            if r.status_code == 200:
                respuesta = r.json()[0]["generated_text"]
            else:
                respuesta = f"Error HF: {r.status_code}"
        except Exception as e:
            respuesta = f"Error HF: {e}"
    else:
        respuesta = f"IA dice: {mensaje}"

    memoria_ia[user_id].append({"role": "assistant", "content": respuesta})
    return respuesta

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
# VOZ CON gTTS
# =========================
async def enviar_voz(update, texto):
    tts = gTTS(text=texto, lang='es')
    with tempfile.NamedTemporaryFile(suffix=".mp3") as tmp:
        tts.save(tmp.name)
        await update.message.reply_voice(voice=open(tmp.name, "rb"))

# =========================
# TELEGRAM HANDLERS
# =========================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    mensaje = (
        "🤖 Bot IA + Pollinations + Voz DEFINITIVO\n\n"
        "Escribe directamente tu mensaje o usa:\n"
        "/imagen <descripción> | <estilo opcional>\n"
        "/logo <descripción> | <estilo opcional>\n"
        "/video <prompt1>|<prompt2>|..."
    )
    await update.message.reply_text(mensaje)

async def imagen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("❌ Escribe la descripción. Ej: /imagen Gato astronauta | estilo anime")
        return
    texto = " ".join(context.args)
    partes = texto.split("|")
    prompt = partes[0].strip()
    estilo = partes[1].strip() if len(partes) > 1 else None

    urls = generar_varias_imagenes(prompt, estilo, cantidad=5)
    elecciones_imagen[update.message.from_user.id] = urls

    botones = [[InlineKeyboardButton(f"Opción {i+1}", callback_data=f"seleccion|{i}")] for i in range(len(urls))]
    markup = InlineKeyboardMarkup(botones)
    await update.message.reply_text("Selecciona la imagen que más te guste:", reply_markup=markup)

async def logo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("❌ Escribe la descripción. Ej: /logo Logo robot | estilo futurista")
        return
    texto = " ".join(context.args)
    partes = texto.split("|")
    prompt = partes[0].strip()
    estilo = partes[1].strip() if len(partes) > 1 else None

    urls = generar_varias_imagenes(prompt, estilo, cantidad=5)
    elecciones_imagen[update.message.from_user.id] = urls

    botones = [[InlineKeyboardButton(f"Opción {i+1}", callback_data=f"seleccion|{i}")] for i in range(len(urls))]
    markup = InlineKeyboardMarkup(botones)
    await update.message.reply_text("Selecciona el logo que más te guste:", reply_markup=markup)

async def video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("❌ Escribe al menos un prompt. Ej: /video gato|perro|robot")
        return
    prompts = " ".join(context.args).split("|")
    urls = []
    for p in prompts:
        urls.extend(generar_varias_imagenes(p.strip(), cantidad=2))
    elecciones_video[update.message.from_user.id] = urls

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
            await query.edit_message_text("❌ Error: No hay imágenes para seleccionar.")
            return
        url = elecciones_imagen[user_id][index]
        if user_id not in elecciones_video:
            elecciones_video[user_id] = []
        elecciones_video[user_id].append(url)

        r = requests.get(url)
        if r.status_code == 200:
            with tempfile.NamedTemporaryFile(suffix=".png") as tmp:
                tmp.write(r.content)
                tmp.flush()
                await query.message.reply_photo(photo=open(tmp.name, "rb"))
        await query.edit_message_text("✅ Has seleccionado esta imagen para tu colección.")

# =========================
# MENSAJES NORMALES SIN /
# =========================
async def mensaje_normal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    texto = update.message.text
    user_id = update.message.from_user.id

    # Detecta si el usuario pide noticias
    if "noticia" in texto.lower() or "últimas noticias" in texto.lower():
        if NEWSAPI_KEY:
            url = f"https://newsapi.org/v2/top-headlines?country=mx&apiKey={NEWSAPI_KEY}&pageSize=3"
            r = requests.get(url).json()
            if r.get("status") == "ok":
                noticias = r.get("articles", [])
                mensaje = "📰 Últimas noticias:\n\n"
                for n in noticias:
                    mensaje += f"- {n['title']} ({n['source']['name']})\n{n['url']}\n\n"
            else:
                mensaje = "❌ No se pudieron obtener noticias ahora."
            await update.message.reply_text(mensaje)
            return

    # Si no son noticias, responder con IA
    respuesta = responder_ia(user_id, texto)
    await update.message.reply_text(respuesta)
    await enviar_voz(update, respuesta)

# =========================
# INICIALIZAR BOT
# =========================
if __name__ == "__main__":
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    # Comandos
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("imagen", imagen))
    app.add_handler(CommandHandler("logo", logo))
    app.add_handler(CommandHandler("video", video))
    app.add_handler(CallbackQueryHandler(botones))

    # Mensajes normales
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, mensaje_normal))

    print("🤖 BOT IA + Pollinations + Voz + Noticias FINAL ACTIVO")
    app.run_polling()
   


