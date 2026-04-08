import requests
from bs4 import BeautifulSoup
import re
import os
from urllib.parse import urlparse, urljoin
import sys
import argparse

def clean_filename(url):
    """Создает чистое имя файла из URL с учетом /Канон"""
    parsed_url = urlparse(url)
    path_parts = parsed_url.path.split('/')

    # Обработка ссылок, заканчивающихся на "/Канон"
    if path_parts[-1] == 'Канон' and len(path_parts) > 1:
        filename = path_parts[-2]  # Берем предыдущий элемент
    else:
        filename = path_parts[-1] if path_parts[-1] else path_parts[-2]

    filename = re.sub(r'\?.*$', '', filename)
    filename = re.sub(r'\.\w+$', '', filename)
    filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
    return f"{filename}.txt"

def is_mojibake_text(link_text):
    """Проверяет, является ли текст некорректно отображенным (mojibake)"""
    # Паттерны для обнаружения mojibake (некорректно отображенных символов)
    mojibake_patterns = [
        r'–[A-Za-z0-9]–[A-Za-z0-9]',  # –£–±–Є–є—Б—В–≤–∞
        r'â€[a-zA-Z]',                 # â€‹, â€™
        r'Ã[0-9A-Za-z]',               # Ã©, Ã¼
        r'â€"',                        # â€"
        r'â€"',                        # â€"
        r'â€¦',                        # â€¦
    ]

    for pattern in mojibake_patterns:
        if re.search(pattern, link_text):
            return True

    # Проверяем наличие множественных дефисов с буквами/цифрами между ними
    if re.search(r'(?:–[A-Za-z0-9]){3,}', link_text):
        return True

    return False

def is_citation_link(link_text):
    """Проверяет, является ли ссылка цитатой/источником в квадратных скобках"""
    return bool(re.match(r'^\[\d+\]$', link_text))

def is_source_reference(link_text):
    """Проверяет, является ли ссылка указанием на источник"""
    source_patterns = [
        r'^\(источник\)$',
        r'^\(исходник\)$',
        r'^\(source\)$',
        r'^источник$',
        r'^source$'
    ]
    for pattern in source_patterns:
        if re.match(pattern, link_text, re.IGNORECASE):
            return True
    return False

def is_language_translation(text):
    """Проверяет, является ли текст переводом на другой язык"""
    return bool(re.search(r'\(англ\.\s+[^)]+\)', text))

def is_date_link(link_text):
    """Проверяет, является ли ссылка датой"""
    # Паттерны для дат
    date_patterns = [
        r'\d{1,5}\s*[ДП]БЯ',  # 10966 ДБЯ, 10 ПБЯ
        r'\d{4}\s*год',        # 1983 год
        r'^\d{4}$',            # 2016
        r'\d{1,2}\s*[а-я]+',   # 22 июня
        r'\d{1,2}\s*[a-z]+',   # 22 june (английские месяцы)
    ]

    for pattern in date_patterns:
        if re.search(pattern, link_text, re.IGNORECASE):
            return True
    return False

def is_target_language_link(link_text):
    """Проверяет, является ли ссылка на русском или английском языке"""
    # Сначала проверяем на mojibake
    if is_mojibake_text(link_text):
        return False

    # Проверяем на цитаты/источники
    if is_citation_link(link_text):
        return False

    # Проверяем на указания источников
    if is_source_reference(link_text):
        return False

    # Проверяем наличие русских символов
    has_russian = bool(re.search(r'[а-яА-Я]', link_text))

    # Проверяем наличие английских символов
    has_english = bool(re.search(r'[a-zA-Z]', link_text))

    # Проверяем наличие символов других языков (китайские, японские, арабские и т.д.)
    non_target_patterns = [
        r'[\u4e00-\u9fff]',  # Китайские иероглифы
        r'[\u3040-\u309f]',  # Хирагана
        r'[\u30a0-\u30ff]',  # Катакана
        r'[\u0600-\u06ff]',  # Арабские
        r'[\u0900-\u097f]',  # Деванагари
    ]

    has_other_language = False
    for pattern in non_target_patterns:
        if re.search(pattern, link_text):
            has_other_language = True
            break

    # Принимаем ссылку если:
    # 1. Есть русские символы ИЛИ английские символы
    # 2. НЕТ символов других языков
    # 3. ИЛИ это смешанный текст (русский + английский)
    if (has_russian or has_english) and not has_other_language:
        return True

    # Также принимаем чисто цифровые ссылки без других символов
    if re.match(r'^[\d\s\-–—]+$', link_text):
        return True

    return False

def extract_hyperlinks_from_clean_content(clean_content_soup, source_url, debug_mode=False):
    """Извлекает гиперссылки только из очищенного контента с фильтрацией"""
    hyperlinks = set()

    # Ищем все ссылки в очищенном контенте
    for link in clean_content_soup.find_all('a', href=True):
        link_text = link.get_text(strip=True)
        href = link['href']

        # Пропускаем пустые ссылки и ссылки без текста
        if not link_text or len(link_text) < 2:
            continue

        # Пропускаем якорные ссылки (начинаются с #)
        if href.startswith('#'):
            continue

        # Пропускаем служебные и специальные ссылки
        if any(x in href for x in ['Special:', 'File:', 'Category:', 'Template:', 'Help:', 'User:']):
            continue

        # Фильтр 1: Пропускаем ссылки с mojibake (некорректно отображенными символами)
        if is_mojibake_text(link_text):
            if debug_mode:
                print(f"DEBUG: Пропущен mojibake: {link_text}")
            continue

        # Фильтр 2: Пропускаем ссылки-цитаты [1], [15] и т.д.
        if is_citation_link(link_text):
            if debug_mode:
                print(f"DEBUG: Пропущена цитата: {link_text}")
            continue

        # Фильтр 3: Пропускаем ссылки на источники
        if is_source_reference(link_text):
            if debug_mode:
                print(f"DEBUG: Пропущен источник: {link_text}")
            continue

        # Фильтр 4: Пропускаем ссылки с датами
        if is_date_link(link_text):
            if debug_mode:
                print(f"DEBUG: Пропущена дата: {link_text}")
            continue

        # Фильтр 5: Пропускаем ссылки не на русском/английском
        if not is_target_language_link(link_text):
            if debug_mode:
                print(f"DEBUG: Пропущен другой язык: {link_text}")
            continue

        # Форматируем для дебаг режима
        if debug_mode:
            link_entry = f"{link_text} <- {source_url}"
        else:
            link_entry = link_text

        hyperlinks.add(link_entry)

    return hyperlinks

def save_hyperlinks_to_index(hyperlinks, debug_mode=False):
    """Сохраняет гиперссылки в файл names_index.txt с сортировкой по алфавиту"""
    try:
        # Очищаем файл и записываем отсортированные ссылки
        with open('names_index.txt', 'w', encoding='utf-8') as f:
            for link in sorted(hyperlinks):
                f.write(link + '\n')
        print(f"Сохранено {len(hyperlinks)} гиперссылок в names_index.txt")
    except Exception as e:
        print(f"Ошибка при сохранении гиперссылок: {e}")

def extract_clean_content(soup, debug_mode=False):
    """Извлекает и очищает контент, возвращает BeautifulSoup объект и чистый текст"""
    main_content = soup.find('div', {'class': 'mw-parser-output'})
    if not main_content:
        main_content = soup.find('main') or soup.find('article') or soup.body
    if not main_content:
        return None, "Не удалось извлечь основной контент"

    content_copy = BeautifulSoup(str(main_content), 'html.parser')

    # Удаляем ненужные элементы
    for element in content_copy.find_all(['script', 'style', 'nav', 'footer', 'aside', 'header', 'form', 'iframe']):
        element.decompose()
    for element in content_copy.find_all(['figure', 'img', 'figcaption']):
        element.decompose()

    image_related_classes = ['thumb', 'image', 'gallery', 'mw-halign', 'show-info-icon', 'thumbcaption',
                             'caption', 'mw-file-description', 'thumbimage', 'lazyload']
    for class_name in image_related_classes:
        for element in content_copy.find_all(class_=class_name):
            element.decompose()

    for element in content_copy.find_all(attrs={'data-image-name': True}):
        element.decompose()
    for element in content_copy.find_all(attrs={'data-image-key': True}):
        element.decompose()
    for element in content_copy.find_all(attrs={'alt': True}):
        if element.name in ['img', 'figure']:
            element.decompose()

    # Удаляем кнопки редактирования [править]
    for edit_section in content_copy.find_all(class_='mw-editsection'):
        edit_section.decompose()

    for toc_element in content_copy.find_all(class_='toc'):
        toc_element.decompose()

    # Удаляем ненужные разделы (расширенный список)
    sections_to_remove = [
        'Содержание',
        'Оглавление',
        'Примечания и сноски',
        'Источники',
        'Появления',
        'Появления в неканоничных медиа',
        'На других языках',
        'Notes and references',
        'За кулисами',
        'Ссылки на внешние источники',
        'Behind the scenes',
        'Appearances',
        'Sources',
        'External links',
        'Ссылки и примечания',
        'Примечания',
        'Примечания и сноски',
        'Это статья-заготовка'
    ]

    headers = content_copy.find_all(['h2', 'h3', 'h4', 'h5', 'h6'])
    elements_to_remove = []

    for header in headers:
        header_text = header.get_text(strip=True)
        # Удаляем квадратные скобки из заголовков
        clean_header_text = re.sub(r'\[\]$', '', header_text)

        if any(section.lower() in clean_header_text.lower() for section in sections_to_remove):
            elements_to_remove.append(header)
            next_element = header.next_sibling
            while next_element:
                if isinstance(next_element, str):
                    if not next_element.strip():
                        next_element = next_element.next_sibling
                        continue
                if hasattr(next_element, 'name') and next_element.name in ['h2', 'h3', 'h4', 'h5', 'h6']:
                    if int(next_element.name[1]) <= int(header.name[1]):
                        break
                elements_to_remove.append(next_element)
                next_element = next_element.next_sibling

    for element in elements_to_remove:
        if hasattr(element, 'decompose'):
            element.decompose()
        else:
            try:
                element.extract()
            except Exception:
                pass

    # Удаляем disclaimer "Это статья-заготовка"
    for p in content_copy.find_all('p'):
        if 'статья-заготовка' in p.get_text():
            p.decompose()

    # Создаем копию для извлечения текста (без ссылок)
    text_copy = BeautifulSoup(str(content_copy), 'html.parser')

    # Удаляем ссылки на источники в квадратных скобках и указания на источники
    for link in text_copy.find_all('a', href=True):
        link_text = link.get_text(strip=True)
        if is_citation_link(link_text) or is_source_reference(link_text):
            link.decompose()
        else:
            link.replace_with(link.get_text())

    # Извлекаем чистый текст
    text = text_copy.get_text()
    lines = []
    for line in text.split('\n'):
        line = line.strip()
        if line and len(line) > 2:
            # Удаляем цитаты в тексте [15], [1] и т.д.
            line = re.sub(r'\[\d+\]', '', line)
            # Удаляем переводы на другие языки
            line = re.sub(r'\(англ\.\s+[^)]+\)', '', line)
            line = re.sub(r'\s+', ' ', line)
            if line.strip():
                lines.append(line)

    clean_text = '\n\n'.join(lines)
    clean_text = re.sub(r'\n\s*\n\s*\n+', '\n\n', clean_text)

    return content_copy, clean_text

def save_text_from_fandom(url, debug_mode=False):
    """Основная функция для сохранения текста со страницы Fandom"""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        print(f"Загружаем страницу: {url}")
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        response.encoding = response.apparent_encoding
        soup = BeautifulSoup(response.text, 'html.parser')
        title = soup.find('h1')
        page_title = title.get_text(strip=True) if title else "Без названия"

        # Извлекаем очищенный контент и текст
        clean_content, clean_text = extract_clean_content(soup, debug_mode)

        if clean_text == "Не удалось извлечь основной контент":
            return None, set()

        # Извлекаем гиперссылки только из очищенного контента
        hyperlinks = extract_hyperlinks_from_clean_content(clean_content, url, debug_mode)

        # Создаем директорию для сохранения файлов
        folder_path = './knowledge_base_source'
        os.makedirs(folder_path, exist_ok=True)

        # Создаем имя файла с учетом папки
        filename = clean_filename(url)
        filepath = os.path.join(folder_path, filename)

        # Сохраняем текст в файл
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(f"Заголовок: {page_title}\n")
            if debug_mode:
                f.write(f"URL: {url}\n")
            f.write("-" * 50 + "\n\n")
            f.write(clean_text)

        print(f"Текст успешно сохранен в файл: {filepath}")
        print(f"Размер текста: {len(clean_text)} символов")
        return filepath, hyperlinks

    except requests.RequestException as e:
        print(f"Ошибка при загрузке страницы: {e}")
        return None, set()
    except Exception as e:
        print(f"Произошла ошибка: {e}")
        return None, set()

def main():
    parser = argparse.ArgumentParser(description='Извлечение текста с Fandom.com')
    parser.add_argument('url', nargs='?', help='URL страницы Fandom')
    parser.add_argument('--file', '-f', help='Файл со списком URL')
    parser.add_argument('--debug', '-d', action='store_true', help='Режим дебага с сохранением источников ссылок')
    args = parser.parse_args()

    print("Скрипт для извлечения текста с Fandom.com")
    if args.debug:
        print("РЕЖИМ ДЕБАГА АКТИВЕН")
    print("-" * 40)

    urls = []

    # 1. Аргумент --file
    if args.file:
        try:
            with open(args.file, 'r', encoding='utf-8') as f:
                urls = [line.strip() for line in f if line.strip()]
            print(f"Загружено {len(urls)} URL из файла {args.file}")
        except FileNotFoundError:
            print(f"Файл {args.file} не найден!")
            return

    # 2. Аргумент URL
    if args.url:
        urls.append(args.url)

    # 3. Файл source_index.txt
    if not urls and os.path.exists("source_index.txt"):
        try:
            with open("source_index.txt", 'r', encoding='utf-8') as f:
                urls = [line.strip() for line in f if line.strip()]
            print(f"Загружено {len(urls)} URL из файла source_index.txt")
        except Exception as e:
            print(f"Ошибка при чтении source_index.txt: {e}")
            return

    # 4. Ручной ввод
    if not urls:
        url_input = input("Введите URL страницы Fandom (или несколько через запятую): ").strip()
        if url_input:
            urls = [url.strip() for url in url_input.split(',')]

    if not urls:
        print("URL не может быть пустым!")
        return

    # Очищаем файл перед началом обработки
    open('names_index.txt', 'w', encoding='utf-8').close()
    print("Файл names_index.txt очищен")

    all_hyperlinks = set()

    for i, url in enumerate(urls, 1):
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url

        print(f"\nОбрабатываем URL {i}/{len(urls)}: {url}")

        if 'fandom.com' not in url:
            print("Предупреждение: URL не принадлежит fandom.com")
            confirm = input("Продолжить? (y/n): ")
            if confirm.lower() != 'y':
                continue

        result, hyperlinks = save_text_from_fandom(url, args.debug)
        all_hyperlinks.update(hyperlinks)

        if result:
            print(f"Готово! Файл создан: {result}")
            print(f"Извлечено {len(hyperlinks)} ссылок из контента")
        else:
            print("Не удалось сохранить текст.")

    # Перезаписываем финальный отсортированный список всех гиперссылок
    if all_hyperlinks:
        save_hyperlinks_to_index(all_hyperlinks, args.debug)
        print(f"\nФинальный файл names_index.txt содержит {len(all_hyperlinks)} уникальных гиперссылок")

        if args.debug:
            print("Режим дебага: ссылки сохранены в формате 'текст <- URL_источника'")
        else:
            print("Примеры извлеченных ссылок:")
            for i, link in enumerate(sorted(all_hyperlinks)[:10], 1):
                print(f"  {i}. {link}")
    else:
        print("\nНе удалось извлечь гиперссылки из контента")

if __name__ == "__main__":
    main()