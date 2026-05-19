import os
import streamlit as st
import pandas as pd
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()

@st.cache_resource
def get_mongo_client(env_type):
    if env_type == "Хмара (Atlas)":
        uri = os.getenv("MONGO_CLOUD_URI")
    else:
        uri = os.getenv("MONGO_LOCAL_URI")

    client = MongoClient(uri)
    client.admin.command('ping')
    return client

st.set_page_config(page_title="Spotify BI Dashboard", layout="wide", page_icon="🎵")

# --- Бічна панель ---
st.sidebar.title("🎛 Налаштування БД")
env_choice = st.sidebar.radio("Середовище MongoDB:", ["Локально (Docker)", "Хмара (Atlas)"])

try:
    client = get_mongo_client(env_choice)
    db = client["spotify"]
    tracks = db["tracks"]
    st.sidebar.success("✅ Підключено успішно!")
except Exception as e:
    st.sidebar.error("❌ Помилка підключення")
    st.stop()

# --- Головний екран ---
st.title("🎵 Spotify Insights: Аналітична Платформа")

col1, col2, col3 = st.columns(3)
col1.metric("Всього треків", tracks.count_documents({}))
col2.metric("Унікальних жанрів", len(tracks.distinct("track_genre")))
col3.metric("База підключена", env_choice)

st.divider()

# --- Інтерактивний модуль 1: Настрої ---
st.subheader("📊 Розподіл треків за настроєм")
pipeline_mood = [
    {"$addFields": {
        "mood": {
            "$switch": {
                "branches": [
                    {"case": {"$and": [{"$gte": ["$audio_features.valence", 0.5]}, {"$gte": ["$audio_features.energy", 0.5]}]}, "then": "Happy (Усміхнений)"},
                    {"case": {"$and": [{"$lt": ["$audio_features.valence", 0.5]}, {"$gte": ["$audio_features.energy", 0.5]}]}, "then": "Angry (Агресивний)"},
                    {"case": {"$and": [{"$gte": ["$audio_features.valence", 0.5]}, {"$lt": ["$audio_features.energy", 0.5]}]}, "then": "Calm (Спокійний)"},
                    {"case": {"$and": [{"$lt": ["$audio_features.valence", 0.5]}, {"$lt": ["$audio_features.energy", 0.5]}]}, "then": "Sad (Сумний)"}
                ],
                "default": "Unknown"
            }
        }
    }},
    {"$group": {"_id": "$mood", "Кількість": {"$sum": 1}}},
    {"$sort": {"Кількість": -1}}
]
mood_data = list(tracks.aggregate(pipeline_mood))
if mood_data:
    df_mood = pd.DataFrame(mood_data).rename(columns={"_id": "Настрій"}).set_index("Настрій")
    st.bar_chart(df_mood, color="#1DB954")

st.divider()

# --- Інтерактивний модуль 2: Найбільш танцювальні жанри ---
st.subheader("💃 Найбільш танцювальні жанри (мінімум 100 треків)")
min_tracks = st.slider("Мінімальна кількість треків у жанрі:", 10, 500, 100)

pipeline_dance = [
    {"$group": {
        "_id": "$track_genre",
        "track_count": {"$sum": 1},
        "Танцювальність": {"$avg": "$audio_features.danceability"}
    }},
    {"$match": {"track_count": {"$gte": min_tracks}}},
    {"$sort": {"Танцювальність": -1}},
    {"$limit": 10}
]
dance_data = list(tracks.aggregate(pipeline_dance))
if dance_data:
    df_dance = pd.DataFrame(dance_data).rename(columns={"_id": "Жанр"}).set_index("Жанр")
    st.line_chart(df_dance[["Танцювальність"]])

# --- Інтерактивний модуль 3: Топ-10 виконавців ---
st.subheader("🏆 Топ-10 виконавців за популярністю")
min_artist_tracks = st.slider("Мінімальна кількість треків артиста:", 1, 50, 5)

pipeline_artists = [
    {"$unwind": "$artists"},
    {"$group": {
        "_id": "$artists",
        "Кількість треків": {"$sum": 1},
        "Популярність": {"$avg": "$popularity"}
    }},
    {"$match": {"Кількість треків": {"$gte": min_artist_tracks}}},
    {"$sort": {"Популярність": -1}},
    {"$limit": 10}
]
artists_data = list(tracks.aggregate(pipeline_artists))
if artists_data:
    df_artists = pd.DataFrame(artists_data).rename(columns={"_id": "Артист"}).set_index("Артист")
    st.bar_chart(df_artists["Популярність"], color="#ff4d4d")

st.divider()

# --- Інтерактивний модуль 4: Розумний пошук (Вечірка vs Фонова робота) ---
st.subheader("🎧 Розумний пошук треків (Advanced MQL Filters)")
col_a, col_b = st.columns([1, 3])

with col_a:
    track_type = st.radio("Оберіть мету прослуховування:", ["🎉 Для вечірки", "💻 Для фонової роботи"])
    limit_tracks = st.number_input("Кількість результатів:", min_value=5, max_value=50, value=10)

with col_b:
    if track_type == "🎉 Для вечірки":
        query = {
            "audio_features.danceability": {"$gt": 0.7},
            "audio_features.energy": {"$gt": 0.7},
            "duration_ms": {"$gte": 180000, "$lte": 300000}
        }
    else:
        query = {
            "audio_features.loudness": {"$lt": -10},
            "audio_features.speechiness": {"$lt": 0.1},
            "audio_features.instrumentalness": {"$gt": 0.5},
            "explicit": False
        }

    # Виконуємо запит та конвертуємо в Pandas DataFrame
    found_tracks = list(tracks.find(
        query,
        {"_id": 0, "track_name": 1, "artists": 1, "track_genre": 1, "popularity": 1}
    ).sort("popularity", -1).limit(limit_tracks))

    if found_tracks:
        # Робимо красиве відображення масиву артистів
        df_tracks = pd.DataFrame(found_tracks)
        df_tracks["artists"] = df_tracks["artists"].apply(lambda x: ", ".join(x))
        df_tracks.rename(columns={
            "track_name": "Назва треку",
            "artists": "Виконавці",
            "track_genre": "Жанр",
            "popularity": "Популярність"
        }, inplace=True)

        st.dataframe(df_tracks, use_container_width=True, hide_index=True)
    else:
        st.warning("Треків за такими критеріями не знайдено.")

st.divider()

# --- Інтерактивний модуль 5: Виявлення аномалій (Window Functions) ---
st.subheader("🚀 Аналіз аномалій: Нетипові треки (Window Functions)")

st.markdown("""
*Цей модуль делегує важкі математичні обчислення на сторону MongoDB.
За допомогою `$setWindowFields` база розраховує середнє значення та стандартне відхилення (`stdDevPop`)
для кожного жанру "на льоту", знаходячи треки, чий темп перевищує поріг (Mean + 2 * StdDev).*
""")

col_x, col_y = st.columns([1, 3])

with col_x:
    # Отримуємо список жанрів для інтерактивного фільтра
    all_genres = tracks.distinct("track_genre")
    selected_genre = st.selectbox("Оберіть жанр для пошуку аномалій:", ["Всі жанри"] + sorted(all_genres))

    st.info(f"Шукаємо треки з аномально високим темпом (BPM).")

with col_y:
    # Будуємо динамічний пайплайн
    pipeline_outliers = []

    # Якщо обрано конкретний жанр, фільтруємо ДО важких обчислень (оптимізація)
    if selected_genre != "Всі жанри":
        pipeline_outliers.append({"$match": {"track_genre": selected_genre}})

    # Додаємо магію Window Functions
    pipeline_outliers.extend([
        {
            "$setWindowFields": {
                "partitionBy": "$track_genre",
                "output": {
                    "avg_tempo": {"$avg": "$audio_features.tempo"},
                    "std_tempo": {"$stdDevPop": "$audio_features.tempo"}
                }
            }
        },
        {
            "$addFields": {
                "outlier_threshold": {"$add": ["$avg_tempo", {"$multiply": [2, "$std_tempo"]}]}
            }
        },
        {
            "$match": {
                "$expr": {"$gt": ["$audio_features.tempo", "$outlier_threshold"]}
            }
        },
        {
            "$project": {
                "_id": 0,
                "track_name": 1,
                "artists": 1,
                "track_genre": 1,
                "tempo": {"$round": ["$audio_features.tempo", 1]},
                "threshold": {"$round": ["$outlier_threshold", 1]}
            }
        },
        {"$sort": {"tempo": -1}},
        {"$limit": 50} # Обмеження для UI
    ])

    outliers_data = list(tracks.aggregate(pipeline_outliers))

    if outliers_data:
        df_outliers = pd.DataFrame(outliers_data)
        df_outliers["artists"] = df_outliers["artists"].apply(lambda x: ", ".join(x))
        df_outliers.rename(columns={
            "track_name": "Назва треку",
            "artists": "Виконавці",
            "track_genre": "Жанр",
            "tempo": "Темп (BPM)",
            "threshold": "Поріг аномалії (BPM)"
        }, inplace=True)

        st.dataframe(df_outliers, use_container_width=True, hide_index=True)
    else:
        st.success("У цьому жанрі немає аномально швидких треків!")
