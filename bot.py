import asyncio
import aiohttp
import random
import json
import os
from datetime import datetime
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from utils import get_movie_info, format_movie_message_arabic

# ========== إعدادات البوت ==========
BOT_TOKEN = "8865462282:AAFOQwUBO9eMxhMmLOrBrj5_voIjb4_FgDw"
OMDB_API_KEY = "72c327f4"
CHANNEL_ID = "-1001432210812"
OWNER_ID = 355449817

PUBLISHED_FILE = "published_movies.json"

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

# ========== دالة جلب فيلم عشوائي ==========
async def get_random_movie_from_omdb():
    keywords = [
        "love", "war", "action", "comedy", "drama", "horror", "thriller",
        "science", "fantasy", "adventure", "crime", "mystery", "romance",
        "family", "animation", "musical", "western", "sports", "history",
        "dream", "star", "moon", "sun", "life", "death", "time", "space",
        "world", "king", "queen", "lord", "lady", "knight", "warrior"
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
                    print(f"خطأ في الاتصال: {response.status}")
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
        except asyncio.TimeoutError:
            print("انتهى الوقت في جلب الفيلم")
            return None
        except aiohttp.ClientError as e:
            print(f"خطأ في الاتصال: {e}")
            return None
        except Exception as e:
            print(f"خطأ غير متوقع: {e}")
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
            print(f"محاولة {attempt+1} فشلت: {e}")
            continue
    return None

# ========== أوامر البوت ==========
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    published = load_published_movies()
    await update.message.reply_text(
        "🎬 *مرحباً! أنا بوت الأفلام*\n\n"
        "📌 الأوامر المتاحة:\n"
        "/movie اسم_الفيلم - للبحث عن فيلم (مع ترجمة)\n"
        "/search اسم_الفيلم - للبحث والنشر في القناة\n"
        "/suggest - اقتراح فيلم عشوائي\n"
        "/publish - نشر فيلم عشوائي في القناة\n"
        "/stats - عرض عدد الأفلام المنشورة\n\n"
        f"📊 عدد الأفلام المنشورة: {len(published)}",
        parse_mode="Markdown"
    )

async def movie(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != OWNER_ID:
        await update.message.reply_text("⛔ هذا الأمر للمالك فقط!")
        return
    
    text = update.message.text
    parts = text.split(" ", 1)
    if len(parts) < 2:
        await update.message.reply_text("⚠️ اكتب اسم الفيلم بعد الأمر.\nمثال: `/movie Interstellar`")
        return
    
    movie_name = parts[1]
    loading_msg = await update.message.reply_text(f"🔍 جاري البحث عن: *{movie_name}*...", parse_mode="Markdown")
    
    movie_info = await get_movie_info(movie_name)
    if not movie_info:
        await loading_msg.edit_text(f"❌ ما لقيت فيلم باسم: *{movie_name}*", parse_mode="Markdown")
        return
    
    caption = format_movie_message_arabic(movie_info)
    poster_url = movie_info.get("poster", "")
    
    try:
        if poster_url and poster_url != "N/A":
            short_caption = f"🎬 *{movie_info['title']}* ({movie_info['year']})"
            await update.message.reply_photo(photo=poster_url, caption=short_caption, parse_mode="Markdown")
            await update.message.reply_text(text=caption, parse_mode="Markdown", disable_web_page_preview=True)
        else:
            await update.message.reply_text(text=caption, parse_mode="Markdown", disable_web_page_preview=True)
        await loading_msg.delete()
    except Exception as e:
        await loading_msg.edit_text(f"❌ حدث خطأ: {str(e)}")

async def search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != OWNER_ID:
        await update.message.reply_text("⛔ هذا الأمر للمالك فقط!")
        return
    
    text = update.message.text
    parts = text.split(" ", 1)
    if len(parts) < 2:
        await update.message.reply_text("⚠️ اكتب اسم الفيلم بعد الأمر.\nمثال: `/search Interstellar`")
        return
    
    movie_name = parts[1]
    loading_msg = await update.message.reply_text(f"🔍 جاري البحث عن: *{movie_name}*...", parse_mode="Markdown")
    
    movie_info = await get_movie_info(movie_name)
    if not movie_info:
        await loading_msg.edit_text(f"❌ ما لقيت فيلم باسم: *{movie_name}*", parse_mode="Markdown")
        return
    
    caption = format_movie_message_arabic(movie_info)
    poster_url = movie_info.get("poster", "")
    
    try:
        if poster_url and poster_url != "N/A":
            short_caption = f"🎬 *{movie_info['title']}* ({movie_info['year']})"
            await context.bot.send_photo(chat_id=CHANNEL_ID, photo=poster_url, caption=short_caption, parse_mode="Markdown")
            await context.bot.send_message(chat_id=CHANNEL_ID, text=caption, parse_mode="Markdown", disable_web_page_preview=True)
        else:
            await context.bot.send_message(chat_id=CHANNEL_ID, text=caption, parse_mode="Markdown", disable_web_page_preview=True)
        
        imdb_id = movie_info.get("imdb_id")
        if imdb_id:
            save_published_movie(movie_info['title'], imdb_id)
        await loading_msg.edit_text(f"✅ تم نشر *{movie_info['title']}* في القناة!", parse_mode="Markdown")
    except Exception as e:
        await loading_msg.edit_text(f"❌ حدث خطأ في النشر: {str(e)}")

async def suggest(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != OWNER_ID:
        await update.message.reply_text("⛔ هذا الأمر للمالك فقط!")
        return
    
    loading_msg = await update.message.reply_text("🔍 جاري البحث عن فيلم عشوائي...", parse_mode="Markdown")
    movie_data = await get_unpublished_movie()
    
    if not movie_data:
        await loading_msg.edit_text("❌ ما لقيت فيلم جديد! جرب مرة ثانية.", parse_mode="Markdown")
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
            short_caption = f"🎬 *{movie_info['title']}* ({movie_info['year']})"
            await update.message.reply_photo(photo=poster_url, caption=short_caption, parse_mode="Markdown")
            await update.message.reply_text(text=caption, parse_mode="Markdown", disable_web_page_preview=True)
        else:
            await update.message.reply_text(text=caption, parse_mode="Markdown", disable_web_page_preview=True)
        await loading_msg.delete()
    except Exception as e:
        await loading_msg.edit_text(f"❌ حدث خطأ: {str(e)}")

async def publish(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != OWNER_ID:
        await update.message.reply_text("⛔ هذا الأمر للمالك فقط!")
        return
    
    loading_msg = await update.message.reply_text("🔍 جاري البحث عن فيلم للنشر...", parse_mode="Markdown")
    movie_data = await get_unpublished_movie()
    
    if not movie_data:
        await loading_msg.edit_text("❌ ما لقيت فيلم جديد! جرب مرة ثانية.", parse_mode="Markdown")
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
            short_caption = f"🎬 *{movie_info['title']}* ({movie_info['year']})"
            await context.bot.send_photo(chat_id=CHANNEL_ID, photo=poster_url, caption=short_caption, parse_mode="Markdown")
            await context.bot.send_message(chat_id=CHANNEL_ID, text=caption, parse_mode="Markdown", disable_web_page_preview=True)
        else:
            await context.bot.send_message(chat_id=CHANNEL_ID, text=caption, parse_mode="Markdown", disable_web_page_preview=True)
        
        imdb_id = movie_info.get("imdb_id")
        if imdb_id:
            save_published_movie(movie_info['title'], imdb_id)
        
        published = load_published_movies()
        await loading_msg.edit_text(f"✅ تم نشر *{movie_info['title']}* في القناة!\n📊 عدد الأفلام المنشورة: {len(published)}", parse_mode="Markdown")
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
            f"📊 *إحصائيات البوت*\n\n"
            f"✅ عدد الأفلام المنشورة: {len(published)}\n"
            f"📝 آخر فيلم تم نشره: {last_movie.get('title', 'غير معروف')}\n"
            f"📆 تاريخ النشر: {last_movie.get('date', 'غير معروف')}",
            parse_mode="Markdown"
        )
    else:
        await update.message.reply_text(
            f"📊 *إحصائيات البوت*\n\n"
            f"❌ لم يتم نشر أي فيلم حتى الآن!\n"
            f"استخدم الأمر `/publish` لنشر أول فيلم.",
            parse_mode="Markdown"
        )

# ========== تشغيل البوت ==========
def main():
    print("=" * 50)
    print("🎬 بوت الأفلام جاهز للتشغيل!")
    print("📱 Bot: @AlZalmMoviesBot")
    print("=" * 50)
    print("🚀 جاري تشغيل البوت...")
    
    # نستخدم الإعدادات العادية بدون بروكسي
    application = Application.builder().token(BOT_TOKEN).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("movie", movie))
    application.add_handler(CommandHandler("search", search))
    application.add_handler(CommandHandler("suggest", suggest))
    application.add_handler(CommandHandler("publish", publish))
    application.add_handler(CommandHandler("stats", stats))
    
    print("✅ البوت شغال! انتظر الأوامر...")
    print("💡 اكتب /start في البوت")
    print("-" * 50)
    
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()