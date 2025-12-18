"""
Перевірка структури проекту та залежностей
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

# 3. Перевірити залежності (БЕЗ імпорту модулів)
print("3️⃣  Перевірка Python залежностей...")

dependencies = [
    ('yaml', 'PyYAML'),
    ('dotenv', 'python-dotenv'),
    ('bs4', 'beautifulsoup4'),
    ('requests', 'requests'),
    ('lxml', 'lxml'),
]

missing_deps = []
for module_name, package_name in dependencies:
    try:
        __import__(module_name)
        print(f"   ✅ {package_name}")
    except ImportError:
        print(f"   ❌ {package_name} - НЕ ВСТАНОВЛЕНО!")
        missing_deps.append(package_name)

if missing_deps:
    print()
    print("="*60)
    print("❌ ВІДСУТНІ ЗАЛЕЖНОСТІ!")
    print("="*60)
    print()
    print("Встановіть їх командою:")
    print()
    print(f"   pip install {' '.join(missing_deps)}")
    print()
    print("Або встановіть всі мінімальні залежності:")
    print()
    print("   pip install PyYAML python-dotenv beautifulsoup4 requests lxml")
    print()
    print("Або запустіть автоматичну установку:")
    print("   - Windows: подвійний клік на INSTALL.bat")
    print("   - Linux/Mac: chmod +x install.sh && ./install.sh")
    print()
    print("="*60)
    sys.exit(1)

print()

# 4. Тепер можна імпортувати модулі
print("4️⃣  Тестування імпортів пакетів...")

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

# 5. Спробувати імпортувати emmamason
print("5️⃣  Тестування Emma Mason scraper...")
try:
    from app.scrapers.emmamason import EmmaMasonScraper, scrape_emmamason
    print(f"   ✅ EmmaMasonScraper імпортовано успішно")
    print(f"   ✅ scrape_emmamason функція доступна")
except ImportError as e:
    print(f"   ❌ Помилка імпорту Emma Mason scraper:")
    print(f"      {e}")
    all_ok = False

print()

# 6. Тестування модулів
print("6️⃣  Тестування модулів...")
try:
    from app.modules import get_logger, PricingEngine, SKUMatcher
    print(f"   ✅ get_logger")
    print(f"   ✅ PricingEngine")
    print(f"   ✅ SKUMatcher")
except ImportError as e:
    print(f"   ❌ Помилка імпорту модулів:")
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
    print("   python run_repricer.py --test")
else:
    print("❌ Є ПРОБЛЕМИ! Перегляньте помилки вище")
print("="*60)
