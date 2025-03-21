#!/usr/bin/env python
# -*- coding: utf-8 -*-

import argparse
import os
import sys
import logging
from dotenv import load_dotenv
from sqlalchemy import create_engine, MetaData, Table, select, insert
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import SQLAlchemyError

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger('migrate_to_mysql')

# Загрузка переменных окружения
load_dotenv()

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

def migrate_data(sqlite_path, batch_size=100):
    """
    Миграция данных из SQLite в MySQL
    
    Args:
        sqlite_path (str): Путь к файлу SQLite
        batch_size (int): Размер пакета для переноса данных
    """
    # Подключение к SQLite
    sqlite_url = f"sqlite:///{sqlite_path}"
    sqlite_engine = create_engine(sqlite_url)
    sqlite_metadata = MetaData()
    sqlite_metadata.reflect(bind=sqlite_engine)
    sqlite_session = sessionmaker(bind=sqlite_engine)()
    
    # Подключение к MySQL
    mysql_url = get_mysql_url()
    mysql_engine = create_engine(mysql_url)
    mysql_metadata = MetaData()
    mysql_metadata.reflect(bind=mysql_engine)
    mysql_session = sessionmaker(bind=mysql_engine)()
    
    # Список таблиц для миграции
    tables = ['jetton', 'transaction', 'holder', 'telegram_message', 
              'potential_token', 'telegram_channel']
    
    try:
        # Перенос данных из каждой таблицы
        for table_name in tables:
            logger.info(f"Начало миграции таблицы '{table_name}'")
            
            # Пропускаем таблицу, если её нет в SQLite
            if table_name not in sqlite_metadata.tables:
                logger.warning(f"Таблица '{table_name}' отсутствует в SQLite, пропускаем")
                continue
            
            # Пропускаем таблицу, если её нет в MySQL
            if table_name not in mysql_metadata.tables:
                logger.warning(f"Таблица '{table_name}' отсутствует в MySQL, пропускаем")
                continue
            
            # Получаем объекты таблиц
            sqlite_table = Table(table_name, sqlite_metadata, autoload_with=sqlite_engine)
            mysql_table = Table(table_name, mysql_metadata, autoload_with=mysql_engine)
            
            # Получаем общий список колонок
            common_columns = set(c.name for c in sqlite_table.columns).intersection(
                set(c.name for c in mysql_table.columns)
            )
            
            # Получаем количество записей
            count_query = select([sqlite_table.count()])
            total_records = sqlite_engine.execute(count_query).scalar()
            
            if total_records == 0:
                logger.info(f"Таблица '{table_name}' в SQLite пуста, пропускаем")
                continue
            
            # Передача данных пакетами
            offset = 0
            migrated = 0
            
            while offset < total_records:
                # Выбираем данные из SQLite
                select_stmt = select([sqlite_table]).limit(batch_size).offset(offset)
                rows = list(sqlite_engine.execute(select_stmt))
                
                if not rows:
                    break
                
                # Подготавливаем данные для вставки в MySQL
                data_to_insert = []
                for row in rows:
                    row_dict = {col: row[col] for col in common_columns if col in row.keys()}
                    data_to_insert.append(row_dict)
                
                # Вставляем данные в MySQL
                if data_to_insert:
                    try:
                        mysql_session.execute(mysql_table.insert(), data_to_insert)
                        mysql_session.commit()
                        migrated += len(data_to_insert)
                        logger.info(f"Перенесено {migrated}/{total_records} записей из '{table_name}'")
                    except SQLAlchemyError as e:
                        mysql_session.rollback()
                        logger.error(f"Ошибка при вставке данных в MySQL: {str(e)}")
                        # Попытка вставить по одной записи
                        for row_dict in data_to_insert:
                            try:
                                mysql_session.execute(mysql_table.insert(), [row_dict])
                                mysql_session.commit()
                                migrated += 1
                            except SQLAlchemyError as e:
                                mysql_session.rollback()
                                logger.error(f"Не удалось перенести запись: {str(e)}")
                
                offset += batch_size
            
            logger.info(f"Миграция таблицы '{table_name}' завершена. Перенесено {migrated} записей")
        
        logger.info("Миграция успешно завершена")
        
    except Exception as e:
        logger.error(f"Произошла ошибка во время миграции: {str(e)}")
        return False
    finally:
        # Закрываем сессии
        sqlite_session.close()
        mysql_session.close()
    
    return True

def main():
    """Основная функция для запуска миграции"""
    parser = argparse.ArgumentParser(description='Миграция данных из SQLite в MySQL')
    parser.add_argument('--sqlite-path', required=True, help='Путь к файлу SQLite')
    parser.add_argument('--batch-size', type=int, default=100, help='Размер пакета для миграции')
    
    args = parser.parse_args()
    
    logger.info(f"Начало миграции из {args.sqlite_path} в MySQL")
    
    if not os.path.exists(args.sqlite_path):
        logger.error(f"Файл SQLite не найден: {args.sqlite_path}")
        return 1
    
    success = migrate_data(args.sqlite_path, args.batch_size)
    
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main()) 