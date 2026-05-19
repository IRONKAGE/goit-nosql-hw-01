import os
import pandas as pd
from pymongo import MongoClient
from tqdm import tqdm
from dotenv import load_dotenv

# Імпортуємо наше універсальне Ядро
from etl_core import SecureDownloader

load_dotenv()

# --- 1. ETL Фаза: Безпечне завантаження ---
KAGGLE_PATH = "maharshipandya/-spotify-tracks-dataset"
KAGGLE_URL = "https://www.kaggle.com/api/v1/datasets/download/maharshipandya/-spotify-tracks-dataset"
DATA_DIR = "data"

print("--- Фаза 1: Отримання даних ---")
downloader = SecureDownloader(dataset_path=KAGGLE_PATH, dataset_url=KAGGLE_URL, data_dir=DATA_DIR)
downloader.download()
extracted = downloader.extract_atomically(target_extensions=('.csv',))

# Динамічно отримуємо шлях до розпакованого CSV (захист від зміни імені файлу в архіві)
CSV_PATH = extracted[0]

# --- 2. Database Фаза: Підключення та Трансформація ---
print("\n--- Фаза 2: Завантаження в MongoDB ---")
# Додано .strip() для очищення від випадкових пробілів у .env
active_env = os.getenv("ACTIVE_ENV", "cloud").strip()

# Fallback-логіка: якщо рев'юер використовує старий формат .env з методички (MONGO_URI)
MONGO_URI = os.environ.get("MONGO_LOCAL_URI") if active_env == "local" else (os.environ.get("MONGO_URI") or os.environ.get("MONGO_CLOUD_URI"))

client = MongoClient(MONGO_URI)
db = client["spotify"]
db["tracks_raw"].drop() # Ідемпотентність запуску

df = pd.read_csv(CSV_PATH)
print(f"Завантажуємо {len(df)} треків...")

# Архітектурне очищення (видаляємо артефакт індексу Pandas, якщо він є)
if "Unnamed: 0" in df.columns:
    df.drop(columns=["Unnamed: 0"], inplace=True)

df["explicit"] = df["explicit"].astype(bool)

int_cols = ["popularity", "duration_ms", "key", "mode", "time_signature"]
for col in int_cols: df[col] = df[col].astype(int)

float_cols = ["danceability", "energy", "loudness", "speechiness", "acousticness", "instrumentalness", "liveness", "valence", "tempo"]
for col in float_cols: df[col] = df[col].astype(float)

# Прибираємо биті записи
query = df["artists"].isna() | df["track_name"].isna()
records = df[~query].to_dict("records")

# Вставляємо батчами по 1000, щоб не перевантажити RAM кластера
for i in tqdm(range(0, len(records), 1000), desc="Вставка батчів"):
    db["tracks_raw"].insert_many(records[i : i + 1000])

print(f"\n✅ Готово! Документів у базі: {db['tracks_raw'].count_documents({})}")
