import sys
import os
import re
import argparse
import json
import random
from collections import defaultdict
try:
    import pymorphy2
    PYMOРHY2_AVAILABLE = True
except ImportError:
    PYMOРHY2_AVAILABLE = False

class TextProcessor:
    def __init__(self):
        self.morph = None
        if PYMOРHY2_AVAILABLE:
            try:
                self.morph = pymorphy2.MorphAnalyzer()
                print("pymorphy2 успешно загружен для проверки русского языка")
            except Exception as e:
                print(f"Ошибка инициализации pymorphy2: {e}")
                self.morph = None
        else:
            print("Предупреждение: pymorphy2 не установлен. Проверка русского языка будет ограничена.")

        # Для стадии S2
        self.token_map = {}  # Словарь для хранения замен токенов
        self.special_replacements = {
            'TIE': 'raumJr',
            'ТИЕ': 'РЖР',
            'AT': 'schr.gepanzerTr',
            'АТ': 'schr.gepanzerTr',
            'IG': 'hw.hoherLst',
            'ДБЯ': 'ДБА',
            'wing': 'Staffel'
        }

        # Для стадии S3 - таблицы замен букв
        # Неизменяемые символы: н, й, к, м, л, а, р, т, п, х, ъ, ь
        self.immutable_chars = {'н', 'й', 'к', 'м', 'л', 'а', 'р', 'т', 'п', 'х', 'ъ', 'ь',
                               'Н', 'Й', 'К', 'М', 'Л', 'А', 'Р', 'Т', 'П', 'Х', 'Ъ', 'Ь'}

        # Гласные для замены (исключая неизменяемую 'а')
        self.vowel_replacements = {
            'е': 'ё', 'и': 'ы', 'о': 'ю', 'у': 'э',
            'ё': 'е', 'ы': 'и', 'ю': 'о', 'э': 'у',
            'Е': 'Ё', 'И': 'Ы', 'О': 'Ю', 'У': 'Э',
            'Ё': 'Е', 'Ы': 'И', 'Ю': 'О', 'Э': 'У'
        }

        # Согласные для замены (исключая неизменяемые: н, й, к, м, л, р, т, п, х)
        self.consonant_replacements = {
            'б': 'в', 'в': 'б', 'г': 'д', 'д': 'г',
            'ж': 'з', 'з': 'ж', 'с': 'ф', 'ф': 'с',
            'ц': 'ч', 'ч': 'ц', 'ш': 'щ', 'щ': 'ш',
            'Б': 'В', 'В': 'Б', 'Г': 'Д', 'Д': 'Г',
            'Ж': 'З', 'З': 'Ж', 'С': 'Ф', 'Ф': 'С',
            'Ц': 'Ч', 'Ч': 'Ц', 'Ш': 'Щ', 'Щ': 'Ш'
        }

        # Русские гласные буквы
        self.russian_vowels = {'а', 'е', 'ё', 'и', 'о', 'у', 'ы', 'э', 'ю', 'я',
                              'А', 'Е', 'Ё', 'И', 'О', 'У', 'Ы', 'Э', 'Ю', 'Я'}

        # Русские согласные буквы
        self.russian_consonants = {'б', 'в', 'г', 'д', 'ж', 'з', 'й', 'к', 'л', 'м',
                                  'н', 'п', 'р', 'с', 'т', 'ф', 'х', 'ц', 'ч', 'ш', 'щ',
                                  'Б', 'В', 'Г', 'Д', 'Ж', 'З', 'Й', 'К', 'Л', 'М',
                                  'Н', 'П', 'Р', 'С', 'Т', 'Ф', 'Х', 'Ц', 'Ч', 'Ш', 'Щ'}

    def is_russian_word(self, word):
        """Проверка, является ли слово русским с помощью pymorphy2"""
        if not word or len(word) < 2:
            return False

        # Проверка с помощью pymorphy2
        if self.morph:
            try:
                parsed = self.morph.parse(word.lower())
                if parsed and hasattr(parsed[0], 'tag') and 'CYRL' in str(parsed[0].tag):
                    return True
            except Exception as e:
                print(f"Ошибка анализа слова '{word}': {e}")
                return False

        return False

    def process_stage_s1(self, input_file):
        """Обработка стадии S1"""
        print(f"Обработка стадии S1 для файла: {input_file}")

        # Файлы для записи
        names_file = input_file.replace('.txt', '-s1_names.txt')
        abbr_file = input_file.replace('.txt', '-s1_abbr.txt')
        terms_file = input_file.replace('.txt', '-s1_terms.txt')
        log_file = input_file.replace('.txt', '-s1.log')

        # Списки для каждой категории
        names_lines = []
        abbr_lines = []
        terms_lines = []

        # Множество для удаления дубликатов
        seen_lines = set()

        # Чтение входного файла
        try:
            with open(input_file, 'r', encoding='utf-8') as f:
                lines = [line.strip() for line in f if line.strip()]
        except FileNotFoundError:
            print(f"Ошибка: Файл {input_file} не найден")
            return
        except Exception as e:
            print(f"Ошибка чтения файла: {e}")
            return

        # Обработка каждой строки
        for line in lines:
            # Пропускаем пустые строки и дубликаты
            if not line or line in seen_lines:
                continue
            seen_lines.add(line)

            # Сначала проверяем на аббревиатуры (более строгие условия)
            if self._is_abbr_line(line):
                abbr_lines.append(line)
            # Затем проверяем на имена
            elif self._is_name_line(line):
                names_lines.append(line)
            # Все остальное в terms
            else:
                terms_lines.append(line)

        # Сортировка (case-insensitive)
        names_lines.sort(key=lambda x: x.lower())
        abbr_lines.sort(key=lambda x: x.lower())
        terms_lines.sort(key=lambda x: x.lower())

        # Запись в файлы
        self._write_lines_to_file(names_file, names_lines)
        self._write_lines_to_file(abbr_file, abbr_lines)
        self._write_lines_to_file(terms_file, terms_lines)

        # Статистика
        total_lines = len(names_lines) + len(abbr_lines) + len(terms_lines)
        stats = f"""Статистика обработки S1:
Файл names: {len(names_lines)} строк
Файл abbr: {len(abbr_lines)} строк
Файл terms: {len(terms_lines)} строк
Всего: {total_lines} строк
"""
        print(stats)

        # Проверка русских слов
        russian_matches = self._check_russian_words(names_lines, abbr_lines, terms_lines)

        # Запись в лог
        with open(log_file, 'w', encoding='utf-8') as log:
            log.write(stats)
            if russian_matches:
                log.write("\nРусские слова найдены в:\n")
                for match in russian_matches:
                    log.write(f"{match}\n")
                    print(f"Предупреждение: {match}")
            else:
                log.write("\nРусские слова не найдены.\n")

        print(f"Обработка S1 завершена. Лог сохранен в {log_file}")

    def _is_name_line(self, line):
        """Проверка, соответствует ли строка критериям names"""
        # Убираем лишние пробелы
        line = line.strip()

        # Условие 1: все слова начинаются с прописных букв
        # Апострофы и тире считаются частью слова
        words = re.findall(r'\b[\w\'’\-]+\b', line)
        if words:
            all_title_case = all(
                (word[0].isupper() and (len(word) == 1 or not word[1:].isupper()))
                or (word.startswith("'") and len(word) > 1 and word[1].isupper())
                or (word.startswith("’") and len(word) > 1 and word[1].isupper())
                for word in words
            )
            if all_title_case:
                return True

        # Условие 2: одно слово с прописной, другое - цифры/римские цифры
        # Используем пробелы как разделители (тире и апострофы - часть слов)
        parts = re.split(r'\s+', line)
        if len(parts) == 2:
            word1, word2 = parts
            if (word1 and word1[0].isupper() and
                self._is_roman_or_digits(word2)):
                return True
            if (word2 and word2[0].isupper() and
                self._is_roman_or_digits(word1)):
                return True

        return False

    def _is_roman_or_digits(self, text):
        """Проверка, состоит ли текст из римских цифр или цифр"""
        roman_pattern = r'^[IVXLCDMivxlcdm]+$'
        digits_pattern = r'^[0-9]+$'
        return bool(re.match(roman_pattern, text) or re.match(digits_pattern, text))

    def _is_abbr_line(self, line):
        """Проверка, соответствует ли строка критериям abbreviations"""
        line = line.strip()

        # Проверка на аббревиатуры с цифрами и дефисами (самое строгое условие)
        if re.match(r'^[A-Za-z0-9\'’\-\.]+$', line):
            return True

        # Проверка на римские цифры с буквами
        if re.match(r'^[A-Za-z\'’]+[-\s]?[IVXLCDM0-9]+$', line):
            return True

        # Проверка на комбинации букв, цифр, дефисов и точек
        if re.match(r'^[A-Za-z0-9\'’\-\.\s]+$', line):
            # Убедимся, что это не обычное слово
            words = re.split(r'\s+', line)
            if len(words) == 1 and not any(word.isalpha() and len(word) > 3 for word in words):
                return True

        # Проверка на русские прописные аббревиатуры
        if re.match(r'^[А-Я0-9\'’\-\.]+$', line):
            return True

        return False

    def _check_russian_words(self, names_lines, abbr_lines, terms_lines):
        """Поиск русских слов в строках"""
        matches = []

        # Проверка файла names
        for i, line in enumerate(names_lines, 1):
            # Ищем русские слова, игнорируя апострофы и тире внутри слов
            words = re.findall(r'\b[а-яА-ЯёЁ]+[а-яА-ЯёЁ\'’\-]*[а-яА-ЯёЁ]*\b', line)
            for word in words:
                # Убираем апострофы и тире для проверки
                clean_word = re.sub(r'[\'’\-]', '', word)
                if clean_word and self.is_russian_word(clean_word):
                    matches.append(f"names.txt - строка {i}: {line} (слово: {word})")

        # Проверка файла abbr
        for i, line in enumerate(abbr_lines, 1):
            words = re.findall(r'\b[а-яА-ЯёЁ]+[а-яА-ЯёЁ\'’\-]*[а-яА-ЯёЁ]*\b', line)
            for word in words:
                clean_word = re.sub(r'[\'’\-]', '', word)
                if clean_word and self.is_russian_word(clean_word):
                    matches.append(f"abbr.txt - строка {i}: {line} (слово: {word})")

        # Проверка файла terms
        for i, line in enumerate(terms_lines, 1):
            words = re.findall(r'\b[а-яА-ЯёЁ]+[а-яА-ЯёЁ\'’\-]*[а-яА-ЯёЁ]*\b', line)
            for word in words:
                clean_word = re.sub(r'[\'’\-]', '', word)
                if clean_word and self.is_russian_word(clean_word):
                    matches.append(f"terms.txt - строка {i}: {line} (слово: {word})")

        return matches

    def _write_lines_to_file(self, filename, lines):
        """Запись строк в файл"""
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                for line in lines:
                    f.write(line.strip() + '\n')
            print(f"Создан файл: {filename} ({len(lines)} строк)")
        except Exception as e:
            print(f"Ошибка записи в файл {filename}: {e}")

    def _is_russian_lowercase_word(self, token):
        """Проверка, является ли токен словом из строчных русских букв"""
        if not token:
            return False

        # Убираем апострофы и тире для проверки
        clean_token = re.sub(r'[\'’\-]', '', token)
        if not clean_token:
            return False

        # Проверяем, что все символы - строчные русские буквы
        if not re.match(r'^[а-яё]+$', clean_token):
            return False

        # Дополнительная проверка с pymorphy2
        if self.morph:
            try:
                parsed = self.morph.parse(clean_token)
                if parsed and hasattr(parsed[0], 'tag') and 'CYRL' in str(parsed[0].tag):
                    return True
            except:
                return False

        return True

    def _generate_replacement(self, token):
        """Генерация замены для токенов"""
        # Проверяем специальные замены
        if token in self.special_replacements:
            return self.special_replacements[token]

        # Проверяем, является ли токен словом из строчных русских букв
        if self._is_russian_lowercase_word(token):
            return token  # Оставляем как есть

        # Проверяем, есть ли уже замена для этого токена
        if token in self.token_map:
            return self.token_map[token]

        # Генерируем новую замену
        replacement = ''

        for char in token:
            if char.isupper() and 'A' <= char <= 'Z':
                # Прописная английская буква
                replacement += random.choice('ABCDEFGHIJKLMNOPQRSTUVWXYZ')
            elif char.islower() and 'a' <= char <= 'z':
                # Строчная английская буква
                replacement += random.choice('abcdefghijklmnopqrstuvwxyz')
            elif char.isupper() and 'А' <= char <= 'Я':
                # Прописная русская буква
                replacement += random.choice('АБВГДЕЁЖЗИЙКЛМНОПРСТУФХЦЧШЩЪЫЬЭЮЯ')
            elif char.islower() and 'а' <= char <= 'я':
                # Строчная русская буква (но не слово)
                replacement += random.choice('абвгдеёжзийклмнопрстуфхцчшщъыьэюя')
            elif char.isdigit():
                # Цифра
                replacement += random.choice('0123456789')
            elif char in ['\'', '’', '-']:
                # Апострофы и тире оставляем как есть
                replacement += char
            else:
                # Оставляем другие символы как есть
                replacement += char

        # Сохраняем замену в словаре
        self.token_map[token] = replacement
        return replacement

    def _tokenize_line(self, line):
        """Разбитие строки на токены и разделители"""
        # Используем регулярное выражение для разделения
        # Апострофы и тире считаются частью токенов
        pattern = r'([\s\.\/])|([A-Za-zА-Яа-я0-9\'’\-]+)'
        tokens = []
        separators = []

        for match in re.finditer(pattern, line):
            if match.group(1):  # Разделитель (пробел, точка, слэш)
                separators.append(match.group(1))
                tokens.append(None)
            elif match.group(2):  # Токен (буквы, цифры, апострофы, тире)
                tokens.append(match.group(2))
                separators.append(None)

        return tokens, separators

    def process_stage_s2(self, input_file):
        """Обработка стадии S2"""
        print(f"Обработка стадии S2 для файла: {input_file}")

        # Читаем файл с аббревиатурами из S1
        abbr_file = input_file.replace('.txt', '-s1_abbr.txt')
        output_file = input_file.replace('.txt', '-s2_abbr.txt')
        token_repl_file = 'names_index_reviewed-s2_abbr_token_repl.json'
        string_repl_file = 'terms_map-s2_abbr.json'

        if not os.path.exists(abbr_file):
            print(f"Ошибка: Файл {abbr_file} не найден. Сначала выполните стадию S1.")
            return

        try:
            with open(abbr_file, 'r', encoding='utf-8') as f:
                lines = [line.strip() for line in f if line.strip()]
        except Exception as e:
            print(f"Ошибка чтения файла {abbr_file}: {e}")
            return

        # Обрабатываем каждую строку
        processed_lines = []
        string_replacement_pairs = {}  # Пары: входная строка -> выходная строка
        token_replacement_pairs = {}   # Пары: токен -> замена

        print("\nПары замен строк:")
        print("-" * 80)

        for line in lines:
            # Разбиваем строку на токены и разделители
            tokens, separators = self._tokenize_line(line)

            # Обрабатываем каждый токен
            processed_tokens = []
            for i, token in enumerate(tokens):
                if token is None:  # Разделитель
                    processed_tokens.append(separators[i])
                else:
                    replacement = self._generate_replacement(token)
                    processed_tokens.append(replacement)
                    # Сохраняем пару токен-замена (только если замена отличается)
                    if token != replacement:
                        token_replacement_pairs[token] = replacement

            # Собираем обработанную строку
            processed_line = ''.join(processed_tokens)
            processed_lines.append(processed_line)

            # Сохраняем пару строка-замена
            string_replacement_pairs[line] = processed_line

            # Выводим пару замены строк
            print(f"{line} -> {processed_line}")

        # Записываем обработанные строки
        with open(output_file, 'w', encoding='utf-8') as f:
            for line in processed_lines:
                f.write(line + '\n')

        # Сохраняем словарь замен токенов в JSON
        with open(token_repl_file, 'w', encoding='utf-8') as f:
            json.dump(token_replacement_pairs, f, ensure_ascii=False, indent=2)

        # Сохраняем словарь замен строк в JSON
        with open(string_repl_file, 'w', encoding='utf-8') as f:
            json.dump(string_replacement_pairs, f, ensure_ascii=False, indent=2)

        print("-" * 80)
        print(f"Создан файл: {output_file} ({len(processed_lines)} строк)")
        print(f"Создан файл замен токенов: {token_repl_file}")
        print(f"Создан файл замен строк: {string_repl_file}")
        print(f"Статистика S2: {len(processed_lines)} строк")

    def _is_quoted_string(self, line):
        """Проверка, является ли строка строкой в кавычках"""
        line = line.strip()
        return (line.startswith('"') and line.endswith('"')) or \
               (line.startswith('«') and line.endswith('»')) or \
               (line.startswith('»') and line.endswith('«'))

    def _get_synonym_or_antonym(self, word):
        """Получение синонима или антонима для слова (упрощенная версия)"""
        if not self.morph:
            return word

        try:
            parsed = self.morph.parse(word)[0]

            # Простая замена на основе морфологического анализа
            if word.lower() in ['хороший', 'добрый', 'отличный']:
                return 'плохой' if random.choice([True, False]) else 'ужасный'
            elif word.lower() in ['плохой', 'ужасный', 'скверный']:
                return 'хороший' if random.choice([True, False]) else 'отличный'
            elif word.lower() in ['большой', 'крупный', 'огромный']:
                return 'маленький' if random.choice([True, False]) else 'крошечный'
            elif word.lower() in ['маленький', 'небольшой', 'крошечный']:
                return 'большой' if random.choice([True, False]) else 'огромный'

            # Если слово не найдено в нашем упрощенном словаре, возвращаем как есть
            return word

        except:
            return word

    def _replace_letter(self, char):
        """Замена буквы согласно таблицам замен"""
        # Проверяем, является ли символ неизменяемым
        if char in self.immutable_chars:
            return char

        # Проверяем таблицы замен
        if char in self.vowel_replacements:
            return self.vowel_replacements[char]
        elif char in self.consonant_replacements:
            return self.consonant_replacements[char]
        else:
            # Оставляем другие символы как есть (латинские буквы, цифры, знаки, апострофы, тире)
            return char

    def _process_quoted_string(self, line):
        """Обработка строки в кавычках"""
        # Убираем кавычки
        content = line.strip()
        if content.startswith('"') and content.endswith('"'):
            content = content[1:-1]
        elif (content.startswith('«') and content.endswith('»')) or \
             (content.startswith('»') and content.endswith('«')):
            content = content[1:-1]

        # Разбиваем на слова и обрабатываем каждое
        # Апострофы и тире считаются частью слов
        words = re.findall(r'\b[\w\'’\-]+\b|[^\w\s]', content)
        processed_words = []

        for word in words:
            if re.match(r'^[\w\'’\-]+$', word):  # Если это слово (с апострофами и тире)
                processed_words.append(self._get_synonym_or_antonym(word))
            else:  # Если это не слово (знаки препинания и т.д.)
                processed_words.append(word)

        # Собираем обратно с сохранением оригинальных кавычек
        processed_content = ''.join(processed_words)
        if line.startswith('"') and line.endswith('"'):
            return f'"{processed_content}"'
        else:
            return f'«{processed_content}»'

    def _process_regular_string(self, line):
        """Обработка обычной строки (побуквенная замена)"""
        result = []
        for char in line:
            # Определяем тип символа
            if char in self.immutable_chars:
                # Неизменяемые символы остаются как есть
                result.append(char)
            elif char in self.russian_vowels:
                # Гласные буквы (кроме неизменяемых)
                result.append(self.vowel_replacements.get(char, char))
            elif char in self.russian_consonants:
                # Согласные буквы (кроме неизменяемых)
                result.append(self.consonant_replacements.get(char, char))
            else:
                # Все остальные символы (латинские буквы, цифры, знаки препинания, апострофы, тире)
                result.append(char)
        return ''.join(result)

    def _find_duplicate_words_in_terms(self, input_file):
        """Поиск повторяющихся слов в файле terms"""
        terms_file = input_file.replace('.txt', '-s1_terms.txt')

        if not os.path.exists(terms_file):
            print("Ошибка: Файл terms не найден. Сначала выполните стадию S1.")
            return

        # Чтение файла
        words_dict = defaultdict(list)

        try:
            with open(terms_file, 'r', encoding='utf-8') as f:
                lines = [line.strip() for line in f if line.strip()]
        except Exception as e:
            print(f"Ошибка чтения файла {terms_file}: {e}")
            return

        # Извлекаем слова с позициями
        for line_num, line in enumerate(lines, 1):
            # Извлекаем слова (игнорируем регистр, апострофы и тире - часть слов)
            words = re.findall(r'\b[a-zA-Zа-яА-ЯёЁ\'’\-]+\b', line)
            for word in words:
                lower_word = word.lower()
                words_dict[lower_word].append(line_num)

        print("\nПоиск повторяющихся слов в terms.txt:")
        print("-" * 80)

        # Поиск дубликатов
        found_duplicates = False

        for word, line_numbers in words_dict.items():
            if len(line_numbers) > 1:
                found_duplicates = True
                line_numbers_str = ", ".join(map(str, line_numbers))
                print(f"Слово: '{word}' - строки: {line_numbers_str}")

        if not found_duplicates:
            print("Повторяющиеся слова не найдены.")

        print("-" * 80)

    def _sort_terms_file(self, input_file):
        """Сортировка файла terms по алфавиту"""
        terms_file = input_file.replace('.txt', '-s1_terms.txt')

        if not os.path.exists(terms_file):
            print(f"Файл {terms_file} не найден, пропускаем сортировку")
            return

        try:
            with open(terms_file, 'r', encoding='utf-8') as f:
                lines = [line.strip() for line in f if line.strip()]

            # Сортировка без учета регистра
            lines.sort(key=lambda x: x.lower())

            # Перезаписываем файл
            with open(terms_file, 'w', encoding='utf-8') as f:
                for line in lines:
                    f.write(line + '\n')

            print(f"Файл {terms_file} отсортирован по алфавиту ({len(lines)} строк)")

        except Exception as e:
            print(f"Ошибка при сортировке файла {terms_file}: {e}")

    def process_stage_s3(self, input_file):
        """Обработка стадии S3"""
        print(f"Обработка стадии S3 для файла: {input_file}")

        # 1. Сортировка файла terms по алфавиту
        self._sort_terms_file(input_file)

        # 2. Поиск повторяющихся слов в terms
        self._find_duplicate_words_in_terms(input_file)

        # 3. Обработка терминов (оригинальная функциональность)
        terms_file = input_file.replace('.txt', '-s1_terms.txt')
        output_file = input_file.replace('.txt', '-s3_terms.txt')
        json_file = 'terms_map-s3_terms.json'

        if not os.path.exists(terms_file):
            print(f"Ошибка: Файл {terms_file} не найден. Сначала выполните стадию S1.")
            return

        try:
            with open(terms_file, 'r', encoding='utf-8') as f:
                lines = [line.strip() for line in f if line.strip()]
        except Exception as e:
            print(f"Ошибка чтения файла {terms_file}: {e}")
            return

        # Обрабатываем каждую строку
        processed_lines = []
        replacement_pairs = {}

        print("\nПары замен строк для S3:")
        print("-" * 80)

        for line in lines:
            if self._is_quoted_string(line):
                # Обработка строк в кавычках
                processed_line = self._process_quoted_string(line)
            else:
                # Обработка обычных строк
                processed_line = self._process_regular_string(line)

            processed_lines.append(processed_line)
            replacement_pairs[line] = processed_line

            # Выводим пару замены
            print(f"{line} -> {processed_line}")

        # Записываем обработанные строки
        with open(output_file, 'w', encoding='utf-8') as f:
            for line in processed_lines:
                f.write(line + '\n')

        # Сохраняем словарь замен в JSON
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(replacement_pairs, f, ensure_ascii=False, indent=2)

        print("-" * 80)
        print(f"Создан файл: {output_file} ({len(processed_lines)} строк)")
        print(f"Создан JSON файл: {json_file}")
        print(f"Статистика S3: {len(processed_lines)} строк")

def get_input_files():
    """Получение входных файлов одним из способов"""
    # Способ 1: аргументы командной строки
    if len(sys.argv) >= 3:
        input_file = sys.argv[1]
        corpus_dir = sys.argv[2]
        if os.path.isfile(input_file) and os.path.isdir(corpus_dir):
            return input_file, corpus_dir

    # Способ 2: файлы по умолчанию
    default_file = 'names_index_reviewed.txt'
    default_dir = 'knowledge_base_source_reviewed'

    if os.path.isfile(default_file) and os.path.isdir(default_dir):
        return default_file, default_dir

    # Способ 3: ручной ввод
    print("Файлы не найдены автоматически. Пожалуйста, укажите вручную:")

    while True:
        input_file = input("Введите путь к файлу с именами и понятиями: ").strip()
        if os.path.isfile(input_file):
            break
        print("Файл не найден. Попробуйте еще раз.")

    while True:
        corpus_dir = input("Введите путь к каталогу с корпусом текстов: ").strip()
        if os.path.isdir(corpus_dir):
            break
        print("Каталог не найден. Попробуйте еще раз.")

    return input_file, corpus_dir

def main():
    parser = argparse.ArgumentParser(description='Обработчик текстовых данных')
    parser.add_argument('-s1', action='store_true', help='Выполнить стадию S1')
    parser.add_argument('-s2', action='store_true', help='Выполнить стадию S2')
    parser.add_argument('-s3', action='store_true', help='Выполнить стадию S3')

    args = parser.parse_args()

    # Если не указаны ключи, используем все стадии
    if not any([args.s1, args.s2, args.s3]):
        args.s1 = args.s2 = args.s3 = True

    # Получаем входные файлы
    input_file, corpus_dir = get_input_files()
    print(f"Используется файл: {input_file}")
    print(f"Используется каталог: {corpus_dir}")

    # Создаем процессор
    processor = TextProcessor()

    # Выполняем указанные стадии
    if args.s1:
        processor.process_stage_s1(input_file)

    if args.s2:
        processor.process_stage_s2(input_file)

    if args.s3:
        processor.process_stage_s3(input_file)

if __name__ == "__main__":
    main()