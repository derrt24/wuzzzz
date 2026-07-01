import os

# --- ТОКЕН ТЕЛЕГРАМ-БОТА ---
BOT_TOKEN = "8399140736:AAEz-6gOI5XDX6HaeMiPJrNL3Q0rVezt6LY"

# ====================================================================
#                         НАСТРОЙКИ ВУЗОВ
# ====================================================================

# -------------------------------------------------------------------
# 1. СПбПУ (Санкт-Петербургский политехнический университет)
# -------------------------------------------------------------------
SPBPU = {
    "name": "СПбПУ (Политех)",
    "main_page": "https://my.spbstu.ru/home/abit/list-applicants/bachelor",
    "get_abit_list": "https://my.spbstu.ru/home/get-abit-list",
    "get_code_list": "https://my.spbstu.ru/home/get-code-list",
    "get_direction_info": "https://my.spbstu.ru/home/get-direction-info",
    # Параметры фильтрации (оставляем пустым — поиск по всем условиям)
    "education_form": "2",           # 2 = Очная
    "condition": "",                  # пусто = все условия (бюджет, контракт, квоты...)
    "education_level": "bachelor",
}

# -------------------------------------------------------------------
# 2. СПбГУ (Санкт-Петербургский государственный университет)
# -------------------------------------------------------------------
SPBGU = {
    "name": "СПбГУ",
    "report_page": "https://enrollelists.spbu.ru/reports/PriemList02.php",
    "report_url": (
        "https://enrollelists.spbu.ru/reports/PriemList02.php"
        "?mode=list&education_level_sort_order=1"
        "&speciality=&program_name=&education_form_name="
        "&fin_source_name=&faculty_name=&is_foreign=0"
    ),
    "api_data": "https://enrollelists.spbu.ru/api/reports/priem-list-02/data",
    "education_level": "1",          # 1 = Бакалавриат и специалитет
}

# Общие заголовки HTTP
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
    "Content-Type": "application/json",
}

# -------------------------------------------------------------------
# База данных
# -------------------------------------------------------------------
DB_PATH = os.path.join(os.path.dirname(__file__), "bot_data.db")

# -------------------------------------------------------------------
# Мониторинг
# -------------------------------------------------------------------
MONITOR_INTERVAL_MINUTES = 30
