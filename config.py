import os
import logging
from dotenv import load_dotenv

# Загружаем переменные окружения из .env файла
load_dotenv()

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# URLs API
MEMEPAD_API_URL = "https://api.memepad.io/v1"
REACTIONS_API_URL = "https://api.reactions.io/v1"
STONFI_API_URL = "https://api.stonfi.io/v1"

# Telegram API и авторизация
TELEGRAM_API_ID = os.getenv("TELEGRAM_API_ID")
TELEGRAM_API_HASH = os.getenv("TELEGRAM_API_HASH")
TELEGRAM_PHONE = os.getenv("TELEGRAM_PHONE")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# Конфигурация базы данных
DATABASE_URL = os.getenv(
    "DATABASE_URL", 
    f"mysql+pymysql://{os.getenv('MYSQL_USER', 'root')}:{os.getenv('MYSQL_PASSWORD', '')}@{os.getenv('MYSQL_HOST', 'localhost')}:{os.getenv('MYSQL_PORT', '3306')}/{os.getenv('MYSQL_DATABASE', 'cryptxspider')}"
)

# Параметры для анализа скама
SCAM_THRESHOLD = 0.75  # Вероятность скама выше 75% считается скамом
MIN_CHANNEL_AGE_DAYS = 14  # Минимальный возраст канала для доверия
SCAN_INTERVAL = 600  # Интервал сканирования в секундах (10 минут)

# Telegram-каналы для мониторинга
MONITORED_CHANNELS = [
    "tonblum",      # Блюм
    "memescope",    # Memescope
    "ton_diamonds", # TON Diamonds
    "toncoin_rus",  # TON Community RU
    "tonx_dev",     # TON Dev Community
    "stTON_chat",   # stTON
]

# Ключевые слова для поиска новых токенов
TOKEN_KEYWORDS = [
    "jetton", "токен", "token", "блюм", "блум", "blum", 
    "memepad", "airdrop", "дроп", "эирдроп", "TON", "тон"
]

# Шаблоны для поиска скам-проектов
SCAM_PATTERNS = [
    r"(?i)100x",
    r"(?i)1000x",
    r"guaranteed.{0,20}profit",
    r"без.{0,10}риска",
    r"without.{0,10}risk",
    r"(?i)pump.{0,5}dump",
    r"(?i)скам",
    r"(?i)scam.{0,5}alert"
]

# Параметры автоматического обнаружения каналов
CHANNEL_DISCOVERY = {
    "enabled": True,                 # Включить автоматическое обнаружение
    "max_channels_per_run": 5,       # Максимальное количество новых каналов за одно сканирование
    "min_relevance_score": 0.6,      # Минимальная оценка релевантности для добавления канала
    "max_monitored_channels": 50,    # Максимальное количество мониторимых каналов
    "scan_frequency_hours": 6,       # Частота поиска новых каналов (в часах)
    "cleanup_frequency_days": 7,     # Частота очистки неактивных каналов (в днях)
}

# Ключевые слова для поиска каналов
CHANNEL_SEARCH_KEYWORDS = [
    "TON", "toncoin", "ton crypto", "ton blockchain", 
    "jetton", "memepad", "meme coin", "блюм", "блум", 
    "tonblum", "ton diamond", "tonx"
]

# Шаблоны для поиска ссылок на Telegram в сообщениях
TELEGRAM_LINK_PATTERNS = [
    r"(?:https?://)?t\.me/([a-zA-Z0-9_]+)",
    r"@([a-zA-Z0-9_]{5,})",
    r"(?:https?://)?t\.me/\+([a-zA-Z0-9_-]+)",
    r"(?:https?://)?t\.me/joinchat/([a-zA-Z0-9_-]+)"
]

# Факторы для оценки релевантности канала
RELEVANCE_FACTORS = {
    "token_mentions": 0.4,       # Вес упоминаний токенов в сообщениях
    "members_count": 0.2,        # Вес количества участников
    "activity": 0.15,            # Вес активности канала
    "description_relevance": 0.15, # Вес релевантности описания
    "age": 0.1                   # Вес возраста канала
}

# OpenAI API для генерации отчетов
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GPT_MODEL = "gpt-4"

# API URLs
MEMEPAD_BASE_URL = "https://memepad.io/api"
REACTIONS_BASE_URL = "https://reactions.llc/api"
STONFI_BASE_URL = "https://api.ston.fi/v1"
