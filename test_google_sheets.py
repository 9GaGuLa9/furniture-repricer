"""
Тестування підключення до Google Sheets
"""

import sys
from pathlib import Path

# Додати root до path
sys.path.insert(0, str(Path(__file__).parent))

from app.modules import GoogleSheetsClient, get_config

def test_google_sheets():
    """Тест підключення до Google Sheets"""
    
    print("="*60)
    print("ТЕСТ GOOGLE SHEETS ПІДКЛЮЧЕННЯ")
    print("="*60)
    print()
    
    # Завантажити конфігурацію
    print("1️⃣  Завантаження конфігурації...")
    config = get_config()
    
    credentials_path = config.google_credentials_path
    sheet_id = config.main_sheet_id
    sheet_name = config.main_sheet_name
    
    print(f"   ✓ Credentials: {credentials_path}")
    print(f"   ✓ Sheet ID: {sheet_id}")
    print(f"   ✓ Sheet Name: {sheet_name}")
    print()
    
    # Перевірити credentials файл
    print("2️⃣  Перевірка credentials файлу...")
    if not credentials_path.exists():
        print(f"   ❌ Файл не знайдено: {credentials_path}")
        print()
        print("   Створіть файл:")
        print(f"   {credentials_path}")
        print()
        print("   Інструкції:")
        print("   1. Відкрийте Google Cloud Console")
        print("   2. Створіть Service Account")
        print("   3. Завантажте JSON ключ")
        print("   4. Збережіть як service_account.json")
        print()
        return False
    print(f"   ✓ Файл існує")
    print()
    
    # Підключитись до Google Sheets
    print("3️⃣  Підключення до Google Sheets API...")
    try:
        client = GoogleSheetsClient(str(credentials_path))
        print("   ✓ Підключення успішне")
    except Exception as e:
        print(f"   ❌ Помилка підключення: {e}")
        print()
        print("   Можливі причини:")
        print("   - Невалідний JSON файл")
        print("   - Service Account не має доступу до API")
        print("   - Google Sheets API не увімкнений")
        print()
        return False
    print()
    
    # Тест підключення
    print("4️⃣  Тестування підключення...")
    try:
        if client.test_connection():
            print("   ✓ Тест підключення пройдено")
        else:
            print("   ❌ Тест підключення не пройдено")
            return False
    except Exception as e:
        print(f"   ❌ Помилка: {e}")
        return False
    print()
    
    # Спробувати відкрити таблицю
    print("5️⃣  Відкриття таблиці...")
    if not sheet_id or sheet_id == "YOUR_SPREADSHEET_ID_HERE":
        print("   ⚠️  Sheet ID не налаштовано в config.yaml")
        print()
        print("   Відредагуйте config.yaml:")
        print("   google_sheets:")
        print("     spreadsheet_id: \"ВАШ_ID_ТАБЛИЦІ\"")
        print()
        print("   Знайти ID можна в URL таблиці:")
        print("   https://docs.google.com/spreadsheets/d/[ЦЕ_ID]/edit")
        print()
        return False
    
    try:
        worksheet = client.open_sheet(sheet_id, sheet_name)
        print(f"   ✓ Таблиця відкрита: {worksheet.title}")
        
        # Прочитати перші 3 рядки
        print()
        print("6️⃣  Читання даних...")
        data = worksheet.get_all_values()[:3]
        
        if data:
            print(f"   ✓ Прочитано {len(data)} рядків")
            print()
            print("   Перші 3 рядки:")
            for i, row in enumerate(data, 1):
                preview = row[:5]  # Перші 5 колонок
                print(f"   {i}. {preview}")
        else:
            print("   ⚠️  Таблиця пуста")
        
    except Exception as e:
        print(f"   ❌ Помилка відкриття таблиці: {e}")
        print()
        print("   Можливі причини:")
        print("   - Невірний Sheet ID")
        print("   - Service Account не має доступу до таблиці")
        print("   - Аркуш з назвою '{sheet_name}' не існує")
        print()
        print("   Рішення:")
        print("   1. Відкрийте таблицю в браузері")
        print("   2. Share → додайте email Service Account")
        print("   3. Дайте права Editor")
        print()
        return False
    
    print()
    print("="*60)
    print("✅ ВСІ ТЕСТИ ПРОЙДЕНО!")
    print("="*60)
    print()
    print("Google Sheets готовий до використання!")
    print()
    return True


if __name__ == "__main__":
    success = test_google_sheets()
    sys.exit(0 if success else 1)
