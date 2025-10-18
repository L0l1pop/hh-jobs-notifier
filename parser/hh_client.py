import aiohttp
from typing import Optional, List, Dict
import logging
from dateutil import parser as date_parser

logger = logging.getLogger(__name__)


class HHClient:
    """Клиент для работы с API HeadHunter"""
    
    BASE_URL = "https://api.hh.ru"
    
    def __init__(self):
        self.session: Optional[aiohttp.ClientSession] = None
    
    async def __aenter__(self):
        """Создание сессии при входе в контекст"""
        self.session = aiohttp.ClientSession()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Закрытие сессии при выходе из контекста"""
        if self.session:
            await self.session.close()
    
    async def search_vacancies(
        self,
        text: str,
        area: Optional[str] = None,
        experience: Optional[str] = None,
        salary: Optional[int] = None,
        per_page: int = 20,
        page: int = 0
    ) -> Dict:
        """
        Поиск вакансий по заданным параметрам
        
        :param text: Ключевые слова для поиска
        :param area: ID города (например, 1 - Москва, 2 - Санкт-Петербург, 88 - Казань)
        :param experience: Опыт работы (noExperience, between1And3, between3And6, moreThan6)
        :param salary: Минимальная зарплата
        :param per_page: Количество результатов на странице (макс 100)
        :param page: Номер страницы
        :return: Словарь с результатами поиска
        """
        if not self.session:
            raise RuntimeError("Session is not initialized. Use 'async with' context manager.")
        
        params = {
            "text": text,
            "per_page": per_page,
            "page": page,
            "only_with_salary": "false"  # показывать вакансии без указания зарплаты
        }
        
        if area:
            area_id = await self._get_area_id(area)
            if area_id:
                params["area"] = area_id
        
        if experience:
            params["experience"] = experience
        
        if salary:
            params["salary"] = salary
            params["only_with_salary"] = "true"
        
        try:
            async with self.session.get(
                f"{self.BASE_URL}/vacancies",
                params=params,
                headers={"User-Agent": "HH Jobs Bot/1.0"}
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    logger.info(f"Found {data.get('found', 0)} vacancies for query: {text}")
                    return data
                else:
                    logger.error(f"HH API error: {response.status}")
                    return {"items": [], "found": 0}
        
        except Exception as e:
            logger.error(f"Error fetching vacancies: {e}")
            return {"items": [], "found": 0}
    
    async def _get_area_id(self, city_name: str) -> Optional[int]:
        """
        Получить ID города по названию
        
        :param city_name: Название города
        :return: ID города или None
        """
        cities_map = {
            "москва": 1,
            "санкт-петербург": 2,
            "петербург": 2,
            "спб": 2,
            "новосибирск": 4,
            "екатеринбург": 3,
            "казань": 88,
            "нижний новгород": 66,
            "челябинск": 96,
            "самара": 78,
            "омск": 68,
            "ростов-на-дону": 76,
            "уфа": 99,
            "красноярск": 54,
            "воронеж": 26,
            "пермь": 70,
            "волгоград": 24,
            "краснодар": 53,
            "саратов": 79,
            "тюмень": 97
        }
        
        city_lower = city_name.lower().strip()
        return cities_map.get(city_lower)
    
    async def get_vacancy_details(self, vacancy_id: str) -> Optional[Dict]:
        """
        Получить детальную информацию о вакансии
        
        :param vacancy_id: ID вакансии
        :return: Словарь с данными вакансии или None
        """
        if not self.session:
            raise RuntimeError("Session is not initialized.")
        
        try:
            async with self.session.get(
                f"{self.BASE_URL}/vacancies/{vacancy_id}",
                headers={"User-Agent": "HH Jobs Bot/1.0"}
            ) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    logger.error(f"Error getting vacancy {vacancy_id}: {response.status}")
                    return None
        
        except Exception as e:
            logger.error(f"Error fetching vacancy details: {e}")
            return None
    
    @staticmethod
    def format_vacancy(vacancy: Dict) -> str:
        """
        Форматирование вакансии для отправки пользователю
        
        :param vacancy: Словарь с данными вакансии
        :return: Отформатированная строка
        """
        name = vacancy.get("name", "Без названия")
        company = vacancy.get("employer", {}).get("name", "Не указано")
        

        salary = vacancy.get("salary")
        if salary:
            salary_from = salary.get("from")
            salary_to = salary.get("to")
            currency = salary.get("currency", "RUR")
            
            currency_map = {
                "RUR": "₽",
                "RUB": "₽",
                "USD": "$",
                "EUR": "€",
                "KZT": "₸",
                "UAH": "₴",
                "BYR": "Br",
                "AZN": "₼",
                "UZS": "сўм",
                "GEL": "₾"
            }
            
            currency_symbol = currency_map.get(currency, currency)
            
            if salary_from and salary_to:
                salary_text = f"{salary_from:,} - {salary_to:,} {currency_symbol}"
            elif salary_from:
                salary_text = f"от {salary_from:,} {currency_symbol}"
            elif salary_to:
                salary_text = f"до {salary_to:,} {currency_symbol}"
            else:
                salary_text = "Не указана"
        else:
            salary_text = "Не указана"
        
        experience = vacancy.get("experience", {}).get("name", "Не указан")
        
        area = vacancy.get("area", {}).get("name", "Не указан")
        
        url = vacancy.get("alternate_url", "")
        
        published = vacancy.get("published_at", "")
        if published:
            try:
                dt = date_parser.parse(published)
                
                months = {
                    1: "января", 2: "февраля", 3: "марта", 4: "апреля",
                    5: "мая", 6: "июня", 7: "июля", 8: "августа",
                    9: "сентября", 10: "октября", 11: "ноября", 12: "декабря"
                }
                
                day = dt.day
                month = months[dt.month]
                year = dt.year
                
                published_text = f"{day} {month} {year}г."
            except:
                published_text = "Неизвестно"
        else:
            published_text = "Неизвестно"
        
        message = (
            f"💼 <b>{name}</b>\n\n"
            f"🏢 Компания: <b>{company}</b>\n"
            f"💰 Зарплата: <code>{salary_text}</code>\n"
            f"🏙 Город: <code>{area}</code>\n"
            f"📊 Опыт: <code>{experience}</code>\n"
            f"📅 Опубликовано: <code>{published_text}</code>\n\n"
            f"🔗 <a href='{url}'>Открыть вакансию</a>"
        )
        
        return message

