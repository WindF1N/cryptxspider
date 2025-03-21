import logging
import re
from typing import List, Dict, Any, Optional, Set, Tuple
from datetime import datetime, timedelta
import asyncio

from telethon import TelegramClient
from telethon.tl.functions.channels import GetFullChannelRequest, JoinChannelRequest
from telethon.tl.functions.messages import SearchGlobalRequest
from telethon.tl.types import Message, InputPeerEmpty, Channel
from telethon.errors import ChatAdminRequiredError, ChannelPrivateError, FloodWaitError, UsernameNotOccupiedError

from cryptxspider.config import (
    TELEGRAM_API_ID, TELEGRAM_API_HASH, TELEGRAM_PHONE, 
    TOKEN_KEYWORDS, MONITORED_CHANNELS, CHANNEL_DISCOVERY,
    CHANNEL_SEARCH_KEYWORDS, TELEGRAM_LINK_PATTERNS, RELEVANCE_FACTORS
)
from cryptxspider.models.db import session, TelegramMessage, PotentialToken, TelegramChannel

logger = logging.getLogger(__name__)

class TelegramSpider:
    """
    Парсер для мониторинга Telegram-каналов и поиска новых токенов.
    """
    
    def __init__(self):
        """Инициализация Telegram-парсера."""
        self.client = None
        self.active_channels = []  # Список активных каналов, загружается из БД
        self.token_keywords = TOKEN_KEYWORDS
        
        # Регулярные выражения для поиска информации о токенах
        self.token_patterns = [
            r'(?i)запуск\s+токена\s+([a-zA-Z0-9]+)',
            r'(?i)новый\s+токен\s+([a-zA-Z0-9]+)',
            r'(?i)листинг\s+на\s+Blum\s+([a-zA-Z0-9]+)',
            r'(?i)токен\s+([a-zA-Z0-9]+)\s+скоро',
            r'(?i)пресейл\s+([a-zA-Z0-9]+)',
            r'(?i)airdrop\s+([a-zA-Z0-9]+)',
            r'(?i)private\s+sale\s+([a-zA-Z0-9]+)',
        ]
        
        # Регулярные выражения для поиска ссылок на Telegram-каналы
        self.telegram_link_patterns = TELEGRAM_LINK_PATTERNS
    
    async def connect(self) -> bool:
        """
        Подключение к Telegram API.
        
        Returns:
            Успешно ли подключение
        """
        try:
            # Создаем клиент Telegram
            self.client = TelegramClient('cryptxspider_session', TELEGRAM_API_ID, TELEGRAM_API_HASH)
            await self.client.start(phone=TELEGRAM_PHONE)
            logger.info("Successfully connected to Telegram API")
            
            # Загружаем активные каналы из БД
            await self.load_active_channels()
            
            return True
        except Exception as e:
            logger.error(f"Failed to connect to Telegram API: {str(e)}")
            return False
    
    async def load_active_channels(self):
        """Загрузка активных каналов из базы данных."""
        try:
            # Загружаем каналы с релевантностью выше порога
            channels = session.query(TelegramChannel).filter(
                TelegramChannel.is_active == True,
                TelegramChannel.relevance_score >= CHANNEL_DISCOVERY["min_relevance_score"]
            ).all()
            
            if channels:
                self.active_channels = [channel.username for channel in channels if channel.username]
                logger.info(f"Loaded {len(self.active_channels)} active channels from database")
            else:
                # Используем начальный список каналов
                self.active_channels = MONITORED_CHANNELS.copy()
                
                # Сохраняем начальные каналы в БД, если их там еще нет
                for channel_name in self.active_channels:
                    await self.add_channel_to_db(channel_name, source="initial")
                
                logger.info(f"Using {len(self.active_channels)} initial channels")
        except Exception as e:
            logger.error(f"Failed to load active channels: {str(e)}")
            self.active_channels = MONITORED_CHANNELS.copy()
    
    async def add_channel_to_db(self, channel_name: str, source: str = None, source_details: str = None) -> Optional[TelegramChannel]:
        """
        Добавление канала в базу данных.
        
        Args:
            channel_name: Имя канала
            source: Источник обнаружения канала
            source_details: Дополнительные сведения об источнике
            
        Returns:
            Объект канала, если успешно добавлен
        """
        try:
            # Проверяем, существует ли канал уже в БД
            existing_channel = session.query(TelegramChannel).filter(
                TelegramChannel.username == channel_name
            ).first()
            
            if existing_channel:
                return existing_channel
            
            # Получаем информацию о канале
            try:
                entity = await self.client.get_entity(channel_name)
                if not isinstance(entity, Channel):
                    logger.warning(f"{channel_name} is not a channel, skipping")
                    return None
                
                full_channel = await self.client(GetFullChannelRequest(channel=entity))
                
                # Создаем новую запись в БД
                new_channel = TelegramChannel(
                    channel_id=str(entity.id),
                    username=channel_name,
                    title=getattr(entity, 'title', channel_name),
                    description=full_channel.full_chat.about if hasattr(full_channel, 'full_chat') and hasattr(full_channel.full_chat, 'about') else None,
                    members_count=full_channel.full_chat.participants_count if hasattr(full_channel, 'full_chat') and hasattr(full_channel.full_chat, 'participants_count') else None,
                    created_at=entity.date if hasattr(entity, 'date') else None,
                    relevance_score=0.5,  # Начальная оценка релевантности
                    source=source,
                    source_details=source_details
                )
                
                session.add(new_channel)
                session.commit()
                logger.info(f"Added new channel to database: {channel_name}")
                return new_channel
            except UsernameNotOccupiedError:
                logger.warning(f"Channel {channel_name} does not exist")
                return None
            except (ChannelPrivateError, ChatAdminRequiredError):
                logger.warning(f"Channel {channel_name} is private or requires admin privileges")
                return None
            except Exception as e:
                logger.error(f"Error getting channel info for {channel_name}: {str(e)}")
                return None
                
        except Exception as e:
            logger.error(f"Failed to add channel {channel_name} to database: {str(e)}")
            session.rollback()
            return None
    
    async def parse_token_chats(self, socials: List[Dict[str, str]]) -> List[Dict[str, Any]]:
        """
        Парсинг чатов из Memepad для анализа социальной активности токена и обнаружения новых каналов.
        
        Args:
            socials: Список социальных сетей токена
        
        Returns:
            Данные об активности в каналах
        """
        results = []
        
        if not self.client:
            if not await self.connect():
                return results
        
        found_telegram_channels = []
        
        # Ищем и обрабатываем все Telegram-ссылки
        for social in socials:
            # TELEGRAM ссылки
            if social.get("type") == "TELEGRAM":
                url = social.get("url", "")
                if not url:
                    continue
                
                # Извлекаем имя канала из URL
                channel_name = url.split('/')[-1]
                found_telegram_channels.append(channel_name)
                
                try:
                    # Получаем информацию о канале
                    entity = await self.client.get_entity(channel_name)
                    
                    # Добавляем канал в БД и наш список активных каналов
                    channel_db = await self.add_channel_to_db(channel_name, source="jetton_social")
                    if channel_db and channel_name not in self.active_channels:
                        self.active_channels.append(channel_name)
                    
                    full_channel = await self.client(GetFullChannelRequest(channel=entity))
                    
                    # Получаем последние сообщения
                    messages = await self.client.get_messages(entity, limit=50)
                    
                    # Анализируем сообщения на предмет ссылок на другие каналы
                    await self.extract_channel_links_from_messages(messages, source_details=f"via jetton social {channel_name}")
                    
                    # Анализируем сообщения и канал
                    message_count = len(messages)
                    members_count = full_channel.full_chat.participants_count if hasattr(full_channel, 'full_chat') and hasattr(full_channel.full_chat, 'participants_count') else 0
                    
                    # Проверяем возраст канала
                    if hasattr(entity, 'date'):
                        channel_age_days = (datetime.now() - entity.date).days
                    else:
                        channel_age_days = None
                    
                    results.append({
                        "channel_name": channel_name,
                        "channel_title": getattr(entity, 'title', channel_name),
                        "message_count": message_count,
                        "members_count": members_count,
                        "channel_age_days": channel_age_days,
                        "last_activity": messages[0].date if messages else None
                    })
                except Exception as e:
                    logger.error(f"Failed to parse Telegram channel {channel_name}: {str(e)}")
            
            # Проверяем другие типы соцсетей на скрытые Telegram-ссылки
            elif social.get("url"):
                url = social.get("url", "")
                # Проверяем, содержит ли URL ссылку на Telegram
                for pattern in self.telegram_link_patterns:
                    matches = re.findall(pattern, url)
                    for match in matches:
                        channel_name = match
                        if channel_name and channel_name not in found_telegram_channels:
                            found_telegram_channels.append(channel_name)
                            # Добавляем канал в БД и наш список активных каналов
                            channel_db = await self.add_channel_to_db(channel_name, source="hidden_in_social", source_details=f"found in {social.get('type')} URL")
                            if channel_db and channel_name not in self.active_channels:
                                self.active_channels.append(channel_name)
        
        return results
    
    def _extract_potential_token_names(self, message_text: str) -> List[str]:
        """
        Извлечение названий потенциальных токенов из текста сообщения.
        
        Args:
            message_text: Текст сообщения
        
        Returns:
            Список потенциальных названий токенов
        """
        potential_tokens = []
        
        # Проверяем наличие ключевых слов
        has_keywords = any(keyword.lower() in message_text.lower() for keyword in self.token_keywords)
        if not has_keywords:
            return []
        
        # Применяем регулярные выражения для поиска токенов
        for pattern in self.token_patterns:
            matches = re.findall(pattern, message_text)
            potential_tokens.extend(matches)
        
        # Дополнительный поиск по шаблону "TICKER (Name)"
        ticker_pattern = r'\b([A-Z]{2,10})\s+\(([^)]+)\)'
        matches = re.findall(ticker_pattern, message_text)
        for ticker, name in matches:
            potential_tokens.append(ticker)
        
        return list(set(potential_tokens))  # Удаляем дубликаты
    
    def _extract_channel_links(self, text: str) -> List[str]:
        """
        Извлечение ссылок на Telegram-каналы из текста.
        
        Args:
            text: Текст для анализа
        
        Returns:
            Список найденных имен каналов
        """
        channel_names = []
        
        # Применяем регулярные выражения для поиска ссылок на каналы
        for pattern in self.telegram_link_patterns:
            matches = re.findall(pattern, text)
            channel_names.extend(matches)
        
        # Удаляем дубликаты и возвращаем результат
        return list(set(channel_names))
    
    async def extract_channel_links_from_messages(self, messages: List[Message], source_details: str = None) -> List[str]:
        """
        Извлечение ссылок на Telegram-каналы из списка сообщений.
        
        Args:
            messages: Список сообщений для анализа
            source_details: Подробности об источнике
        
        Returns:
            Список обнаруженных имен каналов
        """
        found_channels = []
        
        for message in messages:
            if not message.text:
                continue
            
            # Ищем ссылки на каналы в тексте сообщения
            channel_names = self._extract_channel_links(message.text)
            
            for channel_name in channel_names:
                if channel_name and channel_name not in found_channels:
                    found_channels.append(channel_name)
                    # Добавляем канал в БД и в наш список активных каналов
                    channel_db = await self.add_channel_to_db(channel_name, source="message_link", source_details=source_details)
                    if channel_db and channel_name not in self.active_channels:
                        self.active_channels.append(channel_name)
        
        return found_channels
    
    async def _process_message(self, message: Message, chat_entity) -> Tuple[Optional[PotentialToken], List[str]]:
        """
        Обработка сообщения для поиска упоминаний новых токенов и ссылок на каналы.
        
        Args:
            message: Сообщение Telegram
            chat_entity: Сущность чата
        
        Returns:
            Кортеж (потенциальный токен, если найден, список найденных каналов)
        """
        if not message.text:
            return None, []
        
        message_text = message.text
        potential_token_names = self._extract_potential_token_names(message_text)
        
        # Ищем ссылки на другие каналы
        channel_names = self._extract_channel_links(message_text)
        
        # Обновляем статистику канала, если обнаружены упоминания токенов
        if potential_token_names:
            try:
                chat_id = str(chat_entity.id)
                channel = session.query(TelegramChannel).filter(TelegramChannel.channel_id == chat_id).first()
                if channel:
                    channel.token_mentions_count += 1
                    # Пересчитываем релевантность канала
                    await self.update_channel_relevance(channel)
                    session.commit()
            except Exception as e:
                logger.error(f"Error updating channel stats: {e}")
                session.rollback()
        
        if not potential_token_names:
            return None, channel_names
        
        # Сохраняем сообщение в БД
        telegram_message = TelegramMessage(
            message_id=message.id,
            chat_id=str(chat_entity.id),
            chat_title=getattr(chat_entity, 'title', str(chat_entity.id)),
            sender_id=str(message.sender_id),
            text=message_text,
            timestamp=message.date,
            contains_token_mention=True,
            potential_token_name=", ".join(potential_token_names)
        )
        
        session.add(telegram_message)
        
        # Обрабатываем первый найденный токен (для MVP)
        token_name = potential_token_names[0]
        
        # Проверяем, существует ли такой токен уже в базе
        existing_token = session.query(PotentialToken).filter_by(name=token_name).first()
        
        if existing_token:
            # Обновляем существующий токен
            existing_token.mention_count += 1
            existing_token.last_mentioned_at = datetime.utcnow()
            existing_token.confidence_score = min(1.0, existing_token.confidence_score + 0.1)
            return existing_token, channel_names
        else:
            # Создаем новый потенциальный токен
            new_token = PotentialToken(
                name=token_name,
                description=message_text,
                confidence_score=0.3  # Начальная уверенность
            )
            session.add(new_token)
            return new_token, channel_names
    
    async def parse_external_chats(self, limit_per_channel: int = 100) -> List[PotentialToken]:
        """
        Парсинг сторонних чатов для поиска будущих токенов и новых каналов.
        
        Args:
            limit_per_channel: Количество сообщений для анализа из каждого канала
        
        Returns:
            Список обнаруженных потенциальных токенов
        """
        discovered_tokens = []
        
        if not self.client:
            if not await self.connect():
                return discovered_tokens
        
        for channel_name in self.active_channels:
            try:
                logger.info(f"Parsing channel: {channel_name}")
                
                # Получаем сущность канала
                entity = await self.client.get_entity(channel_name)
                
                # Получаем последние сообщения
                messages = await self.client.get_messages(entity, limit=limit_per_channel)
                
                # Обновляем время последнего сканирования канала
                channel = session.query(TelegramChannel).filter(TelegramChannel.username == channel_name).first()
                if channel:
                    channel.last_scanned_at = datetime.utcnow()
                    session.commit()
                
                # Обрабатываем каждое сообщение
                for message in messages:
                    potential_token, found_channels = await self._process_message(message, entity)
                    if potential_token and potential_token not in discovered_tokens:
                        discovered_tokens.append(potential_token)
                
                # Сохраняем изменения в БД после обработки канала
                session.commit()
                
            except Exception as e:
                logger.error(f"Failed to parse channel {channel_name}: {str(e)}")
                session.rollback()
        
        return discovered_tokens
    
    async def search_channels_by_keywords(self, keywords: List[str] = None) -> List[str]:
        """
        Поиск новых каналов по ключевым словам через Telegram API.
        
        Args:
            keywords: Список ключевых слов для поиска
        
        Returns:
            Список найденных имен каналов
        """
        if not keywords:
            keywords = CHANNEL_SEARCH_KEYWORDS
        
        found_channels = []
        
        if not self.client:
            if not await self.connect():
                return found_channels
        
        for keyword in keywords:
            try:
                logger.info(f"Searching for channels with keyword: {keyword}")
                
                # Используем Telegram API для поиска каналов по ключевым словам
                try:
                    results = await self.client(SearchGlobalRequest(
                        q=keyword,
                        filter=None,
                        min_date=None,
                        max_date=None,
                        offset_rate=0,
                        offset_peer=InputPeerEmpty(),
                        offset_id=0,
                        limit=20
                    ))
                    
                    for result in results.chats:
                        if hasattr(result, 'username') and result.username:
                            channel_name = result.username
                            if channel_name not in found_channels:
                                found_channels.append(channel_name)
                                # Добавляем канал в БД
                                channel_db = await self.add_channel_to_db(channel_name, source="keyword_search", source_details=f"keyword: {keyword}")
                                if channel_db and channel_name not in self.active_channels:
                                    self.active_channels.append(channel_name)
                except FloodWaitError as e:
                    logger.warning(f"Hit rate limit when searching channels, need to wait {e.seconds} seconds")
                    await asyncio.sleep(e.seconds)
                    continue
                
                # Добавляем небольшую задержку между поисками
                await asyncio.sleep(2)
                
            except Exception as e:
                logger.error(f"Failed to search channels with keyword {keyword}: {str(e)}")
        
        return found_channels
    
    async def update_channel_relevance(self, channel: TelegramChannel) -> float:
        """
        Обновление оценки релевантности канала.
        
        Args:
            channel: Объект канала
        
        Returns:
            Новая оценка релевантности
        """
        try:
            # Получаем все факторы для оценки
            token_mentions_score = min(1.0, channel.token_mentions_count / 10) * RELEVANCE_FACTORS["token_mentions"]
            
            # Оценка по количеству участников
            members_count = channel.members_count or 0
            members_score = min(1.0, members_count / 10000) * RELEVANCE_FACTORS["members_count"]
            
            # Оценка по активности (как часто сканируется и обновляется)
            activity_score = 0.5  # По умолчанию средняя оценка
            if channel.last_scanned_at:
                days_since_scan = (datetime.utcnow() - channel.last_scanned_at).days
                activity_score = max(0.1, 1.0 - (days_since_scan / 30)) * RELEVANCE_FACTORS["activity"]
            
            # Оценка по релевантности описания
            description_score = 0.5  # По умолчанию средняя оценка
            if channel.description:
                # Проверяем наличие ключевых слов в описании
                keyword_matches = sum(1 for keyword in TOKEN_KEYWORDS if keyword.lower() in channel.description.lower())
                description_score = min(1.0, keyword_matches / 5) * RELEVANCE_FACTORS["description"]
            
            # Оценка по возрасту канала
            age_score = 0.5  # По умолчанию средняя оценка
            if channel.created_at:
                age_days = (datetime.utcnow() - channel.created_at).days
                # Предпочитаем каналы старше 30 дней, но не слишком старые
                if age_days < 7:
                    age_score = 0.2 * RELEVANCE_FACTORS["age"]  # Очень новые каналы
                elif age_days < 30:
                    age_score = 0.5 * RELEVANCE_FACTORS["age"]  # Новые каналы
                elif age_days < 365:
                    age_score = 0.9 * RELEVANCE_FACTORS["age"]  # Оптимальный возраст
                else:
                    age_score = 0.7 * RELEVANCE_FACTORS["age"]  # Старые каналы
            
            # Рассчитываем общую оценку релевантности
            relevance_score = token_mentions_score + members_score + activity_score + description_score + age_score
            
            # Обновляем оценку в объекте канала
            channel.relevance_score = relevance_score
            
            return relevance_score
        except Exception as e:
            logger.error(f"Error updating channel relevance: {e}")
            return channel.relevance_score  # Возвращаем текущую оценку в случае ошибки
    
    async def join_channel(self, channel_name: str) -> bool:
        """
        Присоединение к каналу, если это необходимо.
        
        Args:
            channel_name: Имя канала
        
        Returns:
            Успешно ли присоединение
        """
        try:
            # Получаем сущность канала
            entity = await self.client.get_entity(channel_name)
            
            # Проверяем, нужно ли присоединяться
            try:
                # Пробуем получить сообщения из канала
                await self.client.get_messages(entity, limit=1)
                logger.info(f"Already a member of channel {channel_name}")
                return True
            except (ChannelPrivateError, ChatAdminRequiredError):
                # Если не можем получить сообщения, присоединяемся к каналу
                await self.client(JoinChannelRequest(entity))
                logger.info(f"Successfully joined channel {channel_name}")
                return True
        except Exception as e:
            logger.error(f"Failed to join channel {channel_name}: {str(e)}")
            return False
    
    async def discover_new_channels(self, notification_bot=None):
        """
        Обнаружение новых каналов через разные методы.
        
        Args:
            notification_bot: Опциональный объект NotificationBot для отправки уведомлений
        """
        if not CHANNEL_DISCOVERY["enabled"]:
            return
        
        try:
            logger.info("Starting channel discovery process")
            
            # Проверяем, не превышен ли лимит каналов
            current_count = session.query(TelegramChannel).filter(TelegramChannel.is_active == True).count()
            if current_count >= CHANNEL_DISCOVERY["max_channels_total"]:
                logger.info(f"Channel limit reached: {current_count}/{CHANNEL_DISCOVERY['max_channels_total']}")
                return
            
            # Ищем каналы по ключевым словам
            new_channels = await self.search_channels_by_keywords()
            
            # Если есть новые каналы и бот уведомлений, отправляем уведомления
            if new_channels and notification_bot:
                for channel_name in new_channels:
                    channel = session.query(TelegramChannel).filter(
                        TelegramChannel.username == channel_name,
                        TelegramChannel.relevance_score >= 0.6  # Отправляем только о релевантных каналах
                    ).first()
                    
                    if channel:
                        await notification_bot.send_new_channel_alert(channel)
                        logger.info(f"Sent notification about new channel: {channel_name}")
            
            # Получаем каналы, которые еще не анализировали
            unscanned_channels = session.query(TelegramChannel).filter(
                TelegramChannel.is_active == True,
                TelegramChannel.last_scanned_at == None
            ).limit(CHANNEL_DISCOVERY["max_channels_per_run"]).all()
            
            for channel in unscanned_channels:
                if channel.username:
                    # Присоединяемся к каналу, если это необходимо
                    joined = await self.join_channel(channel.username)
                    if joined:
                        # Получаем последние сообщения
                        try:
                            entity = await self.client.get_entity(channel.username)
                            messages = await self.client.get_messages(entity, limit=50)
                            
                            # Ищем упоминания токенов и ссылки на другие каналы
                            token_mentions = 0
                            for message in messages:
                                potential_token, found_channels = await self._process_message(message, entity)
                                if potential_token:
                                    token_mentions += 1
                            
                            # Обновляем данные о канале
                            channel.token_mentions_count = token_mentions
                            channel.last_scanned_at = datetime.utcnow()
                            
                            # Обновляем релевантность канала
                            await self.update_channel_relevance(channel)
                            
                            # Если канал оказался высокорелевантным, отправляем уведомление
                            if channel.relevance_score >= 0.7 and notification_bot:
                                await notification_bot.send_new_channel_alert(channel)
                                logger.info(f"Sent notification about high-relevance channel: {channel.username}")
                            
                            session.commit()
                        except Exception as e:
                            logger.error(f"Error scanning channel {channel.username}: {e}")
                            session.rollback()
            
            # Обновляем список активных каналов
            await self.load_active_channels()
            
        except Exception as e:
            logger.error(f"Error in channel discovery: {e}")
    
    async def monitor_channels(self, interval: int = 3600):
        """
        Непрерывный мониторинг каналов для поиска новых токенов.
        
        Args:
            interval: Интервал между проверками в секундах
        """
        if not self.client:
            if not await self.connect():
                logger.error("Failed to start monitoring: could not connect to Telegram")
                return
        
        logger.info(f"Starting Telegram channels monitoring with interval {interval} seconds")
        
        while True:
            try:
                # Ищем новые каналы
                await self.discover_new_channels()
                
                # Парсим внешние каналы
                discovered_tokens = await self.parse_external_chats()
                logger.info(f"Discovered {len(discovered_tokens)} potential tokens")
                
                # Ждем указанный интервал
                await asyncio.sleep(interval)
                
            except Exception as e:
                logger.error(f"Error during channel monitoring: {str(e)}")
                await asyncio.sleep(60)  # Ждем минуту перед следующей попыткой
    
    async def close(self):
        """Закрытие соединения с Telegram API."""
        if self.client:
            await self.client.disconnect()
            logger.info("Telegram client disconnected")
