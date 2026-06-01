import os

def htc_file_button_click(output_folder_path: str):
    """
    Объединяет файлы meteo-параметров (Rhum, Tair, Cloud) в один файл Result.htc.
    Все уведомления и ошибки выводятся через print().
    
    :param output_folder_path: Путь к папке с файлами результатов (например, 'outdata')
    """
    # Гарантируем, что путь заканчивается слэшем
    if output_folder_path and not output_folder_path.endswith(os.sep):
        output_folder_path += os.sep

    print(f"\n=== Начало объединения файлов в папке '{output_folder_path}' ===")

    # Инициализируем списки строк (аналоги TStringList)
    rhum_lines = []
    tair_lines = []
    cloud_lines = []
    result_lines = []

    done = True

    # Пути к файлам
    rhum_path = os.path.join(output_folder_path, "Rhum.amr")
    tair_path = os.path.join(output_folder_path, "Tair.amt")
    cloud_path = os.path.join(output_folder_path, "Cloud.amc")

    # Безопасная загрузка файлов (каждый проверяется независимо)
    if os.path.exists(rhum_path):
        with open(rhum_path, 'r', encoding='utf-8') as f:
            rhum_lines = [line.rstrip('\n') for line in f]
    else:
        print(f"[ERROR] Файл не найден: {rhum_path}")

    if os.path.exists(tair_path):
        with open(tair_path, 'r', encoding='utf-8') as f:
            tair_lines = [line.rstrip('\n') for line in f]
    else:
        print(f"[ERROR] Файл не найден: {tair_path}")

    if os.path.exists(cloud_path):
        with open(cloud_path, 'r', encoding='utf-8') as f:
            cloud_lines = [line.rstrip('\n') for line in f]
    else:
        print(f"[ERROR] Файл не найден: {cloud_path}")

    # Поиск значения n_rows в мета-заголовке файла Rhum
    n_rows = 0
    for line in rhum_lines:
        if line.strip().startswith("n_rows"):
            if "=" in line:
                parts = line.split("=")
                if len(parts) > 1:
                    try:
                        n_rows = int(parts[1].strip())
                    except ValueError:
                        n_rows = 0
            break

    if n_rows == 0:
        done = False
        print("[ERROR] Не удалось определить параметр n_rows из файла Rhum.amr!")
    else:
        print(f"[INFO] Количество строк (n_rows) определено: {n_rows}")
        i = 0
        rhum_count = len(rhum_lines)
        
        while i < rhum_count:
            s = rhum_lines[i]
            result_lines.append(rhum_lines[i])
            i += 1

            fn = ""
            try:
                if "TIME" in s:
                    # Чтение блока Rhum
                    fn = "Rhum.amr"
                    for k in range(n_rows):
                        result_lines.append(rhum_lines[i + k])

                    # Чтение блока Tair
                    fn = "Tair.amt"
                    for k in range(n_rows):
                        result_lines.append(tair_lines[i + k])

                    # Чтение блока Cloud
                    fn = "Cloud.amc"
                    for k in range(n_rows):
                        result_lines.append(cloud_lines[i + k])

                    i += n_rows
            except IndexError:
                done = False
                print(f"[ERROR] Данные исходного файла {fn} неполные на позиции строки {i}!")
                break

    # Сохранение итогового файла
    if done and result_lines:
        result_path = os.path.join(output_folder_path, "Meteo.hac")
        try:
            with open(result_path, 'w', encoding='utf-8') as f:
                for line in result_lines:
                    f.write(line + '\n')
            print(f"[OK] Объединение файлов выполнено успешно! Создан: {result_path}")
        except Exception as e:
            print(f"[ERROR] Не удалось сохранить итоговый файл Result.htc: {e}")
    else:
        print("[ERROR] Объединение прервано из-за ошибок в структуре данных.")

if __name__ == "__main__":
    # Скрипт можно запустить самостоятельно для проверки
    htc_file_button_click("outdata")
