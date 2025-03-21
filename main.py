#!/usr/bin/env python3
import os
import sys
import asyncio
import logging
import signal
from datetime import datetime, timedelta

# Добавляем родительский каталог в пути импорта
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import SCAN_INTERVAL
from utils.init_db import init_db
from memepad.parser import MemepadParser
from telegram.spider import TelegramSpider
from analyzer.scam_detector import ScamDetector
from bot.notification import NotificationBot
from models.db import session, Jetton, PotentialToken, TelegramChannel

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("cryptxspider.log")
    ]
)
logger = logging.getLogger(__name__)

# Глобальные переменные для объектов системы
memepad_parser = None
telegram_spider = None
scam_detector = None
notification_bot = None

async def setup():
    """Инициализация компонентов системы."""
    global memepad_parser, telegram_spider, scam_detector, notification_bot
    
    logger.info("Инициализация базы данных...")
    init_db()
    
    logger.info("Создание экземпляров классов...")
    memepad_parser = MemepadParser()
    telegram_spider = TelegramSpider()
    scam_detector = ScamDetector()
    notification_bot = NotificationBot()
    
    # Подключение к API
    await telegram_spider.connect()
    await notification_bot.start()
    
    logger.info("Система инициализирована успешно")

async def scan_tokens():
    """Сканирование токенов из Memepad и их анализ."""
    try:
        # Получаем список токенов из Memepad
        tokens = await memepad_parser.get_new_tokens()
        logger.info(f"Получено {len(tokens)} токенов из Memepad")
        
        for token in tokens:
            # Анализируем токен на скам
            is_scam, confidence = await scam_detector.analyze_token(token)
            
            if is_scam:
                logger.warning(f"Обнаружен скам-токен: {token['name']} с уверенностью {confidence:.2f}")
                # Отправляем уведомление о скам-токене
                await notification_bot.send_scam_alert(token, confidence)
            else:
                logger.info(f"Проверен легитимный токен: {token['name']} ({1.0 - confidence:.2f})")
            
            # Проверяем наличие социальных каналов в Telegram
            if token.get('socials'):
                social_stats = await telegram_spider.parse_token_chats(token['socials'])
                if social_stats:
                    logger.info(f"Проанализированы соц. каналы для токена {token['name']}: {len(social_stats)} каналов")
    
    except Exception as e:
        logger.error(f"Ошибка при сканировании токенов: {str(e)}")

async def check_external_tokens():
    """Анализ внешних источников для поиска потенциальных новых токенов."""
    try:
        # Ищем новые каналы в Telegram
        await telegram_spider.discover_new_channels(notification_bot)
        
        # Получаем потенциальные токены из Telegram-каналов
        potential_tokens = await telegram_spider.parse_external_chats()
        
        if not potential_tokens:
            logger.info("Новых потенциальных токенов не обнаружено")
            return
        
        logger.info(f"Обнаружено {len(potential_tokens)} потенциальных токенов в Telegram")
        
        # Проверяем на наличие в Memepad
        for token in potential_tokens:
            # Проверяем, есть ли токен уже в нашей базе
            existing = session.query(Jetton).filter(
                (Jetton.name.ilike(f"%{token.name}%")) | 
                (Jetton.ticker.ilike(f"%{token.name}%"))
            ).first()
            
            if existing:
                logger.info(f"Токен {token.name} уже есть в базе, пропускаем")
                continue
            
            # Проверяем, был ли найден в Memepad
            found_on_memepad = await memepad_parser.search_token(token.name)
            
            if found_on_memepad:
                logger.info(f"Токен {token.name} найден на Memepad, добавляем в базу")
                # Обновляем запись в БД
                token.found_on_memepad = True
                token.confidence_score = 0.9
                session.commit()
            else:
                # Высылаем уведомление о потенциальном новом токене
                if token.confidence_score > 0.5:
                    logger.info(f"Отправляем уведомление о новом потенциальном токене: {token.name}")
                    await notification_bot.send_new_token_alert(token)
    
    except Exception as e:
        logger.error(f"Ошибка при проверке внешних токенов: {str(e)}")

async def clean_old_channels():
    """Очистка неактивных каналов с низкой релевантностью."""
    try:
        # Получаем каналы с низкой релевантностью, которые давно не сканировались
        month_ago = datetime.utcnow() - timedelta(days=30)
        old_channels = session.query(TelegramChannel).filter(
            TelegramChannel.is_active == True,
            TelegramChannel.relevance_score < 0.3,
            TelegramChannel.last_scanned_at < month_ago
        ).all()
        
        if old_channels:
            logger.info(f"Удаление {len(old_channels)} неактивных каналов с низкой релевантностью")
            for channel in old_channels:
                channel.is_active = False
            session.commit()
    
    except Exception as e:
        logger.error(f"Ошибка при очистке старых каналов: {str(e)}")

async def channel_stats():
    """Вывод статистики по каналам."""
    try:
        # Получаем общее количество каналов
        total_channels = session.query(TelegramChannel).count()
        active_channels = session.query(TelegramChannel).filter(TelegramChannel.is_active == True).count()
        high_relevance = session.query(TelegramChannel).filter(
            TelegramChannel.is_active == True,
            TelegramChannel.relevance_score >= 0.7
        ).count()
        
        logger.info(f"Статистика каналов: всего {total_channels}, активных {active_channels}, высокорелевантных {high_relevance}")
        
        # Топ-5 каналов по релевантности
        top_channels = session.query(TelegramChannel).filter(
            TelegramChannel.is_active == True
        ).order_by(TelegramChannel.relevance_score.desc()).limit(5).all()
        
        if top_channels:
            logger.info(f"Топ-5 каналов по релевантности:")
            for i, channel in enumerate(top_channels, 1):
                logger.info(f"{i}. @{channel.username} - {channel.relevance_score:.2f} - {channel.token_mentions_count} упоминаний")
    
    except Exception as e:
        logger.error(f"Ошибка при получении статистики каналов: {str(e)}")

async def main_loop():
    """Основной цикл работы программы."""
    await setup()
    
    # Обработчик сигналов для корректного завершения
    def signal_handler():
        logger.info("Получен сигнал завершения, закрываем соединения...")
        loop.create_task(shutdown())
    
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, signal_handler)
    
    logger.info("Запуск основного цикла программы...")
    
    while True:
        try:
            # Сканируем токены из Memepad
            await scan_tokens()
            
            # Проверяем внешние источники
            await check_external_tokens()
            
            # Очищаем старые каналы раз в неделю
            if datetime.now().weekday() == 0:  # По понедельникам
                await clean_old_channels()
            
            # Выводим статистику каналов раз в день
            if datetime.now().hour == 0:  # В полночь
                await channel_stats()
            
            # Ожидаем указанный интервал
            logger.info(f"Ожидание {SCAN_INTERVAL} секунд до следующего сканирования...")
            await asyncio.sleep(SCAN_INTERVAL)
        
        except Exception as e:
            logger.error(f"Ошибка в основном цикле: {str(e)}")
            await asyncio.sleep(60)  # Ждем минуту при ошибке

async def shutdown():
    """Корректное завершение работы программы."""
    logger.info("Завершение работы системы...")
    
    # Закрываем соединения
    if telegram_spider:
        await telegram_spider.close()
    
    if notification_bot:
        await notification_bot.stop()
    
    # Закрываем сессию БД
    session.close()
    
    logger.info("Система остановлена")
    sys.exit(0)

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    
    try:
        loop.run_until_complete(main_loop())
    except KeyboardInterrupt:
        logger.info("Получен сигнал прерывания клавиатуры")
    finally:
        loop.run_until_complete(shutdown())
        loop.close()
