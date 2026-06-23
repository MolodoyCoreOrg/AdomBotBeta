import os
import re


SUPPORTED_IMAGE_FORMATS = [".png", ".jpg", ".jpeg"]

def find_image_file(name: str, folder: str) -> str | None:
    """
    Ищет файл с указанным именем и любым поддерживаемым расширением.
    Возвращает путь к файлу или None, если не найден.
    """
    # Если имя уже содержит расширение, проверяем его сначала
    for ext in SUPPORTED_IMAGE_FORMATS:
        if name.endswith(ext):
            path = os.path.join(folder, name)
            if os.path.exists(path):
                return path
            # Если файл с таким именем не найден, продолжаем поиск без расширения
            name_without_ext = name[:-len(ext)]
            break
    else:
        name_without_ext = name
    
    # Ищем файл без расширения с поддерживаемыми форматами
    for ext in SUPPORTED_IMAGE_FORMATS:
        path = os.path.join(folder, name_without_ext + ext)
        if os.path.exists(path):
            return path
    return None