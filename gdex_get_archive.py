import time
import gdex_client
import os
import tarfile
import glob

def clean_input_directory(target_dir="indata"):
    """
    Полностью очищает указанную папку от старых файлов (.grib2, .idx и др.)
    перед распаковкой нового архива, чтобы избежать смешивания данных.
    """
    if os.path.exists(target_dir):
        print(f"\n[INFO] Очистка папки '{target_dir}' от старых данных прошлых расчетов...")
        # Находим абсолютно все файлы внутри папки indata
        all_files = glob.glob(os.path.join(target_dir, "*.*"))
        
        deleted_count = 0
        for file_path in all_files:
            try:
                if os.path.isfile(file_path):
                    os.remove(file_path)
                    deleted_count += 1
            except Exception as e:
                print(f"[Предупреждение] Не удалось удалить файл {file_path}: {e}")
        
        if deleted_count > 0:
            print(f"[OK] Удалено старых файлов: {deleted_count}")
        else:
            print("[INFO] Папка изначально пуста.")
    else:
        # Если папки еще нет в системе, создаем её
        os.makedirs(target_dir)
        print(f"[INFO] Создана пустая папка '{target_dir}'")
        
def main():
    #print(gdex_client.get_metadata('d084001')) # или ds084.1
    
    control_file = "d084001_control_file"
    
    # 1. Запрос данных
    print(f"Submitting request with control file: {control_file}...")
    submit_response = gdex_client.submit(control_file)
    
    # 2. Из ответа получаем request_id (согласно вашему JSON)
    # Используем .get() для безопасного извлечения данных
    data_section = submit_response.get('data', {})
    request_id = data_section.get('request_id')
    
    if not request_id:
        print(f"Error: Could not find 'request_id' in response. Full response: {submit_response}")
        return

    print(f"Request submitted successfully. ID: {request_id}")

    # 3. Проверка статуса (цикл до "Completed")
    print("Waiting for request to complete...")
    while True:
        status_response = gdex_client.get_status(request_id)
        
        # Получаем текущий статус из структуры ответа
        # Основываясь на логике gdex, статус находится в data -> status
        current_status = status_response.get('data', {}).get('status')
        
        print(f"Current status: {current_status}")
        
        if current_status == "Completed":
            break
        elif current_status in ["Error", "Failed", "Cancelled"]:
            print(f"Request failed with status: {current_status}")
            return
            
        time.sleep(30)  # Пауза 30 секунд между проверками

    # 4. Загрузка архива и 5. Получение имени загружаемого файла
    print("Downloading files...")
    # Функция download в gdex_client возвращает метаданные файлов после загрузки
    download_info = gdex_client.download(request_id)

    # Создаем папку для данных, если она не существует
    target_dir = "indata"
    #if not os.path.exists(target_dir):
    #    os.makedirs(target_dir)
    # ЭТАП ОЧИСТКИ: Вызываем функцию очистки перед отправкой запроса и распаковкой
    clean_input_directory(target_dir)
    
    unique_archives = set()
    if 'data' in download_info and 'web_files' in download_info['data']:
        for file_entry in download_info['data']['web_files']:
            # Получаем имя файла из пути
            file_name = file_entry.get('web_path', '').split('/')[-1]
            unique_archives.add(file_name)
            #print(f"Downloaded file: {file_name}")

        for archive_name in unique_archives:
            if not archive_name:
                continue

            if os.path.exists(archive_name):
                print(f"Processing unique archive: {archive_name}")

                # Логика для TAR (tar.gz, tar)
                if archive_name.endswith(('.tar.gz', '.tar', '.tgz')):
                    with tarfile.open(archive_name, 'r:*') as tar_ref:
                        tar_ref.extractall(target_dir)#, filter='data')
                    print(f"Successfully extracted all files to {target_dir}")
                
            print(f"Extraction of {file_name} completed.")

            # Опционально: удаляем архив после распаковки, чтобы не дублировать данные
            # os.remove(archive_name)

    # 6. Удалить данные на сервере
    print(f"Purging request {request_id} from server...")
    purge_response = gdex_client.purge_request(request_id)
    print("Purge response:", purge_response.get('status', 'Done'))

if __name__ == "__main__":
    main()
