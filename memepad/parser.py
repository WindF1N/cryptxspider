import aiohttp
import asyncio
import logging
from typing import List, Dict, Any, Optional

from cryptxspider.config import MEMEPAD_BASE_URL, REACTIONS_BASE_URL, STONFI_BASE_URL

logger = logging.getLogger(__name__)

class MemepadParser:
    """
    Асинхронный парсер для получения данных о токенах с Memepad
    """
    
    async def fetch_jettons(self, endpoint: str) -> List[Dict[str, Any]]:
        """
        Получение токенов со всех вкладок.
        
        Args:
            endpoint: Конечная точка API, например:
                - Spotlight: /jetton/spotlight
                - Listed: /jetton/sections/published_at?published=only&pageToken=1
                - Bluming: /jetton/sections/nearest_to_listing?published=include_listed
                - Hot: /jetton/sections/hot?published=include
                - Live: /jetton/sections/live-streams?published=include
                - New: /jetton/sections/created_at?published=exclude
                
        Returns:
            Список токенов
        """
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{MEMEPAD_BASE_URL}/{endpoint}") as resp:
                    if resp.status != 200:
                        logger.error(f"Error fetching jettons from {endpoint}: {resp.status}")
                        return []
                    
                    data = await resp.json()
                    return data.get("jettons", [])
        except Exception as e:
            logger.error(f"Failed to fetch jettons from {endpoint}: {str(e)}")
            return []

    async def fetch_all_jettons(self) -> List[Dict[str, Any]]:
        """
        Получение токенов со всех вкладок.
        
        Returns:
            Объединенный список токенов без дубликатов
        """
        endpoints = [
            "jetton/spotlight",
            "jetton/sections/published_at?published=only&pageToken=1",
            "jetton/sections/nearest_to_listing?published=include_listed",
            "jetton/sections/hot?published=include",
            "jetton/sections/live-streams?published=include",
            "jetton/sections/created_at?published=exclude"
        ]
        
        tasks = [self.fetch_jettons(endpoint) for endpoint in endpoints]
        results = await asyncio.gather(*tasks)
        
        # Объединяем все токены и удаляем дубликаты по адресу
        all_jettons = []
        seen_addresses = set()
        
        for jettons_list in results:
            for jetton in jettons_list:
                address = jetton.get("address")
                if address and address not in seen_addresses:
                    seen_addresses.add(address)
                    all_jettons.append(jetton)
        
        return all_jettons

    async def fetch_jetton_details(self, short_name: str) -> Optional[Dict[str, Any]]:
        """
        Получение детальной информации о токене.
        
        Args:
            short_name: Короткое имя токена
            
        Returns:
            Детальная информация о токене
        """
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{MEMEPAD_BASE_URL}/jetton/s/{short_name}") as resp:
                    if resp.status != 200:
                        logger.error(f"Error fetching jetton details for {short_name}: {resp.status}")
                        return None
                    
                    return await resp.json()
        except Exception as e:
            logger.error(f"Failed to fetch jetton details for {short_name}: {str(e)}")
            return None

    async def fetch_reactions(self, short_name: str) -> Dict[str, int]:
        """
        Получение реакций для токена.
        
        Args:
            short_name: Короткое имя токена
            
        Returns:
            Словарь с реакциями
        """
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{REACTIONS_BASE_URL}/reactions/{short_name}") as resp:
                    if resp.status != 200:
                        logger.error(f"Error fetching reactions for {short_name}: {resp.status}")
                        return {}
                    
                    return await resp.json()  # {"fire":0,"rocket":1,...}
        except Exception as e:
            logger.error(f"Failed to fetch reactions for {short_name}: {str(e)}")
            return {}

    async def fetch_transactions(self, short_name: str) -> List[Dict[str, Any]]:
        """
        Получение транзакций для токена.
        
        Args:
            short_name: Короткое имя токена
            
        Returns:
            Список транзакций
        """
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{MEMEPAD_BASE_URL}/jetton/s/{short_name}/transactions") as resp:
                    if resp.status != 200:
                        logger.error(f"Error fetching transactions for {short_name}: {resp.status}")
                        return []
                    
                    data = await resp.json()
                    return data.get("transactions", [])
        except Exception as e:
            logger.error(f"Failed to fetch transactions for {short_name}: {str(e)}")
            return []

    async def fetch_stonfi_data(self, contract_address: str) -> Optional[Dict[str, Any]]:
        """
        Получение данных о токене с Ston.fi.
        
        Args:
            contract_address: Адрес контракта токена
            
        Returns:
            Данные о токене с Ston.fi
        """
        try:
            async with aiohttp.ClientSession() as session:
                # Используем стандартный адрес кошелька из документации
                wallet_address = "EQDjal6NZlYefSz0qYbbKYL_5G7lzdixamDHcXv3sUP0OYMu"
                async with session.get(f"{STONFI_BASE_URL}/wallets/{wallet_address}/assets/{contract_address}") as resp:
                    if resp.status != 200:
                        logger.error(f"Error fetching Ston.fi data for {contract_address}: {resp.status}")
                        return None
                    
                    return await resp.json()
        except Exception as e:
            logger.error(f"Failed to fetch Ston.fi data for {contract_address}: {str(e)}")
            return None

    async def get_complete_jetton_data(self, short_name: str, address: str) -> Dict[str, Any]:
        """
        Получение полной информации о токене из всех источников.
        
        Args:
            short_name: Короткое имя токена
            address: Адрес контракта токена
            
        Returns:
            Полная информация о токене
        """
        tasks = [
            self.fetch_jetton_details(short_name),
            self.fetch_reactions(short_name),
            self.fetch_transactions(short_name),
            self.fetch_stonfi_data(address)
        ]
        
        results = await asyncio.gather(*tasks)
        
        return {
            "details": results[0],
            "reactions": results[1],
            "transactions": results[2],
            "stonfi_data": results[3]
        }
