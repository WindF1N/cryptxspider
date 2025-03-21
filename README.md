# CryptxSpiderAI

MVP системы для анализа токенов в сети TON и выявления скам-проектов на основе данных Memepad и Telegram.

## Особенности

- 🔍 **Мониторинг Telegram-каналов** для выявления новых токенов, которые еще не появились на Memepad
- 🚨 **Анализ скам-проектов** на Memepad с использованием машинного обучения и множества факторов
- 🤖 **Интеграция с GPT-4** для генерации детальных отчетов о рисках
- 📊 **Асинхронная обработка данных** для анализа большого количества токенов
- 🔔 **Уведомления через Telegram-бота** о новых токенах и скам-проектах
- 🔎 **Автоматическое обнаружение новых каналов** для поиска токенов на ранних стадиях
- 📡 **Оценка релевантности каналов** для повышения точности анализа
- 💾 **Хранение данных в MySQL** для высокой производительности и надежности

## Архитектура

Система состоит из следующих компонентов:

1. **MemepadParser** - асинхронный парсер для получения данных с API Memepad
2. **TelegramSpider** - парсер Telegram-каналов для поиска новых токенов
3. **ScamAnalyzer** - анализатор скам-проектов с использованием ML и эвристик
4. **NotificationBot** - система уведомлений через Telegram-бота
5. **Database Models** - модели для хранения данных о токенах и результатах анализа

## Установка и запуск

### Требования

- Python 3.8+
- MySQL 5.7+ или MariaDB 10.3+
- Токен Telegram-бота (получить у @BotFather)
- API ID и хэш для Telegram API (получить на https://my.telegram.org/apps)
- API ключ OpenAI для генерации отчетов через GPT-4

### Установка

1. Клонировать репозиторий
```bash
git clone https://github.com/yourusername/cryptxspider.git
cd cryptxspider
```

2. Создать виртуальное окружение
```bash
python -m venv venv
source venv/bin/activate  # На Windows: venv\Scripts\activate
```

3. Установить зависимости
```bash
pip install -r requirements.txt
```

4. Создать пользователя и базу данных MySQL
```bash
mysql -u root -p
```

В MySQL выполнить:
```sql
CREATE DATABASE cryptxspider CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'cryptxspider'@'localhost' IDENTIFIED BY 'your_strong_password';
GRANT ALL PRIVILEGES ON cryptxspider.* TO 'cryptxspider'@'localhost';
FLUSH PRIVILEGES;
EXIT;
```

5. Создать файл `.env` с необходимыми переменными окружения (см. пример `.env.example`)
```bash
TELEGRAM_API_ID=your_api_id
TELEGRAM_API_HASH=your_api_hash
TELEGRAM_PHONE=your_phone_number
TELEGRAM_BOT_TOKEN=your_bot_token
OPENAI_API_KEY=your_openai_key

# MySQL настройки
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_USER=cryptxspider
MYSQL_PASSWORD=your_strong_password
MYSQL_DATABASE=cryptxspider
```

6. Инициализировать базу данных
```bash
python utils/init_db.py
```

### Миграция с SQLite на MySQL

Если у вас уже есть данные в SQLite, вы можете перенести их в MySQL:

```bash
python utils/migrate_to_mysql.py --sqlite-path путь_к_файлу_sqlite.db
```

### Запуск

```bash
python main.py
```

## Использование

1. Запустите систему
2. Подпишитесь на уведомления в боте, отправив `/subscribe all`
3. Для просмотра статистики мониторинга каналов, отправьте `/stats`
4. Система будет автоматически сканировать Telegram-каналы и Memepad, а также искать новые каналы для мониторинга
5. Вы будете получать уведомления о новых токенах, скам-проектах и обнаруженных релевантных каналах

## Лицензия

MIT 