import os
import json
import regex
from collections import OrderedDict

# === Пути ===
TERMS_MAP_FILE = "terms_map.json"
SOURCE_DIR = "knowledge_base_source_reviewed"
TARGET_DIR = "knowledge_base_final"
LOG_FILE = "names_index_reviewed-s4.log"

# === Подготовка выходной директории ===
os.makedirs(TARGET_DIR, exist_ok=True)

# === Загрузка и сортировка terms_map.json ===
def load_terms_map_sorted(filepath):
    with open(filepath, "r", encoding="utf-8") as f:
        terms = json.load(f)
    sorted_terms = sorted(terms.items(), key=lambda x: x[0].lower())
    return list(reversed(sorted_terms))  # Обработка от конца к началу

# === Корректировка регистра ===
def adjust_case(original, replacement):
    if original[0].isupper():
        return replacement[0].upper() + replacement[1:]
    else:
        return replacement[0].lower() + replacement[1:]

# === Регулярное выражение для начала слова ===
# Началом слова считается: пробел, табуляция, \n, ", «, _, (, [, -
START_BOUNDARY_CHARS = r"[\s\t\n\"«_[(\-]"

# === Замена терминов в тексте ===
def replace_terms_in_text(text, terms):
    replacements_log = {}

    for key, value in terms:
        key_escaped = regex.escape(key)
        # (?<=...) - positive lookbehind, проверка начала "слова"
        pattern = regex.compile(
            rf"(?i)(?<={START_BOUNDARY_CHARS}|^){key_escaped}(?=\X*)"
        )

        def sub_func(match):
            matched = match.group(0)
            replaced = adjust_case(matched, value)
            replacements_log.setdefault((matched, replaced), 0)
            replacements_log[(matched, replaced)] += 1
            return replaced

        text = pattern.sub(sub_func, text)

    return text, replacements_log

# === Замена терминов в имени файла ===
def replace_terms_in_filename(filename, terms):
    name, ext = os.path.splitext(filename)
    for key, value in terms:
        key_escaped = regex.escape(key)
        pattern = regex.compile(
            rf"(?i)(?<={START_BOUNDARY_CHARS}|^){key_escaped}(?=\X*)"
        )

        def sub_func(match):
            matched = match.group(0)
            return adjust_case(matched, value)

        name = pattern.sub(sub_func, name)
    return name + ext

# === Обработка всех файлов ===
def process_all_files(terms):
    log_lines = []

    for filename in os.listdir(SOURCE_DIR):
        if not filename.endswith(".txt"):
            continue

        source_path = os.path.join(SOURCE_DIR, filename)

        # Заменяем имя файла
        new_filename = replace_terms_in_filename(filename, terms)
        target_path = os.path.join(TARGET_DIR, new_filename)

        with open(source_path, "r", encoding="utf-8") as f:
            original_text = f.read()

        updated_text, replacements = replace_terms_in_text(original_text, terms)

        # Сохраняем изменённый файл
        with open(target_path, "w", encoding="utf-8") as f:
            f.write(updated_text)

        # Лог
        log_lines.append(f"Файл: {filename} → {new_filename if new_filename != filename else filename}")
        total = 0
        for (orig, repl), count in sorted(replacements.items()):
            log_lines.append(f"  Заменено: {orig} → {repl} ({count} раз(а))")
            total += count
        log_lines.append(f"  Всего замен: {total}\n")

    # Сохраняем лог
    with open(LOG_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(log_lines))

# === Точка входа ===
if __name__ == "__main__":
    if not os.path.exists(TERMS_MAP_FILE):
        print(f"❌ Файл {TERMS_MAP_FILE} не найден.")
        exit(1)

    terms = load_terms_map_sorted(TERMS_MAP_FILE)
    process_all_files(terms)
    print(f"✅ Обработка завершена. Лог сохранён в {LOG_FILE}")
