# config.py

# Шансы выпадения по редкости (в процентах)
RARITY_WEIGHTS = {
    "Обычная": 30,
    "Редкая": 15,
    "Эпическая": 2,
    "Легендарная": 0.25
}

DB_FILE = "database/users.db"

ADMINS_LIST = [1114626593, 347632821, 462179661, 776301286, 1628880507, 1489467578]  # тут твои ID админов

DA_TOKEN = "pqtvXdJ2EdIogi87hGzK"

# Указываем режим работы
MODE = "PROD"   # DEV / PROD / TEST

# Токены
TOKEN_DEV = "8068425537:AAGgB-LwUWai_2Zqld5SEEKqAEjzBKYkEvI"
TOKEN_PROD = "7496302615:AAGnggJsYKbXa8REfmdK4_xsnJf27a4Ahus"
TOKEN_TEST = "8295786123:AAEZxxvp-ofJKlKXgb48h8CFRK9oTCdEooQ"

# Выбор токена по режиму
if MODE == "DEV":
    TOKEN = TOKEN_DEV
elif MODE == "PROD":
    TOKEN = TOKEN_PROD
elif MODE == "TEST":
    TOKEN = TOKEN_TEST
else:
    raise ValueError("Укажи корректный MODE: DEV, PROD или TEST")
