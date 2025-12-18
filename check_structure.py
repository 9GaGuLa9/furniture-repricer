"""
Перевірка структури проекту та імпортів
"""

import sys
from pathlib import Path

print("="*60)
print("ПЕРЕВІРКА СТРУКТУРИ ПРОЕКТУ")
print("="*60)
print()

# Додати root до path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# 1. Перевірити структуру
print("1️⃣  Перевірка структури директорій...")
required_dirs = [
    project_root / "app",
    project_root / "app" / "scrapers",
    project_root / "app" / "modules",
]

for dir_path in required_dirs:
    if dir_path.exists():
        print(f"   ✅ {dir_path.relative_to(project_root)}")
    else:
        print(f"   ❌ {dir_path.relative_to(project_root)} - ВІДСУТНЯ!")

print()

# 2. Перевірити __init__.py
print("2️⃣  Перевірка __init__.py файлів...")
required_inits = [
    project_root / "app" / "__init__.py",
    project_root / "app" / "scrapers" / "__init__.py",
    project_root / "app" / "modules" / "__init__.py",
]

for init_path in required_inits:
    if init_path.exists():
        print(f"   ✅ {init_path.relative_to(project_root)}")
    else:
        print(f"   ❌ {init_path.relative_to(project_root)} - ВІДСУТНІЙ!")

print()

# 3. Спробувати імпортувати модулі
print("3️⃣  Тестування імпортів...")

test_imports = [
    ("app", "Пакет app"),
    ("app.scrapers", "Пакет scrapers"),
    ("app.modules", "Пакет modules"),
]

all_ok = True

for module_name, description in test_imports:
    try:
        __import__(module_name)
        print(f"   ✅ {description}: {module_name}")
    except ImportError as e:
        print(f"   ❌ {description}: {module_name} - ПОМИЛКА!")
        print(f"      {e}")
        all_ok = False

print()

# 4. Спробувати імпортувати emmamason
print("4️⃣  Тестування Emma Mason scraper...")
try:
    from app.scrapers.emmamason import EmmaMasonScraper, scrape_emmamason
    print(f"   ✅ EmmaMasonScraper імпортовано успішно")
    print(f"   ✅ scrape_emmamason функція доступна")
except ImportError as e:
    print(f"   ❌ Помилка імпорту Emma Mason scraper:")
    print(f"      {e}")
    all_ok = False

print()

# Результат
print("="*60)
if all_ok:
    print("✅ ВСЕ ПРАЦЮЄ! Можете запускати:")
    print()
    print("   python test_scraper.py")
    print("   python -m app.scrapers.emmamason")
else:
    print("❌ Є ПРОБЛЕМИ! Перегляньте помилки вище")
print("="*60)
