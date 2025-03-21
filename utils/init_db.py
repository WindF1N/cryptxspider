#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sys
import logging
from dotenv import load_dotenv

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger('init_db')

# Добавляем родительский каталог в пути импорта для импорта модулей
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Загрузка переменных окружения
load_dotenv()

from sqlalchemy import create_engine, inspect
from sqlalchemy.exc import SQLAlchemyError

def get_mysql_url():
    """Получение URL для подключения к MySQL из переменных окружения"""
    # Проверяем, есть ли готовый URL
    db_url = os.getenv('DATABASE_URL')
    if db_url and 'mysql' in db_url:
        return db_url
    
    # Собираем URL из компонентов
    host = os.getenv('MYSQL_HOST', 'localhost')
    port = os.getenv('MYSQL_PORT', '3306')
    user = os.getenv('MYSQL_USER', 'root')
    password = os.getenv('MYSQL_PASSWORD', '')
    database = os.getenv('MYSQL_DATABASE', 'cryptxspider')
    
    return f"mysql+pymysql://{user}:{password}@{host}:{port}/{database}"

def init_db():
    """
    Функция инициализации базы данных, вызываемая из main.py
    
    Returns:
        bool: True если инициализация прошла успешно, иначе False
    """
    logger.info("Вызов инициализации базы данных")
    return init_mysql_db()

def init_mysql_db():
    """Инициализация базы данных MySQL"""
    # Импортируем модели данных, это также инициализирует Base
    from models.db import Base
    
    # Получаем URL для подключения к MySQL
    db_url = get_mysql_url()
    logger.info(f"Инициализация MySQL базы данных с URL: {db_url}")
    
    try:
        # Создаем движок SQLAlchemy для MySQL
        engine = create_engine(db_url)
        
        # Проверяем подключение к базе данных
        try:
            connection = engine.connect()
            connection.close()
            logger.info("Подключение к MySQL успешно установлено")
        except SQLAlchemyError as e:
            logger.error(f"Не удалось подключиться к MySQL: {str(e)}")
            logger.info("Убедитесь, что MySQL сервер запущен и база данных создана")
            return False
        
        # Создаем все таблицы в базе данных
        Base.metadata.create_all(engine)
        
        # Проверяем, что все таблицы созданы
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        
        expected_tables = ['jetton', 'transaction', 'holder', 'telegram_message', 
                          'potential_token', 'telegram_channel']
        
        missing_tables = [table for table in expected_tables if table not in tables]
        
        if missing_tables:
            logger.warning(f"Следующие таблицы не были созданы: {', '.join(missing_tables)}")
            return False
        
        logger.info(f"Созданы следующие таблицы: {', '.join(tables)}")
        logger.info("Инициализация базы данных MySQL успешно завершена")
        
        return True
    
    except Exception as e:
        logger.error(f"Ошибка при инициализации базы данных: {str(e)}")
        return False

def main():
    """Основная функция для инициализации базы данных"""
    logger.info("Начало инициализации базы данных")
    
    success = init_mysql_db()
    
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main()) 