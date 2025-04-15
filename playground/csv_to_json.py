import csv
import json
import os
from typing import List, Dict, Any, Tuple, Optional

# --- ОБЩИЕ НАСТРОЙКИ ---
# Режим работы: 'extract' (из CSV в JSON) или 'apply' (из JSON в CSV)
# MODE: str = 'apply'  # ИЗМЕНИТЕ ЗДЕСЬ: 'extract' или 'apply'

# --- НАСТРОЙКИ ДЛЯ ОБОИХ РЕЖИМОВ ---
# Путь к ИСХОДНОМУ CSV файлу (читается в 'extract', читается как шаблон в 'apply')
CSV_INPUT_FILE: str = 'rules.csv'
# Путь к JSON файлу (создается в 'extract', читается в 'apply')
JSON_TRANSLATION_FILE: str = 'rules.json'
# Колонки для извлечения/применения перевода (номера через запятую, нумерация с 1)
COLUMNS_TO_TRANSLATE_STR: str = '5,6' # Например, для колонок 'text' и 'options' в вашем исходном примере
# Кодировка ИСХОДНОГО CSV файла
CSV_INPUT_ENCODING: str = 'utf-8'
# Кодировка JSON файла (рекомендуется utf-8)
JSON_ENCODING: str = 'utf-8'

# --- НАСТРОЙКИ ТОЛЬКО ДЛЯ РЕЖИМА 'apply' ---
# Путь к НОВОМУ CSV файлу с примененными переводами
CSV_OUTPUT_FILE: str = 'rules_ru.csv'
# Кодировка ВЫХОДНОГО CSV файла (рекомендуется utf-8 для совместимости)
CSV_OUTPUT_ENCODING: str = 'utf-8'
# Если в JSON для строки нет перевода (null или пустая строка),
# оставить оригинальное значение в CSV? True = оставить, False = заменить пустой строкой.
KEEP_ORIGINAL_IF_NO_TRANSLATION: bool = True
# ---------------------------------------------------------

def parse_column_indices(indices_str: str) -> List[int]:
    """Парсит строку с индексами колонок (1-based) в список 0-based индексов."""
    indices = []
    if not indices_str:
        raise ValueError("Строка с индексами колонок (COLUMNS_TO_TRANSLATE_STR) не может быть пустой.")
    parts = indices_str.split(',')
    for part in parts:
        part = part.strip()
        if not part.isdigit():
            raise ValueError(f"Неверный индекс колонки '{part}'. Индексы должны быть целыми положительными числами.")
        index = int(part)
        if index < 1:
            raise ValueError(f"Неверный индекс колонки '{part}'. Индексы должны быть 1 или больше.")
        indices.append(index - 1) # Преобразуем в 0-based для внутреннего использования
    if not indices:
        raise ValueError("Не указаны корректные индексы колонок.")
    # Убираем дубликаты и сортируем для предсказуемости
    unique_sorted_indices = sorted(list(set(indices)))
    print(f"Будут обработаны колонки (1-based): {[i + 1 for i in unique_sorted_indices]}")
    return unique_sorted_indices

def extract_texts_to_json(
    csv_filepath: str,
    json_filepath: str,
    column_indices: List[int],
    csv_encoding: str,
    json_encoding: str
):
    """
    Режим 'extract': Извлекает уникальные тексты из указанных колонок CSV
    и сохраняет их в JSON для перевода. (Версия с исправленной записью JSON)
    """
    print(f"\n--- РЕЖИМ: extract (CSV -> JSON) ---")
    print(f"Чтение CSV: {csv_filepath} (Кодировка: {csv_encoding})")
    print(f"Запись JSON: {json_filepath} (Кодировка: {json_encoding})")

    if not column_indices:
        print("Ошибка: Не указаны колонки для извлечения (COLUMNS_TO_TRANSLATE_STR пуст или некорректен).")
        return

    unique_texts_map: Dict[str, Dict[str, List[Tuple[int, int]]]] = {}
    header = []
    num_columns_in_csv = 0
    processed_rows = 0
    abs_csv_path = os.path.abspath(csv_filepath) # Получаем полный путь для сообщений

    try:
        print(f"DEBUG: Пытаюсь прочитать CSV из: {abs_csv_path}")
        with open(csv_filepath, 'r', encoding=csv_encoding, newline='') as csvfile:
            reader = csv.reader(csvfile)
            try:
                header = next(reader)
                num_columns_in_csv = len(header)
                print(f"Заголовок CSV ({num_columns_in_csv} колонок): {header}")

                # Проверяем, существуют ли указанные колонки
                max_requested_index = max(column_indices) if column_indices else -1
                if max_requested_index >= num_columns_in_csv:
                    raise IndexError(
                        f"Ошибка: Запрошен индекс колонки {max_requested_index + 1}, "
                        f"но в CSV файле всего {num_columns_in_csv} колонок."
                    )
                processed_rows = 1 # Учли строку заголовка

            except StopIteration:
                print("\n!!! Ошибка: CSV файл пустой или не содержит заголовка.")
                return
            except IndexError as e: # Перехват ошибки проверки индекса
                 print(f"\n!!! Ошибка конфигурации: {e}")
                 return
            except Exception as e:
                 print(f"\n!!! Ошибка чтения заголовка CSV: {e}")
                 traceback.print_exc()
                 return

            # Обрабатываем строки данных (начиная со строки 2)
            print("DEBUG: Начало обработки строк данных CSV...")
            for row_num, row in enumerate(reader, start=2):
                processed_rows += 1
                current_row_data_len = len(row)

                # Пропускаем некорректные строки или дополняем, если нужно
                if current_row_data_len < num_columns_in_csv:
                   print(f"Предупреждение: Строка {row_num} содержит меньше колонок ({current_row_data_len}), чем заголовок ({num_columns_in_csv}). Пропускаем обработку колонок в этой строке.")
                   # Если нужно дополнять: row.extend([''] * (num_columns_in_csv - current_row_data_len))
                   # continue # Если не дополняем, а пропускаем извлечение из этой строки

                for col_index_0based in column_indices:
                    # Дополнительная проверка на случай строк с разной длиной (если не дополняли выше)
                    if col_index_0based >= current_row_data_len:
                        continue # Пропускаем эту ячейку

                    original_text = row[col_index_0based]

                    # Игнорируем пустые строки или строки, состоящие только из пробелов
                    if not original_text.strip():
                        continue

                    location = (row_num, col_index_0based + 1) # Сохраняем 1-based индекс колонки

                    if original_text not in unique_texts_map:
                        unique_texts_map[original_text] = {"locations": []}
                    unique_texts_map[original_text]["locations"].append(location)

    except FileNotFoundError:
        print(f"\n!!! Ошибка: CSV файл не найден по пути {abs_csv_path}")
        return
    except PermissionError:
         print(f"\n!!! Ошибка: Отказано в доступе при чтении CSV файла {abs_csv_path}. Проверьте права.")
         return
    except UnicodeDecodeError as e:
        print(f"\n!!! Ошибка: Не удалось декодировать CSV файл '{os.path.basename(csv_filepath)}' с использованием кодировки '{csv_encoding}'. Строка ~{processed_rows} !!!")
        print(f"!!! Проверьте настройку CSV_INPUT_ENCODING. Ошибка: {e} !!!\n")
        traceback.print_exc()
        return
    except Exception as e:
        print(f"\n!!! Ошибка чтения CSV файла (строка ~{processed_rows}): {e}")
        traceback.print_exc()
        return

    # Преобразуем словарь в итоговый список для JSON
    output_data = []
    for text, data in unique_texts_map.items():
        output_data.append({
            "original": text,
            "translation": None, # Место для будущего перевода
            "_locations": data["locations"] # Сохраняем информацию о местоположении
        })

    # Сортируем для консистентности (опционально, но удобно)
    output_data.sort(key=lambda x: x["original"].lower()) # Сортировка без учета регистра

    print(f"\nНайдено {len(output_data)} уникальных непустых строк для перевода.")
    if not output_data:
        print("Уникальные строки не найдены. JSON файл не будет создан.")
        return

    # Записываем результат в JSON
    abs_json_path = os.path.abspath(json_filepath)
    print(f"Запись JSON: {abs_json_path} (Кодировка: {json_encoding})")
    try:
        # Создаем директорию, ТОЛЬКО если она указана в пути
        output_dir = os.path.dirname(abs_json_path)
        if output_dir: # Проверяем, что путь к директории не пустой
             # Добавим проверку прав перед созданием папки
             if not os.path.exists(output_dir):
                 print(f"DEBUG: Папка для JSON не существует, пытаюсь создать: {output_dir}")
                 try:
                     os.makedirs(output_dir, exist_ok=True)
                     print(f"DEBUG: Папка создана: {output_dir}")
                 except Exception as e_mkdir:
                     # Если не удалось создать папку, сообщаем и выходим ИЗ ФУНКЦИИ
                     print(f"\n!!! КРИТИЧЕСКАЯ ОШИБКА: Не удалось создать папку для JSON файла: {output_dir}")
                     print(f"!!! Ошибка системы: {e_mkdir}")
                     traceback.print_exc()
                     return # Выход из функции extract_texts_to_json
             elif not os.access(output_dir, os.W_OK):
                  print(f"\n!!! КРИТИЧЕСКАЯ ОШИБКА: Нет прав на запись в папку для JSON: {output_dir}")
                  return # Выход из функции extract_texts_to_json

        # Теперь открываем файл для записи
        print(f"DEBUG: Попытка открыть для записи JSON: {abs_json_path}")
        with open(json_filepath, 'w', encoding=json_encoding) as jsonfile:
            json.dump(output_data, jsonfile, ensure_ascii=False, indent=2)
        print("JSON файл для перевода успешно создан.")

    except FileNotFoundError as e: # Может возникнуть при open(), если путь все же невалиден
         print(f"\n!!! Ошибка FileNotFoundError при записи JSON: Не удалось открыть файл.")
         print(f"!!! Сообщение системы: {e}")
         print(f"!!! Проверьте путь: {abs_json_path}")
         traceback.print_exc()
    except PermissionError as e: # Может возникнуть при open(), если нет прав на файл
         print(f"\n!!! Ошибка PermissionError при записи JSON: Отказано в доступе.")
         print(f"!!! Сообщение системы: {e}")
         print(f"!!! Проверьте права на запись файла: {abs_json_path}")
         traceback.print_exc()
    except Exception as e:
        # Ловим все остальные ошибки при записи JSON
        print(f"\n!!! Ошибка записи JSON файла: {e}")
        traceback.print_exc()


def apply_translations_to_csv(
    json_filepath: str,
    csv_input_filepath: str,
    csv_output_filepath: str,
    column_indices: List[int],
    json_encoding: str,
    csv_input_encoding: str,
    csv_output_encoding: str,
    keep_original_if_no_translation: bool
):
    """
    Режим 'apply': Читает JSON с переводами и применяет их к исходному CSV,
    сохраняя результат в новый CSV файл. (Версия с улучшенной обработкой файлов)
    """
    print(f"\n--- РЕЖИМ: apply (JSON -> new CSV) ---")
    print(f"Чтение JSON с переводами: {json_filepath} (Кодировка: {json_encoding})")
    print(f"Чтение исходного CSV: {csv_input_filepath} (Кодировка: {csv_input_encoding})")
    print(f"Запись нового CSV с переводами: {csv_output_filepath} (Кодировка: {csv_output_encoding})")
    print(f"Оставлять оригинал при отсутствии перевода: {keep_original_if_no_translation}")

    # 1. Читаем JSON с переводами
    translations_data: List[Dict[str, Any]] = []
    try:
        abs_json_path = os.path.abspath(json_filepath)
        print(f"DEBUG: Пытаюсь прочитать JSON из: {abs_json_path}")
        with open(json_filepath, 'r', encoding=json_encoding) as f:
            translations_data = json.load(f)
    except FileNotFoundError:
        print(f"\n!!! Ошибка: JSON файл с переводами не найден: {abs_json_path}")
        return # Выходим, если нет файла с переводами
    except json.JSONDecodeError as e:
        print(f"\n!!! Ошибка декодирования JSON файла {json_filepath}: {e}")
        traceback.print_exc()
        return
    except Exception as e:
        print(f"\n!!! Неизвестная ошибка при чтении JSON файла {json_filepath}: {e}")
        traceback.print_exc()
        return

    if not isinstance(translations_data, list):
         print(f"\n!!! Ошибка: Ожидалось, что JSON файл ({json_filepath}) будет содержать список (массив), но получен {type(translations_data)}.")
         return

    # Создаем словарь для быстрого поиска перевода по оригинальному тексту
    translation_map: Dict[str, Optional[str]] = {}
    valid_translations_found = 0
    for item in translations_data:
        if isinstance(item, dict) and "original" in item and "translation" in item:
            # Сохраняем перевод, даже если он None или пустой,
            # чтобы обработать его согласно настройке keep_original_if_no_translation
            translation_map[item["original"]] = item["translation"]
            valid_translations_found += 1
        else:
            print(f"Предупреждение: Пропущен элемент в JSON файле из-за неверного формата: {item}")

    print(f"Загружено {valid_translations_found} записей из JSON файла.")
    if not translation_map:
        print("Предупреждение: Не найдено валидных записей для перевода в JSON файле. Выходной CSV не будет создан/изменен.")
        return # Нет смысла продолжать без переводов

    # 2. Читаем исходный CSV и пишем новый CSV

    # Инициализируем переменные перед блоком try
    infile = None
    outfile = None
    processed_rows = 0
    rows_written = 0
    translations_applied = 0
    header = []
    num_columns_in_csv = 0
    new_row = [] # Инициализируем на случай ошибки до первого цикла

    abs_csv_input_path = os.path.abspath(csv_input_filepath)
    abs_csv_output_path = os.path.abspath(csv_output_filepath)

    try:
        # Создаем директорию для выходного файла, если она не существует
        output_dir = os.path.dirname(abs_csv_output_path)
        if output_dir: # Создаем, только если путь не просто имя файла
             # Добавим проверку прав перед созданием папки
             if not os.path.exists(output_dir):
                 print(f"DEBUG: Папка для выходного CSV не существует, пытаюсь создать: {output_dir}")
                 try:
                     os.makedirs(output_dir, exist_ok=True)
                     print(f"DEBUG: Папка создана: {output_dir}")
                 except Exception as e_mkdir:
                     print(f"\n!!! КРИТИЧЕСКАЯ ОШИБКА: Не удалось создать папку для выходного файла: {output_dir}")
                     print(f"!!! Ошибка системы: {e_mkdir}")
                     return # Не можем продолжать без папки
             elif not os.access(output_dir, os.W_OK):
                  print(f"\n!!! КРИТИЧЕСКАЯ ОШИБКА: Нет прав на запись в папку: {output_dir}")
                  return # Не можем продолжать без прав на запись


        # Открываем файлы
        print(f"DEBUG: Попытка открыть для чтения: {abs_csv_input_path} (Кодировка: {csv_input_encoding})")
        infile = open(csv_input_filepath, 'r', encoding=csv_input_encoding, newline='')

        print(f"DEBUG: Попытка открыть для записи: {abs_csv_output_path} (Кодировка: {csv_output_encoding})")
        outfile = open(csv_output_filepath, 'w', encoding=csv_output_encoding, newline='')

        # --- Используем открытые файлы ---
        reader = csv.reader(infile)
        # Используем QUOTE_MINIMAL по умолчанию, можно изменить на QUOTE_ALL или QUOTE_NONNUMERIC
        writer = csv.writer(outfile, quoting=csv.QUOTE_MINIMAL)

        # Обработка заголовка
        try:
            header = next(reader)
            num_columns_in_csv = len(header)
            writer.writerow(header) # Записываем заголовок в новый файл
            rows_written += 1
            processed_rows += 1
            print(f"Заголовок CSV ({num_columns_in_csv} колонок) успешно прочитан и записан.")

            # Проверяем индексы колонок после чтения заголовка
            max_requested_index = max(column_indices) if column_indices else -1
            if max_requested_index >= num_columns_in_csv:
                # Выбрасываем ошибку, чтобы она была поймана внешним try/except
                raise IndexError(
                    f"Запрошен индекс колонки {max_requested_index + 1}, "
                    f"но в CSV файле всего {num_columns_in_csv} колонок."
                )

        except StopIteration:
            print("\n!!! Ошибка: Исходный CSV файл пустой или не содержит заголовка.")
            # Файлы будут закрыты в finally
            return # Выходим из функции
        except IndexError as e: # Ловим ошибку проверки индекса
             print(f"\n!!! Ошибка конфигурации: {e}")
             # Файлы будут закрыты в finally
             return
        except Exception as e:
             print(f"\n!!! Ошибка при обработке заголовка CSV: {e}")
             traceback.print_exc()
             # Файлы будут закрыты в finally
             raise # Перевыбрасываем критическую ошибку

        # Обработка строк данных
        print("DEBUG: Начало обработки строк данных...")
        for row_num, original_row in enumerate(reader, start=2):
            processed_rows += 1
            current_row_data_len = len(original_row)
            new_row = list(original_row) # Создаем копию для изменений

            # Обработка строк с неверным количеством колонок
            if current_row_data_len != num_columns_in_csv:
                print(f"Предупреждение: Строка {row_num} имеет {current_row_data_len} колонок вместо ожидаемых {num_columns_in_csv}. Строка будет записана как есть.")
                # Можно добавить логику дополнения/обрезки здесь, если нужно

            # Применяем переводы к нужным колонкам
            for col_index_0based in column_indices:
                 # Пропускаем, если индекс выходит за пределы *фактической* длины строки
                if col_index_0based >= current_row_data_len:
                    continue

                original_text = new_row[col_index_0based]

                # Ищем перевод только для непустых оригинальных строк
                if original_text.strip():
                    if original_text in translation_map:
                        translation = translation_map[original_text]

                        if translation is not None:
                             # Если перевод не пустой ИЛИ разрешено заменять пустой строкой
                             if translation or not keep_original_if_no_translation:
                                new_row[col_index_0based] = translation
                                translations_applied += 1
                             # Иначе (перевод пустой И keep_original_if_no_translation=True) - ничего не делаем, оставляем оригинал
                        # else: (если перевод null и keep_original_if_no_translation=True) - ничего не делаем
                    # else: (Текст не найден в карте переводов) - ничего не делаем

            # Записываем (измененную или оригинальную) строку в выходной файл
            writer.writerow(new_row)
            rows_written += 1

            # Опционально: выводить прогресс каждые N строк
            # if processed_rows % 100 == 0:
            #    print(f"DEBUG: Обработано строк: {processed_rows}")


        print(f"\nОбработка завершена.")
        print(f"  Прочитано строк из {os.path.basename(csv_input_filepath)}: {processed_rows}")
        print(f"  Записано строк в {os.path.basename(csv_output_filepath)}: {rows_written}")
        print(f"  Применено переводов (замен в ячейках): {translations_applied}")


    except FileNotFoundError as e:
        print(f"\n!!! Ошибка FileNotFoundError: Не удалось открыть файл.")
        print(f"!!! Сообщение системы: {e}")
        print(f"!!! Проверьте существование файла и права доступа.")
        # Попытка уточнить, какой файл вызвал проблему
        if e.filename == abs_csv_input_path:
             print(f"!!! Похоже, проблема с открытием для чтения: {abs_csv_input_path}")
        elif e.filename == abs_csv_output_path:
             print(f"!!! Похоже, проблема с открытием для записи: {abs_csv_output_path}")
        traceback.print_exc()
        # Не перевыбрасываем, т.к. уже дали подробный вывод
    except PermissionError as e:
        print(f"\n!!! Ошибка PermissionError: Отказано в доступе.")
        print(f"!!! Сообщение системы: {e}")
        print(f"!!! Проверьте права на чтение/запись для файлов и папок:")
        print(f"!!!   - Чтение: {abs_csv_input_path}")
        print(f"!!!   - Запись: {abs_csv_output_path}")
        traceback.print_exc()
    except UnicodeDecodeError as e:
         print(f"\n!!! Ошибка: Не удалось декодировать исходный CSV файл '{os.path.basename(csv_input_filepath)}' с использованием кодировки '{csv_input_encoding}'. Строка ~{processed_rows} !!!")
         print(f"!!! Проверьте настройку CSV_INPUT_ENCODING. Ошибка: {e} !!!")
         # Можно добавить вывод проблемного байта/позиции, если нужно: e.start, e.end, e.object
         traceback.print_exc()
    except UnicodeEncodeError as e:
         print(f"\n!!! Ошибка: Не удалось закодировать данные для записи в выходной CSV файл '{os.path.basename(csv_output_filepath)}' с использованием кодировки '{csv_output_encoding}'. Строка ~{processed_rows} !!!")
         print(f"!!! Проверьте настройку CSV_OUTPUT_ENCODING. Возможно, перевод содержит символы, не поддерживаемые этой кодировкой. Ошибка: {e} !!!")
         try:
             # Пытаемся показать проблемные данные, экранируя ошибки
             problematic_data_repr = repr(new_row).encode('unicode_escape').decode('ascii', 'ignore')
             print(f"!!! Проблемная строка (данные): {problematic_data_repr}")
         except NameError:
             pass # new_row еще не определена
         except Exception as repr_e:
             print(f"!!! Не удалось показать проблемную строку: {repr_e}")
         traceback.print_exc()
    except csv.Error as e:
         print(f"\n!!! Ошибка модуля CSV при обработке строки ~{processed_rows}: {e}")
         traceback.print_exc()
    except Exception as e:
        print(f"\n!!! Неизвестная ошибка при обработке CSV (строка ~{processed_rows}): {e}")
        traceback.print_exc()
        # Перевыбрасываем неизвестную ошибку, чтобы скрипт завершился некорректно
        raise
    finally:
        # Гарантированно закрываем файлы, если они были открыты
        closed_in = False
        closed_out = False
        if infile and not infile.closed:
            infile.close()
            closed_in = True
        if outfile and not outfile.closed:
            outfile.close()
            closed_out = True

        if closed_in: print("DEBUG: Входной CSV файл закрыт.")
        if closed_out: print("DEBUG: Выходной CSV файл закрыт.")


# --- Основной блок запуска ---
if __name__ == "__main__":
    # Получаем АБСОЛЮТНЫЙ путь к директории, где лежит ЭТОТ СКРИПТ (.py файл)
    script_dir = os.path.dirname(os.path.abspath(__file__))
    print(f"DEBUG: Каталог скрипта: {script_dir}")

    # --- Создаем ПОЛНЫЕ ПУТИ к файлам, ОТНОСИТЕЛЬНО КАТАЛОГА СКРИПТА ---

    
    abs_csv_input_path = os.path.join(script_dir, CSV_INPUT_FILE)
    abs_json_translation_path = os.path.join(script_dir, JSON_TRANSLATION_FILE)

    
    abs_csv_output_path = os.path.join(script_dir, CSV_OUTPUT_FILE)

  

    print(f"DEBUG: Полный путь к входному CSV: {abs_csv_input_path}")
    print(f"DEBUG: Полный путь к JSON: {abs_json_translation_path}")
    print(f"DEBUG: Полный путь к выходному CSV: {abs_csv_output_path}")

    MODE = None # Инициализируем переменную для режима
    while MODE not in ['extract', 'apply']:
        print("\nВыберите режим работы скрипта:")
        print("1: Извлечь тексты из CSV в JSON (режим 'extract')")
        print("2: Применить переводы из JSON в новый CSV (режим 'apply')")

        try:
            choice = input("Введите номер режима (1 или 2): ").strip() # .strip() убирает случайные пробелы

            if choice == '1':
                MODE = 'extract'
            elif choice == '2':
                MODE = 'apply'
            else:
                print("Ошибка: Неверный ввод. Пожалуйста, введите 1 или 2.")
        except (KeyboardInterrupt, EOFError): # Обработка прерывания ввода (Ctrl+C)
             print("\nВыбор режима прерван. Выход.")
             exit() # Завершаем скрипт

    print(f"Выбран режим: '{MODE}'")

    try:
        column_indices_0based = parse_column_indices(COLUMNS_TO_TRANSLATE_STR)

        if MODE == 'extract':
            extract_texts_to_json(
                csv_filepath=abs_csv_input_path,          # <--- Используем полный путь
                json_filepath=abs_json_translation_path, # <--- Используем полный путь
                column_indices=column_indices_0based,
                csv_encoding=CSV_INPUT_ENCODING,
                json_encoding=JSON_ENCODING
            )
        elif MODE == 'apply':
            apply_translations_to_csv(
                json_filepath=abs_json_translation_path, # <--- Используем полный путь
                csv_input_filepath=abs_csv_input_path,   # <--- Используем полный путь
                csv_output_filepath=abs_csv_output_path, # <--- Используем полный путь
                column_indices=column_indices_0based,
                json_encoding=JSON_ENCODING,
                csv_input_encoding=CSV_INPUT_ENCODING,
                csv_output_encoding=CSV_OUTPUT_ENCODING,
                keep_original_if_no_translation=KEEP_ORIGINAL_IF_NO_TRANSLATION
            )
        else:
            print(f"Ошибка: Неизвестный режим '{MODE}'. Установите MODE в 'extract' или 'apply'.")

    except ValueError as e: # Ловим ошибки валидации из parse_column_indices
        print(f"Ошибка конфигурации: {e}")
    except Exception as e:
        print(f"Произошла непредвиденная ошибка: {e}")
        import traceback
        traceback.print_exc()

    print("\nСкрипт завершил работу.")