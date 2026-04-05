import os
import re


SUPPORTED_IMAGE_FORMATS = [".png", ".jpg", ".jpeg"]

def find_image_file(name: str, folder: str) -> str | None:
    """
    Ищет файл с указанным именем и любым поддерживаемым расширением.
    Возвращает путь к файлу или None, если не найден.
    """
    for ext in SUPPORTED_IMAGE_FORMATS:
        path = os.path.join(folder, name + ext)
        if os.path.exists(path):
            return path
    return None