# ==============================================================================
# MLOps & Data Engineering Orchestrator (Task 1: MongoDB) by IRONKAGE
# ==============================================================================

# 1. Експорт змінних середовища
ifneq (,$(wildcard ./.env))
	include .env
	export $(shell awk -F= '/^[a-zA-Z_]/ {print $$1}' .env)
endif

# 2. Кросплатформна підтримка ОС (Windows / Linux / MacOS) та Docker
ifeq ($(OS),Windows_NT)
	OPEN_CMD := start ""
	DOCKER_START_CMD := start "" "C:\Program Files\Docker\Docker\Docker Desktop.exe"
	WAIT_DOCKER := powershell -Command "do { Write-Host '⏳ Чекаю на старт Docker...'; Start-Sleep -Seconds 3 } while (!(docker info 2>$$null))"
else
	UNAME_S := $(shell uname -s)
	ifeq ($(UNAME_S),Linux)
		OPEN_CMD := xdg-open
		DOCKER_START_CMD := systemctl --user start docker-desktop || sudo systemctl start docker
		WAIT_DOCKER := until docker info >/dev/null 2>&1; do echo "⏳ Чекаю на старт Docker..."; sleep 3; done
	endif
	ifeq ($(UNAME_S),Darwin)
		OPEN_CMD := open
		DOCKER_START_CMD := open -a Docker
		WAIT_DOCKER := until docker info >/dev/null 2>&1; do echo "⏳ Чекаю на старт Docker..."; sleep 3; done
	endif
endif

# 3. Змінні середовища
VENV := venv
PYTHON_CMD := python3.12
PYTHON := $(VENV)/bin/python
PIP := $(VENV)/bin/pip
STREAMLIT := $(VENV)/bin/streamlit

# Кольори
CYAN := \033[36m
GREEN := \033[32m
YELLOW := \033[33m
RESET := \033[0m
GRAY := \033[90m

# ------------------------------------------------------------------------------
# 🧠 SMART ROUTING & DYNAMIC HELP: Динамічний вибір бази та тексту
# ------------------------------------------------------------------------------
ifeq ($(strip $(ACTIVE_ENV)),cloud)
	TARGET_DB_URI := $(MONGO_CLOUD_URI)
	ENV_LABEL := ☁️  Хмара (MongoDB Atlas)
	# ☁️ Тимчасовий (ефемерний) контейнер для хмари
	MONGOSH_CMD := docker run --rm -i mongo:8.0.23 mongosh --quiet

	HELP_DB_UP      := $(GRAY)[Пропустити] Не потрібно для хмари (Atlas працює 24/7)$(RESET)
	HELP_UI         := $(GRAY)[Пропустити] Використовуйте веб-інтерфейс MongoDB Atlas$(RESET)
	HELP_DB_DOWN    := $(GRAY)[Пропустити] Не потрібно для хмари$(RESET)
	HELP_DEEP_CLEAN := ПОВНЕ очищення (Лише Python кеші, Docker не задіяний)
else
	TARGET_DB_URI := $(MONGO_LOCAL_URI)
	ENV_LABEL := 🖥️  Локально (Docker Replica Set)
	# 🖥️ Використовуємо існуючий контейнер для локальної БД
	MONGOSH_CMD := docker exec -i mongo-primary mongosh --quiet

	HELP_DB_UP      := Підняти MongoDB (Replica Set) та MongoExpress у Docker
	HELP_UI         := Відкрити графічну адмінку Mongo Express у браузері
	HELP_DB_DOWN    := Зупинити контейнери (Дані ЗБЕРІГАЮТЬСЯ у volume)
	HELP_DEEP_CLEAN := ПОВНЕ очищення (Знищити БД, Volumes та Образи Docker)
endif

.PHONY: help setup env docker-ensure db-up db-down ui etl transform queries dashboard clean deep-clean

help:
	@echo "$(CYAN)============================================================================================$(RESET)"
	@echo "$(GREEN)🎧 Spotify Analytics Platform - Data Engineering Makefile | $(YELLOW)$(ENV_LABEL)$(RESET)"
	@echo "$(CYAN)============================================================================================$(RESET)"
	@echo "Послідовність виконання проекту:"
	@echo "  $(YELLOW)[КРОК 0] Підготовка середовища:$(RESET)"
	@echo "    $(GREEN)make env$(RESET)           - Створити базовий .env файл (якщо його немає)"
	@echo "    $(GREEN)make setup$(RESET)         - Створити віртуальне середовище та встановити залежності"
	@echo "--------------------------------------------------------------------------------------------"
	@echo "  $(YELLOW)[КРОК 1] Інфраструктура бази даних:$(RESET)"
	@echo "    $(GREEN)make db-up$(RESET)         - $(HELP_DB_UP)"
	@echo "    $(GREEN)make ui$(RESET)            - $(HELP_UI)"
	@echo "--------------------------------------------------------------------------------------------"
	@echo "  $(YELLOW)[КРОК 2] Завдання 1 (ETL та Схема):$(RESET)"
	@echo "    $(GREEN)make etl$(RESET)           - Завантажити дані з Kaggle та залити в MongoDB (tracks_raw)"
	@echo "    $(GREEN)make transform$(RESET)     - Виконати Aggregation Pipeline для трансформації схеми (tracks)"
	@echo "--------------------------------------------------------------------------------------------"
	@echo "  $(YELLOW)[КРОК 3] Завдання 2-4 (Аналітика та Індекси):$(RESET)"
	@echo "    $(GREEN)make queries$(RESET)       - Виконати всі аналітичні запити (Частини 2, 3 та 4)"
	@echo "    $(GREEN)make dashboard$(RESET)     - Запустити інтерактивний BI-дашборд на Streamlit"
	@echo "--------------------------------------------------------------------------------------------"
	@echo "  $(YELLOW)[КРОК 4] Керування та очищення:$(RESET)"
	@echo "    $(GREEN)make db-down$(RESET)       - $(HELP_DB_DOWN)"
	@echo "    $(GREEN)make clean$(RESET)         - Очистити кеші Python та тимчасові файли завантажень"
	@echo "    $(GREEN)make deep-clean$(RESET)    - $(HELP_DEEP_CLEAN)"
	@echo "$(CYAN)============================================================================================$(RESET)"

env:
	@if [ ! -f .env ]; then \
		echo "ACTIVE_ENV=local" > .env; \
		echo "MONGO_USER=admin" >> .env; \
		echo "MONGO_PASS=SuperSecretPassword2026!" >> .env; \
		echo "ME_AUTH_USER=admin" >> .env; \
		echo "ME_AUTH_PASS=admin" >> .env; \
		echo "MONGO_LOCAL_URI=mongodb://127.0.0.1:27017,127.0.0.1:27018,127.0.0.1:27019/spotify?replicaSet=spotify_rs" >> .env; \
		echo "MONGO_CLOUD_URI=mongodb+srv://<user>:<password>@cluster.mongodb.net/" >> .env; \
		echo "$(GREEN)✅ Файл .env створено! (Згенеровано для Replica Set)$(RESET)"; \
	else \
		echo "$(YELLOW)⚡ Файл .env вже існує. Пропускаємо.$(RESET)"; \
	fi

# ------------------------------------------------------------------------------
# АВТОМАТИЗАЦІЯ PYTHON (Авто-встановлення та VENV)
# ------------------------------------------------------------------------------
ensure-python:
	@echo "$(CYAN)🔍 Перевірка наявності $(PYTHON_CMD)...$(RESET)"
	@command -v $(PYTHON_CMD) >/dev/null 2>&1 || { \
		echo "$(YELLOW)⚙️ $(PYTHON_CMD) не знайдено. Запускаю автоматичне встановлення...$(RESET)"; \
		if [ "$(OS)" = "Windows_NT" ] || [ -n "$$WINDIR" ]; then \
			echo "$(CYAN)🪟 Виявлено Windows. Встановлюю через PowerShell (winget)...$(RESET)"; \
			powershell -NoProfile -Command "winget install --id Python.Python.3.12 -e --silent --accept-package-agreements --accept-source-agreements"; \
		elif [ "$(UNAME_S)" = "Darwin" ]; then \
			echo "$(CYAN)🍏 Виявлено macOS. Встановлюю через Homebrew...$(RESET)"; \
			brew install python@3.12; \
		elif [ "$(UNAME_S)" = "Linux" ]; then \
			echo "$(CYAN)🐧 Виявлено Linux. Встановлюю через APT...$(RESET)"; \
			sudo apt-get update && sudo apt-get install -y python3.12 python3.12-venv; \
		else \
			echo "$(YELLOW)❌ Невідома ОС. Встановіть Python 3.12 вручну з python.org$(RESET)" && exit 1; \
		fi; \
	}
	@echo "$(GREEN)✅ $(PYTHON_CMD) присутній у системі!$(RESET)"

setup: env ensure-python
	@echo "$(CYAN)📦 Створення віртуального середовища ($(PYTHON_CMD))...$(RESET)"
	$(PYTHON_CMD) -m venv $(VENV)
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements.txt
	@echo "$(GREEN)✅ Віртуальне оточення готове!$(RESET)"

# ------------------------------------------------------------------------------
# АВТОМАТИЗАЦІЯ DOCKER (Перевірка, запуск та очікування)
# ------------------------------------------------------------------------------
docker-ensure:
	@echo "$(CYAN)[*] Перевірка наявності Docker...$(RESET)"
	@docker --version >/dev/null 2>&1 || (echo "$(YELLOW)❌ Критична помилка: Docker не встановлено на цьому комп'ютері!$(RESET)\n👉 Будь ласка, завантажте та встановіть Docker Desktop: https://www.docker.com/products/docker-desktop/" && exit 1)
	@echo "$(CYAN)[*] Перевірка стану Docker...$(RESET)"
	@docker info >/dev/null 2>&1 || (echo "$(YELLOW)[!] Docker встановлено, але вимкнено. Виконую автоматичний запуск...$(RESET)" && $(DOCKER_START_CMD) && $(WAIT_DOCKER))
	@echo "$(GREEN)[+] Docker готовий до роботи!$(RESET)"

db-up: docker-ensure
	@if [ "$(strip $(ACTIVE_ENV))" = "cloud" ]; then \
		echo "$(YELLOW)⚡ Активне середовище - хмара (Atlas). Docker інфраструктура не потрібна.$(RESET)"; \
	else \
		echo "$(CYAN)🐳 Запуск інфраструктури (MongoDB + MongoExpress) через Docker Compose V2...$(RESET)"; \
		docker compose up -d; \
		echo "$(GREEN)✅ MongoDB Cluster доступний на 127.0.0.1:27017, 27018, 27019!$(RESET)"; \
		echo "$(GREEN)✅ Mongo Express (Адмінка) доступна на http://127.0.0.1:8081 (admin:admin)$(RESET)"; \
	fi

db-down: docker-ensure
	@if [ "$(strip $(ACTIVE_ENV))" = "cloud" ]; then \
		echo "$(YELLOW)⚡ Активне середовище - хмара (Atlas). Docker інфраструктура не запущена.$(RESET)"; \
	else \
		echo "$(YELLOW)🛑 Зупинка інфраструктури...$(RESET)"; \
		docker compose down; \
		echo "$(GREEN)✅ Контейнери зупинено (дані збережено у volume).$(RESET)"; \
	fi

# Кросплатформне відкриття UI
ui:
	@if [ "$(strip $(ACTIVE_ENV))" = "cloud" ]; then \
		echo "$(YELLOW)⚡ Для хмарного середовища використовуйте веб-інтерфейс MongoDB Atlas: https://cloud.mongodb.com$(RESET)"; \
	else \
		echo "$(CYAN)🌐 Відкриваємо Mongo Express у браузері...$(RESET)"; \
		$(OPEN_CMD) http://127.0.0.1:8081; \
	fi

etl:
	@echo "$(CYAN)⏳ Запуск ETL-ядра (Завантаження даних у tracks_raw)...$(RESET)"
	@echo "$(YELLOW)📍 Цільова БД: $(ENV_LABEL)$(RESET)"
	$(PYTHON) scripts/01_load_data.py

transform:
	@echo "$(CYAN)🔄 Трансформація схеми (tracks_raw -> tracks)...$(RESET)"
	@echo "$(YELLOW)📍 Цільова БД: $(ENV_LABEL)$(RESET)"
	$(MONGOSH_CMD) "$(TARGET_DB_URI)" < scripts/02_transform.js

queries:
	@echo "$(CYAN)📊 Запуск аналітичних запитів...$(RESET)"
	@echo "$(YELLOW)📍 Цільова БД: $(ENV_LABEL)$(RESET)"
	@echo "\n$(YELLOW)--- Частина 2: Базові запити ---$(RESET)"
	@$(MONGOSH_CMD) "$(TARGET_DB_URI)" < queries/part2_queries.js
	@echo "\n$(YELLOW)--- Частина 3: Агрегації ---$(RESET)"
	@$(MONGOSH_CMD) "$(TARGET_DB_URI)" < queries/part3_aggregations.js
	@echo "\n$(YELLOW)--- Частина 4: Аналіз індексів ---$(RESET)"
	@$(MONGOSH_CMD) "$(TARGET_DB_URI)" < queries/part4_indexes.js

dashboard:
	@echo "$(CYAN)📈 Запуск Streamlit Dashboard...$(RESET)"
	$(STREAMLIT) run dashboard/app.py

clean:
	@echo "$(YELLOW)🧹 Очищення тимчасових файлів...$(RESET)"
	rm -rf __pycache__ .pytest_cache
	find . -type d -name "__pycache__" -exec rm -r {} +
	find . -type f -name "*.pyc" -delete
	rm -f data/*.tmp_extract
	@echo "$(GREEN)✅ Проект очищено!$(RESET)"

# Хардкорне знищення всього
deep-clean: clean
	@if [ "$(strip $(ACTIVE_ENV))" = "cloud" ]; then \
		echo "$(YELLOW)⚠️ ПОВНЕ ОЧИЩЕННЯ: Знищено локальні кеші. Хмарна БД не зачеплена.$(RESET)"; \
	else \
		echo "$(YELLOW)⚠️ ПОВНЕ ОЧИЩЕННЯ: Видалення БД, Томів (Volumes) та Мереж...$(RESET)"; \
		docker compose down -v; \
		echo "$(GREEN)✅ Інфраструктуру повністю знищено. Пам'ять звільнено!$(RESET)"; \
	fi

# Хак для ігнорування невідомих аргументів
%:
	@:
