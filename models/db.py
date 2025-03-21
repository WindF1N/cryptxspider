from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, ForeignKey, JSON, Text, create_engine, types
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker
from datetime import datetime
import json
import os
from dotenv import load_dotenv

load_dotenv()

def get_database_url():
    """Получение URL для подключения к базе данных из переменных окружения"""
    # Проверяем, есть ли готовый URL
    db_url = os.getenv('DATABASE_URL')
    if db_url:
        return db_url
    
    # Проверяем настройки MySQL
    mysql_host = os.getenv('MYSQL_HOST')
    if mysql_host:
        # Собираем URL для MySQL
        mysql_port = os.getenv('MYSQL_PORT', '3306')
        mysql_user = os.getenv('MYSQL_USER', 'root')
        mysql_password = os.getenv('MYSQL_PASSWORD', '')
        mysql_database = os.getenv('MYSQL_DATABASE', 'cryptxspider')
        
        return f"mysql+pymysql://{mysql_user}:{mysql_password}@{mysql_host}:{mysql_port}/{mysql_database}"
    
    # По умолчанию используем SQLite
    return "sqlite:///cryptxspider.db"

# Создаем базовый класс для моделей
Base = declarative_base()

# Создаем подключение к базе данных
engine = create_engine(get_database_url(), pool_recycle=3600)

# Создаем сессию БД
Session = sessionmaker(bind=engine)
session = Session()

# Класс для работы с JSON в MySQL
class JSONEncodedDict(types.TypeDecorator):
    impl = types.Text

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        return json.dumps(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        return json.loads(value)

# Определяем тип JSON в зависимости от диалекта БД
JSON_Type = JSON().with_variant(JSONEncodedDict(), 'mysql')

class Jetton(Base):
    """Модель для хранения информации о токенах (джеттонах)"""
    __tablename__ = 'jetton'
    
    id = Column(Integer, primary_key=True)
    address = Column(String(255), unique=True, nullable=False)
    ticker = Column(String(20))
    name = Column(String(255))
    description = Column(Text)
    total_supply = Column(Float)
    minted_timestamp = Column(DateTime)
    creator_address = Column(String(255))
    website = Column(String(255))
    telegram = Column(String(255))
    twitter = Column(String(255))
    image_url = Column(String(255))
    last_updated = Column(DateTime, default=datetime.utcnow)
    is_scam = Column(Boolean, default=False)
    scam_probability = Column(Float, default=0.0)
    
    # Связи с другими таблицами
    transactions = relationship("Transaction", back_populates="jetton")
    holders = relationship("Holder", back_populates="jetton")
    
    def __repr__(self):
        return f"<Jetton(id={self.id}, ticker='{self.ticker}', name='{self.name}')>"

class Transaction(Base):
    """Модель для хранения информации о транзакциях с токенами"""
    __tablename__ = 'transaction'
    
    id = Column(Integer, primary_key=True)
    jetton_id = Column(Integer, ForeignKey('jetton.id'))
    transaction_hash = Column(String(255), nullable=False)
    from_address = Column(String(255))
    to_address = Column(String(255))
    amount = Column(Float)
    timestamp = Column(DateTime)
    
    # Связь с моделью Jetton
    jetton = relationship("Jetton", back_populates="transactions")
    
    def __repr__(self):
        return f"<Transaction(id={self.id}, from='{self.from_address}', to='{self.to_address}', amount={self.amount})>"

class Holder(Base):
    """Модель для хранения информации о держателях токенов"""
    __tablename__ = 'holder'
    
    id = Column(Integer, primary_key=True)
    jetton_id = Column(Integer, ForeignKey('jetton.id'))
    address = Column(String(255), nullable=False)
    amount = Column(Float)
    percent = Column(Float)
    
    # Связь с моделью Jetton
    jetton = relationship("Jetton", back_populates="holders")
    
    def __repr__(self):
        return f"<Holder(id={self.id}, address='{self.address}', amount={self.amount}, percent={self.percent})>"

class TelegramMessage(Base):
    """Модель для хранения сообщений из Telegram"""
    __tablename__ = 'telegram_message'
    
    id = Column(Integer, primary_key=True)
    message_id = Column(Integer)
    chat_id = Column(String(100))
    sender_id = Column(String(100))
    text = Column(Text)
    timestamp = Column(DateTime, default=datetime.utcnow)
    has_token_mention = Column(Boolean, default=False)
    
    def __repr__(self):
        return f"<TelegramMessage(id={self.id}, chat_id='{self.chat_id}', message_id={self.message_id})>"

class PotentialToken(Base):
    """Модель для хранения предполагаемых токенов, найденных в Telegram"""
    __tablename__ = 'potential_token'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(255))
    ticker = Column(String(20))
    description = Column(Text)
    source_message_id = Column(Integer)
    source_chat_id = Column(String(100))
    found_timestamp = Column(DateTime, default=datetime.utcnow)
    confidence_score = Column(Float, default=0.0)
    processed = Column(Boolean, default=False)
    jetton_id = Column(Integer, ForeignKey('jetton.id'), nullable=True)
    
    def __repr__(self):
        return f"<PotentialToken(id={self.id}, name='{self.name}', ticker='{self.ticker}')>"

class TelegramChannel(Base):
    """Модель для хранения информации о Telegram-каналах"""
    __tablename__ = 'telegram_channel'
    
    id = Column(Integer, primary_key=True)
    channel_id = Column(String(100), unique=True, nullable=False)
    username = Column(String(100))
    title = Column(String(255))
    description = Column(Text)
    members_count = Column(Integer, default=0)
    created_at = Column(DateTime)
    added_at = Column(DateTime, default=datetime.utcnow)
    last_scanned_at = Column(DateTime)
    is_active = Column(Boolean, default=True)
    relevance_score = Column(Float, default=0.0)
    token_mentions_count = Column(Integer, default=0)
    source = Column(String(100))
    source_details = Column(Text)
    
    def __repr__(self):
        return f"<TelegramChannel(id={self.id}, username='{self.username}', title='{self.title}', relevance={self.relevance_score})>"

def create_tables():
    """Создание всех таблиц в базе данных"""
    Base.metadata.create_all(engine)
    return True
