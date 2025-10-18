import asyncio
from parser.hh_client import HHClient


async def test_hh_client():
    """Тестирование клиента HH API"""
    
    async with HHClient() as client:
        # Тест 1: Поиск вакансий Python разработчика в Казани
        print("=== Тест 1: Python вакансии в Казани ===")
        result = await client.search_vacancies(
            text="python developer",
            area="Казань",
            per_page=3
        )
        
        print(f"Найдено вакансий: {result.get('found', 0)}")
        print(f"На странице: {len(result.get('items', []))}\n")
        
        for vacancy in result.get('items', [])[:3]:
            formatted = client.format_vacancy(vacancy)
            print(formatted)
            print("-" * 50)
        
        # Тест 2: Поиск вакансий с зарплатой
        print("\n=== Тест 2: Python вакансии с зарплатой от 150000 ===")
        result = await client.search_vacancies(
            text="python",
            salary=150000,
            per_page=3
        )
        
        print(f"Найдено вакансий: {result.get('found', 0)}\n")
        
        for vacancy in result.get('items', [])[:3]:
            formatted = client.format_vacancy(vacancy)
            print(formatted)
            print("-" * 50)


if __name__ == "__main__":
    asyncio.run(test_hh_client())
