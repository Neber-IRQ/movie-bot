import os
import json
import asyncio
import logging
import aiohttp
import random
import threading
from datetime import datetime
from flask import Flask
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from deep_translator import GoogleTranslator

# ========== إعدادات التسجيل ==========
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ========== إعدادات البوت ==========
BOT_TOKEN = "8865462282:AAFOQwUBO9eMxhMmLOrBrj5_voIjb4_FgDw"
OMDB_API_KEY = "72c327f4"
CHANNEL_ID = "-1001432210812"
OWNER_ID = 355449817

PUBLISHED_FILE = "published_movies.json"

# ========== إعدادات Flask (لمنع خطأ No open ports) ==========
flask_app = Flask(__name__)
application = None  # سيتم تعيينها لاحقاً

@flask_app.route('/')
def index():
    return "🎬 البوت شغال!"

@flask_app.route('/health')
def health():
    return "OK", 200

# ========== دوال التخزين ==========
def load_published_movies():
    if os.path.exists(PUBLISHED_FILE):
        try:
            with open(PUBLISHED_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return []
    return []

def save_published_movie(movie_title, imdb_id):
    published = load_published_movies()
    if not any(p.get("imdb_id") == imdb_id for p in published):
        published.append({
            "title": movie_title,
            "imdb_id": imdb_id,
            "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })
        with open(PUBLISHED_FILE, 'w', encoding='utf-8') as f:
            json.dump(published, f, ensure_ascii=False, indent=2)
        return True
    return False

def is_movie_published(imdb_id):
    published = load_published_movies()
    return any(p.get("imdb_id") == imdb_id for p in published)

# ========== دوال جلب المعلومات ==========
async def get_movie_info(movie_name):
    movie_name = movie_name.strip()
    url = f"https://www.omdbapi.com/?t={movie_name}&apikey={OMDB_API_KEY}&plot=full"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url, headers=headers, timeout=15) as response:
                if response.status != 200:
                    return None
                data = await response.json()
                
                if data.get("Response") == "True":
                    return {
                        "title": data.get("Title", "غير معروف"),
                        "year": data.get("Year", "غير معروف"),
                        "rated": data.get("Rated", "غير معروف"),
                        "released": data.get("Released", "غير معروف"),
                        "runtime": data.get("Runtime", "غير معروف"),
                        "genre": data.get("Genre", "غير معروف"),
                        "director": data.get("Director", "غير معروف"),
                        "writer": data.get("Writer", "غير معروف"),
                        "actors": data.get("Actors", "غير معروف"),
                        "plot": data.get("Plot", "غير معروف"),
                        "imdb_rating": data.get("imdbRating", "غير معروف"),
                        "poster": data.get("Poster", ""),
                        "imdb_id": data.get("imdbID", "")
                    }
                else:
                    return None
        except Exception as e:
            logger.error(f"خطأ في جلب الفيلم {movie_name}: {e}")
            return None

async def get_random_movie_from_omdb():
    keywords = [
        "love", "war", "action", "comedy", "drama", "horror", "thriller",
        "science", "fantasy", "adventure", "crime", "mystery", "romance",
        "family", "animation", "musical", "western", "sports", "history",
        "dream", "star", "moon", "sun", "life", "death", "time", "space"
    ]
    
    keyword = random.choice(keywords)
    url = f"https://www.omdbapi.com/?s={keyword}&type=movie&apikey={OMDB_API_KEY}&page={random.randint(1, 5)}"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url, headers=headers, timeout=15) as response:
                if response.status != 200:
                    return None
                data = await response.json()
                
                if data.get("Response") == "True" and data.get("Search"):
                    movies = data["Search"]
                    random_movie = random.choice(movies)
                    movie_id = random_movie.get("imdbID")
                    detail_url = f"https://www.omdbapi.com/?i={movie_id}&apikey={OMDB_API_KEY}&plot=full"
                    
                    async with session.get(detail_url, headers=headers, timeout=15) as detail_response:
                        if detail_response.status != 200:
                            return None
                        detail_data = await detail_response.json()
                        
                        if detail_data.get("Response") == "True":
                            return detail_data
        except Exception as e:
            logger.error(f"خطأ في جلب فيلم عشوائي: {e}")
            return None
    
    return None

async def get_unpublished_movie(max_attempts=20):
    for attempt in range(max_attempts):
        try:
            movie_data = await get_random_movie_from_omdb()
            if movie_data:
                imdb_id = movie_data.get("imdbID")
                if not is_movie_published(imdb_id):
                    if movie_data.get("Poster") and movie_data.get("Poster") != "N/A":
                        return movie_data
        except Exception as e:
            logger.warning(f"محاولة {attempt+1} فشلت: {e}")
            continue
    return None

# ========== دالة الترجمة ==========
translator = GoogleTranslator(source='en', target='ar')

def translate_to_arabic(text):
    try:
        if text and text != "غير معروف" and text != "N/A":
            return translator.translate(text[:500])
        else:
            return text
    except Exception as e:
        logger.error(f"خطأ في الترجمة: {e}")
        return text

def format_movie_message_arabic(movie_info):
    if not movie_info:
        return "❌ الفيلم غير موجود!"
    
    plot_text = movie_info['plot']
    plot_arabic = translate_to_arabic(plot_text)
    genre_arabic = translate_to_arabic(movie_info['genre'])
    
    return f"""
🎬 {movie_info['title']} ({movie_info['year']})

⭐ التقييم: {movie_info['imdb_rating']}/10
📅 السنة: {movie_info['year']}
⏱ المدة: {movie_info['runtime']}
🎭 النوع: {genre_arabic}
🎥 المخرج: {movie_info['director']}
👥 الممثلون: {movie_info['actors']}
📆 تاريخ الإصدار: {movie_info['released']}
🔞 التصنيف العمري: {movie_info['rated']}

📝 القصة (بالعربية):
{plot_arabic}

🔗 IMDb: https://www.imdb.com/title/{movie_info['imdb_id']}/
"""

# ========== أوامر البوت ==========
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    published = load_published_movies()
    await update.message.reply_text(
        f"🎬 مرحباً! أنا بوت الأفلام\n\n"
        f"📌 الأوامر المتاحة:\n"
        f"/movie اسم_الفيلم - للبحث عن فيلم\n"
        f"/suggest - اقتراح فيلم عشوائي\n"
        f"/publish - نشر فيلم عشوائي في القناة\n"
        f"/stats - عرض عدد الأفلام المنشورة\n\n"
        f"📊 عدد الأفلام المنشورة: {len(published)}"
    )

async def movie(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != OWNER_ID:
        await update.message.reply_text("⛔ هذا الأمر للمالك فقط!")
        return
    
    text = update.message.text
    parts = text.split(" ", 1)
    if len(parts) < 2:
        await update.message.reply_text("⚠️ اكتب اسم الفيلم بعد الأمر.\nمثال: /movie Interstellar")
        return
    
    movie_name = parts[1]
    loading_msg = await update.message.reply_text(f"🔍 جاري البحث عن: {movie_name}...")
    
    movie_info = await get_movie_info(movie_name)
    if not movie_info:
        await loading_msg.edit_text(f"❌ ما لقيت فيلم باسم: {movie_name}")
        return
    
    caption = format_movie_message_arabic(movie_info)
    poster_url = movie_info.get("poster", "")
    
    try:
        if poster_url and poster_url != "N/A":
            short_caption = f"🎬 {movie_info['title']} ({movie_info['year']})"
            await update.message.reply_photo(photo=poster_url, caption=short_caption)
            await update.message.reply_text(text=caption)
        else:
            await update.message.reply_text(text=caption)
        await loading_msg.delete()
    except Exception as e:
        await loading_msg.edit_text(f"❌ حدث خطأ: {str(e)}")

async def suggest(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != OWNER_ID:
        await update.message.reply_text("⛔ هذا الأمر للمالك فقط!")
        return
    
    loading_msg = await update.message.reply_text("🔍 جاري البحث عن فيلم عشوائي...")
    movie_data = await get_unpublished_movie()
    
    if not movie_data:
        await loading_msg.edit_text("❌ ما لقيت فيلم جديد! جرب مرة ثانية.")
        return
    
    movie_info = {
        "title": movie_data.get("Title", "غير معروف"),
        "year": movie_data.get("Year", "غير معروف"),
        "rated": movie_data.get("Rated", "غير معروف"),
        "released": movie_data.get("Released", "غير معروف"),
        "runtime": movie_data.get("Runtime", "غير معروف"),
        "genre": movie_data.get("Genre", "غير معروف"),
        "director": movie_data.get("Director", "غير معروف"),
        "writer": movie_data.get("Writer", "غير معروف"),
        "actors": movie_data.get("Actors", "غير معروف"),
        "plot": movie_data.get("Plot", "غير معروف"),
        "imdb_rating": movie_data.get("imdbRating", "غير معروف"),
        "poster": movie_data.get("Poster", ""),
        "imdb_id": movie_data.get("imdbID", "")
    }
    
    caption = format_movie_message_arabic(movie_info)
    poster_url = movie_info.get("poster", "")
    
    try:
        if poster_url and poster_url != "N/A":
            short_caption = f"🎬 {movie_info['title']} ({movie_info['year']})"
            await update.message.reply_photo(photo=poster_url, caption=short_caption)
            await update.message.reply_text(text=caption)
        else:
            await update.message.reply_text(text=caption)
        await loading_msg.delete()
    except Exception as e:
        await loading_msg.edit_text(f"❌ حدث خطأ: {str(e)}")

async def publish(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != OWNER_ID:
        await update.message.reply_text("⛔ هذا الأمر للمالك فقط!")
        return
    
    loading_msg = await update.message.reply_text("🔍 جاري البحث عن فيلم للنشر...")
    movie_data = await get_unpublished_movie()
    
    if not movie_data:
        await loading_msg.edit_text("❌ ما لقيت فيلم جديد! جرب مرة ثانية.")
        return
    
    movie_info = {
        "title": movie_data.get("Title", "غير معروف"),
        "year": movie_data.get("Year", "غير معروف"),
        "rated": movie_data.get("Rated", "غير معروف"),
        "released": movie_data.get("Released", "غير معروف"),
        "runtime": movie_data.get("Runtime", "غير معروف"),
        "genre": movie_data.get("Genre", "غير معروف"),
        "director": movie_data.get("Director", "غير معروف"),
        "writer": movie_data.get("Writer", "غير معروف"),
        "actors": movie_data.get("Actors", "غير معروف"),
        "plot": movie_data.get("Plot", "غير معروف"),
        "imdb_rating": movie_data.get("imdbRating", "غير معروف"),
        "poster": movie_data.get("Poster", ""),
        "imdb_id": movie_data.get("imdbID", "")
    }
    
    caption = format_movie_message_arabic(movie_info)
    poster_url = movie_info.get("poster", "")
    
    try:
        if poster_url and poster_url != "N/A":
            short_caption = f"🎬 {movie_info['title']} ({movie_info['year']})"
            await context.bot.send_photo(chat_id=CHANNEL_ID, photo=poster_url, caption=short_caption)
            await context.bot.send_message(chat_id=CHANNEL_ID, text=caption)
        else:
            await context.bot.send_message(chat_id=CHANNEL_ID, text=caption)
        
        imdb_id = movie_info.get("imdb_id")
        if imdb_id:
            save_published_movie(movie_info['title'], imdb_id)
        
        published = load_published_movies()
        await loading_msg.edit_text(f"✅ تم نشر {movie_info['title']} في القناة!\n📊 عدد الأفلام المنشورة: {len(published)}")
    except Exception as e:
        await loading_msg.edit_text(f"❌ حدث خطأ في النشر: {str(e)}")

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != OWNER_ID:
        await update.message.reply_text("⛔ هذا الأمر للمالك فقط!")
        return
    
    published = load_published_movies()
    
    if published:
        last_movie = published[-1]
        await update.message.reply_text(
            f"📊 إحصائيات البوت\n\n"
            f"✅ عدد الأفلام المنشورة: {len(published)}\n"
            f"📝 آخر فيلم تم نشره: {last_movie.get('title', 'غير معروف')}\n"
            f"📆 تاريخ النشر: {last_movie.get('date', 'غير معروف')}"
        )
    else:
        await update.message.reply_text(
            f"📊 إحصائيات البوت\n\n"
            f"❌ لم يتم نشر أي فيلم حتى الآن!\n"
            f"استخدم الأمر /publish لنشر أول فيلم."
        )

# ========== مهمة النشر التلقائي ==========
async def auto_publish(app):
    while True:
        try:
            await asyncio.sleep(3600)
            
            logger.info("🔄 جاري النشر التلقائي...")
            movie_data = await get_unpublished_movie()
            
            if movie_data:
                movie_info = {
                    "title": movie_data.get("Title", "غير معروف"),
                    "year": movie_data.get("Year", "غير معروف"),
                    "rated": movie_data.get("Rated", "غير معروف"),
                    "released": movie_data.get("Released", "غير معروف"),
                    "runtime": movie_data.get("Runtime", "غير معروف"),
                    "genre": movie_data.get("Genre", "غير معروف"),
                    "director": movie_data.get("Director", "غير معروف"),
                    "writer": movie_data.get("Writer", "غير معروف"),
                    "actors": movie_data.get("Actors", "غير معروف"),
                    "plot": movie_data.get("Plot", "غير معروف"),
                    "imdb_rating": movie_data.get("imdbRating", "غير معروف"),
                    "poster": movie_data.get("Poster", ""),
                    "imdb_id": movie_data.get("imdbID", "")
                }
                
                caption = format_movie_message_arabic(movie_info)
                poster_url = movie_info.get("poster", "")
                
                if poster_url and poster_url != "N/A":
                    await app.bot.send_photo(chat_id=CHANNEL_ID, photo=poster_url, caption=caption)
                else:
                    await app.bot.send_message(chat_id=CHANNEL_ID, text=caption)
                
                imdb_id = movie_info.get("imdb_id")
                if imdb_id:
                    save_published_movie(movie_info['title'], imdb_id)
                
                published = load_published_movies()
                logger.info(f"✅ تم النشر التلقائي: {movie_info['title']} (إجمالي: {len(published)})")
            else:
                logger.warning("❌ ما لقيت فيلم جديد للنشر التلقائي")
                
        except Exception as e:
            logger.error(f"❌ خطأ في النشر التلقائي: {e}")
            await asyncio.sleep(60)

# ========== نقطة النشر التلقائي (لـ cron-job.org) ==========
@flask_app.route('/publish_now')
def publish_now():
    def do_publish():
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            movie_data = loop.run_until_complete(get_unpublished_movie())
            loop.close()
            
            if movie_data and application is not None:
                movie_info = {
                    "title": movie_data.get("Title", "غير معروف"),
                    "year": movie_data.get("Year", "غير معروف"),
                    "rated": movie_data.get("Rated", "غير معروف"),
                    "released": movie_data.get("Released", "غير معروف"),
                    "runtime": movie_data.get("Runtime", "غير معروف"),
                    "genre": movie_data.get("Genre", "غير معروف"),
                    "director": movie_data.get("Director", "غير معروف"),
                    "writer": movie_data.get("Writer", "غير معروف"),
                    "actors": movie_data.get("Actors", "غير معروف"),
                    "plot": movie_data.get("Plot", "غير معروف"),
                    "imdb_rating": movie_data.get("imdbRating", "غير معروف"),
                    "poster": movie_data.get("Poster", ""),
                    "imdb_id": movie_data.get("imdbID", "")
                }
                
                caption = format_movie_message_arabic(movie_info)
                poster_url = movie_info.get("poster", "")
                
                bot = application.bot
                if poster_url and poster_url != "N/A":
                    bot.send_photo(chat_id=CHANNEL_ID, photo=poster_url, caption=caption)
                else:
                    bot.send_message(chat_id=CHANNEL_ID, text=caption)
                
                imdb_id = movie_info.get("imdb_id")
                if imdb_id:
                    save_published_movie(movie_info['title'], imdb_id)
                
                published = load_published_movies()
                logger.info(f"✅ تم النشر التلقائي: {movie_info['title']} (إجمالي: {len(published)})")
            else:
                logger.warning("❌ ما لقيت فيلم جديد للنشر التلقائي")
        except Exception as e:
            logger.error(f"خطأ في النشر التلقائي: {e}", exc_info=True)
    
    threading.Thread(target=do_publish).start()
    return "✅ جاري النشر..."

# ========== تشغيل البوت ==========
def main():
    global application
    
    application = Application.builder().token(BOT_TOKEN).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("movie", movie))
    application.add_handler(CommandHandler("suggest", suggest))
    application.add_handler(CommandHandler("publish", publish))
    application.add_handler(CommandHandler("stats", stats))
    
    logger.info("🎬 بوت الأفلام جاهز للتشغيل!")
    logger.info("📱 Bot: @AlZalmMoviesBot")
    
    def run_flask():
        flask_app.run(host='0.0.0.0', port=10000)
    
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    logger.info("✅ خادم Flask شغال على المنفذ 10000")
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.create_task(auto_publish(application))
    
    logger.info("🚀 جاري تشغيل البوت (Polling)...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
