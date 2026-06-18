import aiohttp
from config import OMDB_API_KEY
from deep_translator import GoogleTranslator

translator = GoogleTranslator(source='en', target='ar')

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
            print(f"خطأ في جلب الفيلم {movie_name}: {e}")
            return None

def translate_to_arabic(text):
    try:
        if text and text != "غير معروف" and text != "N/A":
            return translator.translate(text[:500])
        else:
            return text
    except Exception as e:
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
