import subprocess
import time

while True:
    print("Запускаем бота...")
    process = subprocess.Popen(["python", "d:/Work/Guchigengovo/bot.py"])
    process.wait()  # ждем завершения процесса бота
    print("Бот завершился. Перезапуск через 5 секунд...")
    time.sleep(5)