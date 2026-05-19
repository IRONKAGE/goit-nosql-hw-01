import os
import zipfile
import shutil
import urllib.request
import sys

# Спробуємо імпортувати Kaggle API. Якщо бібліотеки немає, ми просто перейдемо на urllib
try:
    from kaggle.api.kaggle_api_extended import KaggleApi
    KAGGLE_LIB_AVAILABLE = True
except ImportError:
    KAGGLE_LIB_AVAILABLE = False


class SecureDownloader:
    def __init__(self, dataset_path, dataset_url, data_dir="data"):
        """
        Ініціалізує гібридний завантажувач (Kaggle API + urllib Fallback).
        dataset_path: шлях для API (напр. 'maharshipandya/-spotify-tracks-dataset')
        dataset_url: пряме посилання для urllib
        """
        self.dataset_path = dataset_path
        self.dataset_url = dataset_url
        self.data_dir = data_dir
        self.zip_path = os.path.join(self.data_dir, "dataset_archive.zip")
        os.makedirs(self.data_dir, exist_ok=True)

    def is_valid_zip(self):
        """Перевірка цілісності ZIP-архіву (захист від HTML-заглушок та битих файлів)"""
        if not os.path.exists(self.zip_path) or not zipfile.is_zipfile(self.zip_path):
            return False
        try:
            with zipfile.ZipFile(self.zip_path, 'r') as z:
                if z.testzip() is not None:
                    return False
        except Exception:
            return False
        return True

    def download_progress(self, count, block_size, total_size):
        """Візуалізація прогресу в консолі для urllib"""
        if total_size > 0:
            percent = min(int(count * block_size * 100 / total_size), 100)
            bar = '█' * int(30 * percent / 100) + '░' * (30 - int(30 * percent / 100))
            mb = (count * block_size) / 1048576
            tot_mb = total_size / 1048576
            sys.stdout.write(f"\r     📥 [{bar}] {percent}% | {mb:.1f}/{tot_mb:.1f} MB")
            sys.stdout.flush()
        else:
            kb = (count * block_size) / 1024
            sys.stdout.write(f"\r     📥 Завантажено: {kb:.1f} KB")
            sys.stdout.flush()

    def _download_via_api(self):
        """Внутрішній метод для завантаження через офіційне API"""
        print(f"🤖 Виявлено ключі Kaggle. Ініціалізація офіційного API...")
        print(f"⏳ Завантаження датасету '{self.dataset_path}' у '{self.data_dir}'...")

        api = KaggleApi()
        api.authenticate()
        api.dataset_download_files(self.dataset_path, path=self.data_dir, unzip=False)

        # Перейменовуємо скачаний файл у стандартний dataset_archive.zip
        downloaded_files = [f for f in os.listdir(self.data_dir) if f.endswith('.zip') and f != "dataset_archive.zip"]
        if downloaded_files:
            os.rename(os.path.join(self.data_dir, downloaded_files[0]), self.zip_path)

    def _download_via_urllib(self):
        """Внутрішній метод для завантаження через urllib (Fallback)"""
        print("🌐 Ключі Kaggle відсутні. Ініціалізація прямого завантаження (urllib)...")
        print(f"⏳ Завантаження за посиланням: {self.dataset_url}")

        req = urllib.request.Request(self.dataset_url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=10) as response, open(self.zip_path, 'wb') as out_file:
            total_size = int(response.headers.get('Content-Length', -1))
            block_size = 8192
            count = 0
            while True:
                buffer = response.read(block_size)
                if not buffer:
                    break
                count += 1
                out_file.write(buffer)
                self.download_progress(count, block_size, total_size)
        print() # Новий рядок після прогрес-бару

    def download(self):
        """Головний метод завантаження з розумним маршрутизатором (Smart Router)"""
        print("🔍 Перевірка локальних файлів...")

        # 1. Idempotency: Якщо CSV вже є, нічого не качаємо
        csv_files = [f for f in os.listdir(self.data_dir) if f.endswith('.csv')]
        if csv_files:
            print(f"🔋 Знайдено готовий файл: {csv_files[0]}. Пропускаємо завантаження.")
            return

        # 2. Idempotency: Якщо архів вже є і він цілий
        if os.path.exists(self.zip_path):
            if self.is_valid_zip():
                print("🔋 Архів цілий. Пропускаємо мережевий запит.")
                return
            else:
                print("🪫 Архів пошкоджено. Видаляємо та завантажуємо наново...")
                os.remove(self.zip_path)

        # 3. Smart Router: Визначаємо спосіб завантаження
        has_credentials = bool(os.getenv("KAGGLE_USERNAME") and os.getenv("KAGGLE_KEY"))

        try:
            if has_credentials and KAGGLE_LIB_AVAILABLE:
                self._download_via_api()
            else:
                self._download_via_urllib()

            # 4. Фінальна перевірка цілісності архіву
            if not self.is_valid_zip():
                os.remove(self.zip_path)
                raise Exception("Завантажений файл пошкоджено на етапі передачі або це HTML-заглушка Kaggle.")

            print("✅ Завантаження завершено успішно.")

        except Exception as e:
            print(f"\n⚠️ ПОМИЛКА ЗАВАНТАЖЕННЯ: {e}")
            print("🔄 Активуємо Fallback (Резервний план):")
            print(f"   👉 1. Завантажте датасет вручну: https://www.kaggle.com/datasets/{self.dataset_path}")
            print(f"   👉 2. Покладіть завантажений .zip або .csv у папку '{self.data_dir}/'")
            print(f"   👉 3. Перезапустіть 'make etl'")
            sys.exit(1)

    def extract_atomically(self, target_extensions=('.csv',)):
        """Атомарне розпакування з Flattening (вирівнюванням директорій)"""
        existing_csv = [os.path.join(self.data_dir, f) for f in os.listdir(self.data_dir) if f.endswith('.csv')]
        if existing_csv:
            return existing_csv

        if not self.is_valid_zip():
            raise Exception("❌ Критична помилка: Архів відсутній або пошкоджений.")

        extracted_files = []
        print(f"📦 Аналізуємо вміст архіву...")

        with zipfile.ZipFile(self.zip_path, 'r') as zip_ref:
            data_files = [f for f in zip_ref.namelist() if f.endswith(target_extensions)]

            if not data_files:
                raise Exception(f"В архіві немає файлів з розширеннями {target_extensions}!")

            for file_in_zip in data_files:
                # Flattening: ігноруємо вкладені папки всередині ZIP
                final_path = os.path.join(self.data_dir, os.path.basename(file_in_zip))
                tmp_extract_path = final_path + ".tmp_extract"

                # Відновлена логіка ідемпотентності з правильним додаванням у список
                if os.path.exists(final_path):
                    print(f"⚡ Файл '{os.path.basename(final_path)}' вже готовий. Пропускаємо.")
                    extracted_files.append(final_path)
                    continue

                try:
                    print(f"   ⚙️ Витягуємо '{os.path.basename(file_in_zip)}' атомарно...")
                    with zip_ref.open(file_in_zip) as source, open(tmp_extract_path, "wb") as target:
                        shutil.copyfileobj(source, target)

                    os.replace(tmp_extract_path, final_path) # Атомарний коміт на диск
                    extracted_files.append(final_path)

                except Exception as extract_err:
                    raise Exception(f"Помилка фізичного запису на диск: {extract_err}")
                finally:
                    if os.path.exists(tmp_extract_path):
                        os.remove(tmp_extract_path)

        print("✅ Успіх! Файли витягнуто безпечно.")
        return extracted_files
