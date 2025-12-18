═══════════════════════════════════════════════════════════
  НАЛАШТУВАННЯ GOOGLE SERVICE ACCOUNT
═══════════════════════════════════════════════════════════

Щоб репрайсер міг працювати з Google Sheets, потрібно:
1. Створити Service Account в Google Cloud
2. Отримати JSON ключ
3. Надати доступ до таблиці

═══════════════════════════════════════════════════════════
  КРОК 1: Створити Service Account
═══════════════════════════════════════════════════════════

1. Відкрийте Google Cloud Console:
   https://console.cloud.google.com/

2. Створіть новий проект (або оберіть існуючий):
   - Клік на назву проекту вгорі
   - "New Project"
   - Назва: "Furniture Repricer"
   - Create

3. Увімкніть Google Sheets API:
   - Меню → APIs & Services → Library
   - Шукайте "Google Sheets API"
   - Enable

4. Створіть Service Account:
   - Меню → IAM & Admin → Service Accounts
   - "+ CREATE SERVICE ACCOUNT"
   
   Service account details:
   - Name: furniture-repricer
   - ID: (автоматично)
   - Description: Service account for furniture repricer
   - CREATE AND CONTINUE

5. Grant permissions (пропустіть):
   - CONTINUE (без змін)

6. Grant users access (пропустіть):
   - DONE

═══════════════════════════════════════════════════════════
  КРОК 2: Завантажити JSON ключ
═══════════════════════════════════════════════════════════

1. Знайдіть щойно створений Service Account:
   - У списку Service Accounts
   - Клік на email (furniture-repricer@...)

2. Перейдіть на вкладку KEYS

3. Створіть новий ключ:
   - ADD KEY → Create new key
   - Key type: JSON
   - CREATE

4. JSON файл завантажиться автоматично
   Назва: furniture-repricer-xxxxx.json

5. Перемістіть файл у проект:
   
   Windows:
   - Скопіюйте файл у:
     D:\Google Drive\Coding\python\Upwork\furniture-repricer\credentials\
   
   - Перейменуйте на:
     service_account.json

═══════════════════════════════════════════════════════════
  КРОК 3: Надати доступ до Google Sheets
═══════════════════════════════════════════════════════════

1. Відкрийте JSON файл (service_account.json)

2. Знайдіть поле "client_email":
   "client_email": "furniture-repricer@xxx.iam.gserviceaccount.com"
   
   СКОПІЮЙТЕ цей email!

3. Відкрийте вашу Google Sheets таблицю в браузері

4. Клік на Share (Надати доступ)

5. Вставте email Service Account

6. Оберіть роль: Editor

7. Зніміть галочку "Notify people" (не надсилати email)

8. Share

ГОТОВО! Service Account тепер має доступ до таблиці.

═══════════════════════════════════════════════════════════
  КРОК 4: Налаштувати config.yaml
═══════════════════════════════════════════════════════════

1. Відкрийте config.yaml

2. Знайдіть секцію google_sheets

3. Замініть YOUR_SPREADSHEET_ID_HERE на ID вашої таблиці:

   Знайти ID можна в URL таблиці:
   https://docs.google.com/spreadsheets/d/[ЦЕ_ID]/edit
   
   Приклад:
   https://docs.google.com/spreadsheets/d/1MVUjRr6295RLsM8m_lHjKRZ_mIyalcLPVWTNos1oOM4/edit
                                        ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
                                        ЦЕ ID

4. Вставте ID у config.yaml:

   google_sheets:
     spreadsheet_id: "1MVUjRr6295RLsM8m_lHjKRZ_mIyalcLPVWTNos1oOM4"

5. Збережіть файл

═══════════════════════════════════════════════════════════
  КРОК 5: Перевірити підключення
═══════════════════════════════════════════════════════════

Запустіть тестовий скрипт:

python test_google_sheets.py

МАЄ ПОКАЗАТИ:

✅ Credentials файл існує
✅ Підключення успішне
✅ Тест підключення пройдено
✅ Таблиця відкрита
✅ Прочитано дані
✅ ВСІ ТЕСТИ ПРОЙДЕНО!

ЯКЩО ПОМИЛКИ - дивіться нижче:

═══════════════════════════════════════════════════════════
  TROUBLESHOOTING (Вирішення проблем)
═══════════════════════════════════════════════════════════

❌ "Credentials file not found"
   → Перевірте що файл існує:
   → credentials/service_account.json

❌ "Failed to connect to Google Sheets"
   → Перевірте що JSON файл валідний
   → Перевірте що Google Sheets API увімкнений

❌ "Permission denied" або "Requested entity was not found"
   → Service Account НЕ має доступу до таблиці
   → Повторіть КРОК 3 (Share таблицю)

❌ "Worksheet 'Data' not found"
   → Аркуш з назвою "Data" не існує
   → Створіть аркуш або змініть назву в config.yaml

❌ "The caller does not have permission"
   → Service Account має доступ Viewer, а потрібен Editor
   → Змініть права на Editor

═══════════════════════════════════════════════════════════
  СТРУКТУРА credentials/service_account.json
═══════════════════════════════════════════════════════════

Файл має виглядати так:

{
  "type": "service_account",
  "project_id": "furniture-repricer-xxxxx",
  "private_key_id": "xxxxx",
  "private_key": "-----BEGIN PRIVATE KEY-----\n...",
  "client_email": "furniture-repricer@xxxxx.iam.gserviceaccount.com",
  "client_id": "xxxxx",
  "auth_uri": "https://accounts.google.com/o/oauth2/auth",
  "token_uri": "https://oauth2.googleapis.com/token",
  ...
}

Найважливіше поле: "client_email"
Його треба додати в Share таблиці!

═══════════════════════════════════════════════════════════
  БЕЗПЕКА
═══════════════════════════════════════════════════════════

⚠️  service_account.json містить приватний ключ!

НЕ ПУБЛІКУЙТЕ цей файл:
- Не додавайте в Git
- Не надсилайте email
- Не завантажуйте на публічні сервери

Файл вже в .gitignore, тому Git його ігноруватиме.

═══════════════════════════════════════════════════════════
  ГОТОВО!
═══════════════════════════════════════════════════════════

Після успішного тесту можна запускати репрайсер:

python run_repricer.py --test

Репрайсер зможе:
✅ Читати дані з Google Sheets
✅ Записувати оновлені ціни
✅ Зберігати історію змін

Успіхів! 🚀
