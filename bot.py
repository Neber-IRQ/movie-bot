import os
import json
import asyncio
import logging
import aiohttp
import random
import re
import threading
import time
from datetime import datetime
from flask import Flask
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from groq import Groq

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
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")

PUBLISHED_FILE = "published_movies.json"

# ========== إعدادات Groq SDK (fallback) ==========
groq_client = Groq(api_key=GROQ_API_KEY, timeout=60.0, max_retries=0)

# ========== إعدادات Flask ==========
flask_app = Flask(__name__)
application = None

@flask_app.route('/')
def index():
    return "Bot is running!"

@flask_app.route('/health')
def health():
    return "OK", 200

@flask_app.route('/test_groq')
def test_groq():
    """فحص الاتصال بـ Groq عبر SDK"""
    try:
        r = groq_client.chat.completions.create(
            model="openai/gpt-oss-120b",
            messages=[{"role": "user", "content": "قل كلمة: مرحبا"}],
            temperature=0.2,
            max_tokens=50,
        )
        result = r.choices[0].message.content
        return f"✅ SDK OK: {result}"
    except Exception as e:
        return f"❌ SDK ERROR: {type(e).__name__}: {str(e)}", 500

@flask_app.route('/test_groq_http')
def test_groq_http():
    """فحص الاتصال بـ Groq عبر HTTP مباشر"""
    try:
        import requests
        resp = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {GROQ_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": "openai/gpt-oss-120b",
                "messages": [{"role": "user", "content": "قل كلمة: مرحبا"}],
                "temperature": 0.2,
                "max_tokens": 50,
            },
            timeout=60,
        )
        if resp.status_code != 200:
            return f"❌ HTTP {resp.status_code}: {resp.text[:300]}", 500
        data = resp.json()
        result = data["choices"][0]["message"]["content"]
        return f"✅ HTTP OK: {result}"
    except Exception as e:
        return f"❌ HTTP ERROR: {type(e).__name__}: {str(e)}", 500

# ========== قاموس ترجمة الأنواع ==========
GENRE_CACHE = {
    "Action": "أكشن",
    "Drama": "دراما",
    "Comedy": "كوميدي",
    "Horror": "رعب",
    "Thriller": "إثارة",
    "Romance": "رومانسي",
    "Sci-Fi": "خيال علمي",
    "Science Fiction": "خيال علمي",
    "Fantasy": "فانتازيا",
    "Adventure": "مغامرة",
    "Animation": "رسوم متحركة",
    "Crime": "جريمة",
    "Mystery": "غموض",
    "Family": "عائلي",
    "War": "حرب",
    "Western": "غربي",
    "Musical": "موسيقي",
    "Biography": "سيرة ذاتية",
    "History": "تاريخي",
    "Sport": "رياضي",
    "Documentary": "وثائقي",
    "Music": "موسيقى",
    "Film-Noir": "نوار",
    "Short": "قصير",
    "Adult": "للبالغين",
    "News": "أخبار",
    "Talk-Show": "برنامج حواري",
    "Game-Show": "برنامج مسابقات",
    "Reality-TV": "واقعي",
}

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
            logger.error(f"Error fetching movie {movie_name}: {e}")
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
            logger.error(f"Error fetching random movie: {e}")
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
            logger.warning(f"Attempt {attempt+1} failed: {e}")
            continue
    return None

# ========== دوال الترجمة ==========
def is_real_arabic(text):
    """يتأكد إن النص عربي فعلاً - 60% على الأقل"""
    if not text or len(text.strip()) < 3:
        return False
    arabic = len(re.findall(r'[\u0600-\u06FF]', text))
    latin = len(re.findall(r'[A-Za-z]', text))
    total = arabic + latin
    if total == 0:
        return False
    return (arabic / total) >= 0.6


def translate_genre(genre_str):
    """ترجمة النوع من القاموس المحلي"""
    if not genre_str or genre_str in ["غير معروف", "N/A"]:
        return genre_str
    parts = [g.strip() for g in genre_str.split(",")]
    translated = [GENRE_CACHE.get(g, g) for g in parts]
    return ", ".join(translated)


def translate_with_http(text, context_type="plot"):
    """
    الترجمة الأساسية عبر HTTP مباشر (أخف وأسرع من SDK):
    - timeout 60 ثانية
    - 3 محاولات مع انتظار متزايد
    - موديلين
    - يرجع None إذا فشل
    """
    if not text or text in ["غير معروف", "N/A", ""]:
        return text
    if is_real_arabic(text):
        return text

    try:
        import requests
    except ImportError:
        logger.error("مكتبة requests غير مثبتة")
        return None

    if context_type == "plot":
        system_prompt = (
            "أنت مترجم سينمائي محترف. ترجم قصة الفيلم إلى العربية الفصحى بأسلوب مشوق. "
            "قواعد صارمة: (1) اكتب بالعربية فقط. (2) ممنوع أي حرف إنجليزي. "
            "(3) لا تكتب مقدمات مثل 'الترجمة:' أو 'Here is'. "
            "(4) أعطني النص المترجم فقط."
        )
    else:
        system_prompt = "ترجم النص إلى العربية الفصحى. اكتب بالعربية فقط بدون مقدمات."

    models = ["openai/gpt-oss-120b", "llama-3.1-8b-instant"]

    for model in models:
        for attempt in range(3):
            try:
                if attempt > 0:
                    time.sleep(attempt * 2)

                resp = requests.post(
                    "https://api.groq.com/openai/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {GROQ_API_KEY}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": model,
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": text}
                        ],
                        "temperature": 0.2,
                        "max_tokens": 1024,
                    },
                    timeout=60,
                )

                if resp.status_code != 200:
                    logger.error(f"❌ HTTP {resp.status_code}: {resp.text[:200]}")
                    continue

                data = resp.json()
                translated = data["choices"][0]["message"]["content"].strip()

                for prefix in ["الترجمة:", "Translation:", "Here is", "بالعربية:"]:
                    if translated.startswith(prefix):
                        translated = translated[len(prefix):].strip()

                if is_real_arabic(translated):
                    logger.info(f"✅ ترجمة HTTP ناجحة ({context_type}, {model}, محاولة {attempt+1})")
                    return translated
                else:
                    logger.warning(f"⚠️ النص مو عربي كفاية ({model}): {translated[:60]}")

            except Exception as e:
                logger.error(f"❌ HTTP فشل ({model}, try {attempt+1}): {type(e).__name__}: {e}")

    return None


def translate_with_ai(text, context_type="plot", max_retries=3):
    """
    نسخة احتياطية عبر SDK (إذا HTTP فشل)
    """
    if not text or text in ["غير معروف", "N/A", ""]:
        return text
    if is_real_arabic(text):
        return text

    if context_type == "plot":
        system_prompt = (
            "أنت مترجم سينمائي محترف. ترجم قصة الفيلم إلى العربية الفصحى بأسلوب مشوق. "
            "قواعد صارمة: (1) اكتب بالعربية فقط. (2) ممنوع أي حرف إنجليزي. "
            "(3) لا تكتب مقدمات مثل 'الترجمة:' أو 'Here is'. "
            "(4) أعطني النص المترجم فقط."
        )
    else:
        system_prompt = "ترجم النص إلى العربية الفصحى. اكتب بالعربية فقط بدون مقدمات."

    models = ["openai/gpt-oss-120b", "llama-3.1-8b-instant"]

    for model in models:
        for attempt in range(max_retries):
            try:
                if attempt > 0:
                    time.sleep(attempt * 2)

                response = groq_client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": text}
                    ],
                    temperature=0.2,
                    max_tokens=1024,
                )

                if response.choices and len(response.choices) > 0:
                    content = response.choices[0].message.content
                    if content and content.strip():
                        translated = content.strip()

                        for prefix in ["الترجمة:", "Translation:", "Here is", "بالعربية:"]:
                            if translated.startswith(prefix):
                                translated = translated[len(prefix):].strip()

                        if is_real_arabic(translated):
                            logger.info(f"✅ ترجمة SDK ناجحة ({context_type}, {model}, محاولة {attempt+1})")
                            return translated
                        else:
                            logger.warning(f"⚠️ النص مو عربي كفاية ({model}): {translated[:60]}")

            except Exception as e:
                logger.error(f"❌ SDK فشل ({model}, محاولة {attempt+1}): {type(e).__name__}: {e}")

    return None


def format_movie_message_arabic(movie_info):
    if not movie_info:
        return "الفيلم غير موجود!"

    # ✅ HTTP هو الأساس (أسرع وأخف)
    plot_arabic = translate_with_http(movie_info['plot'], "plot")

    # 🔄 إذا HTTP فشل، نجرب SDK
    if plot_arabic is None:
        logger.info("🔄 HTTP فشل، نجرب SDK...")
        plot_arabic = translate_with_ai(movie_info['plot'], "plot")

    genre_arabic = translate_genre(movie_info['genre'])

    if plot_arabic is None:
        plot_arabic = "📝 القصة غير متوفرة بالعربية حالياً."

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

📝 القصة:
{plot_arabic}

🔗 IMDb: https://www.imdb.com/title/{movie_info['imdb_id']}/
"""

# ========== أوامر البوت ==========
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    published = load_published_movies()
    await update.message.reply_text(
        f"مرحباً! أنا بوت الأفلام\n\n"
        f"الأوامر المتاحة:\n"
        f"/movie اسم_الفيلم - للبحث عن فيلم\n"
        f"/suggest - اقتراح فيلم عشوائي\n"
        f"/publish - نشر فيلم عشوائي في القناة\n"
        f"/stats - عرض عدد الأفلام المنشورة\n\n"
        f"عدد الأفلام المنشورة: {len(published)}"
    )

async def movie(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != OWNER_ID:
        await update.message.reply_text("هذا الأمر للمالك فقط!")
        return

    text = update.message.text
    parts = text.split(" ", 1)
    if len(parts) < 2:
        await update.message.reply_text("اكتب اسم الفيلم بعد الأمر.\nمثال: /movie Interstellar")
        return

    movie_name = parts[1]
    loading_msg = await update.message.reply_text(f"جاري البحث عن: {movie_name}...")

    movie_info = await get_movie_info(movie_name)
    if not movie_info:
        await loading_msg.edit_text(f"ما لقيت فيلم باسم: {movie_name}")
        return

    caption = format_movie_message_arabic(movie_info)
    poster_url = movie_info.get("poster", "")

    try:
        if poster_url and poster_url != "N/A":
            short_caption = f"{movie_info['title']} ({movie_info['year']})"
            await update.message.reply_photo(photo=poster_url, caption=short_caption)
            await update.message.reply_text(text=caption)
        else:
            await update.message.reply_text(text=caption)
        await loading_msg.delete()
    except Exception as e:
        await loading_msg.edit_text(f"حدث خطأ: {str(e)}")

async def suggest(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != OWNER_ID:
        await update.message.reply_text("هذا الأمر للمالك فقط!")
        return

    loading_msg = await update.message.reply_text("جاري البحث عن فيلم عشوائي...")
    movie_data = await get_unpublished_movie()

    if not movie_data:
        await loading_msg.edit_text("ما لقيت فيلم جديد! جرب مرة ثانية.")
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
            short_caption = f"{movie_info['title']} ({movie_info['year']})"
            await update.message.reply_photo(photo=poster_url, caption=short_caption)
            await update.message.reply_text(text=caption)
        else:
            await update.message.reply_text(text=caption)
        await loading_msg.delete()
    except Exception as e:
        await loading_msg.edit_text(f"حدث خطأ: {str(e)}")

async def publish(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != OWNER_ID:
        await update.message.reply_text("هذا الأمر للمالك فقط!")
        return

    loading_msg = await update.message.reply_text("جاري البحث عن فيلم للنشر...")
    movie_data = await get_unpublished_movie()

    if not movie_data:
        await loading_msg.edit_text("ما لقيت فيلم جديد! جرب مرة ثانية.")
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
            short_caption = f"{movie_info['title']} ({movie_info['year']})"
            await context.bot.send_photo(chat_id=CHANNEL_ID, photo=poster_url, caption=short_caption)
            await context.bot.send_message(chat_id=CHANNEL_ID, text=caption)
        else:
            await context.bot.send_message(chat_id=CHANNEL_ID, text=caption)

        imdb_id = movie_info.get("imdb_id")
        if imdb_id:
            save_published_movie(movie_info['title'], imdb_id)

        published = load_published_movies()
        await loading_msg.edit_text(f"تم نشر {movie_info['title']} في القناة!\nعدد الأفلام المنشورة: {len(published)}")
    except Exception as e:
        await loading_msg.edit_text(f"حدث خطأ في النشر: {str(e)}")

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != OWNER_ID:
        await update.message.reply_text("هذا الأمر للمالك فقط!")
        return

    published = load_published_movies()

    if published:
        last_movie = published[-1]
        await update.message.reply_text(
            f"إحصائيات البوت\n\n"
            f"عدد الأفلام المنشورة: {len(published)}\n"
            f"آخر فيلم تم نشره: {last_movie.get('title', 'غير معروف')}\n"
            f"تاريخ النشر: {last_movie.get('date', 'غير معروف')}"
        )
    else:
        await update.message.reply_text(
            f"إحصائيات البوت\n\n"
            f"لم يتم نشر أي فيلم حتى الآن!\n"
            f"استخدم الأمر /publish لنشر أول فيلم."
        )

# ========== مهمة النشر التلقائي ==========
async def auto_publish(app):
    while True:
        try:
            await asyncio.sleep(10800)

            logger.info("Auto-publishing...")
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
                logger.info(f"Auto-published: {movie_info['title']} (total: {len(published)})")
            else:
                logger.warning("No new movie found for auto-publish")

        except Exception as e:
            logger.error(f"Auto-publish error: {e}")
            await asyncio.sleep(60)

# ========== نقطة النشر التلقائي ==========
@flask_app.route('/publish_now')
def publish_now():
    def do_publish():
        try:
            movie_data = asyncio.run(get_unpublished_movie())

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
                    asyncio.run(bot.send_photo(chat_id=CHANNEL_ID, photo=poster_url, caption=caption))
                else:
                    asyncio.run(bot.send_message(chat_id=CHANNEL_ID, text=caption))

                imdb_id = movie_info.get("imdb_id")
                if imdb_id:
                    save_published_movie(movie_info['title'], imdb_id)

                published = load_published_movies()
                logger.info(f"Published via /publish_now: {movie_info['title']} (total: {len(published)})")
            else:
                logger.warning("No new movie found for /publish_now")
        except Exception as e:
            logger.error(f"publish_now error: {e}", exc_info=True)

    threading.Thread(target=do_publish).start()
    return "Publishing..."

# ========== تشغيل البوت ==========
def main():
    global application

    if not GROQ_API_KEY:
        logger.error("⚠️ GROQ_API_KEY غير موجود في Environment Variables!")

    application = Application.builder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("movie", movie))
    application.add_handler(CommandHandler("suggest", suggest))
    application.add_handler(CommandHandler("publish", publish))
    application.add_handler(CommandHandler("stats", stats))

    logger.info("Bot is starting...")
    logger.info("Bot: @AlZalmMoviesBot")

    def run_flask():
        flask_app.run(host='0.0.0.0', port=10000)

    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    logger.info("Flask server running on port 10000")

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.create_task(auto_publish(application))

    logger.info("Starting bot (Polling)...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
