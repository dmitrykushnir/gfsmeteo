import xarray as xr
import numpy as np
import os
import glob
import re
from datetime import datetime

# Папки для ввода и вывода данных
INPUT_DIR = 'indata'
OUTPUT_DIR = 'outdata'

# План извлечения и метаданные параметров для заголовка
# Формат: 'Ключ': (grib_var, filters, quantity1, unit1, file_extension)
extraction_plan = {
    'Tair':       ('t2m',   {'typeOfLevel': 'heightAboveGround', 'level': 2}, 'air_temperature', 'Celsius', '.amt'),
    'Rhum':        ('r2',    {'typeOfLevel': 'heightAboveGround', 'level': 2}, 'relative_humidity', '%', '.amr'),
    'Uwind':    ('u10',   {'typeOfLevel': 'heightAboveGround', 'level': 10}, 'x_wind', 'm s-1', '.amu'),
    'Vwind':    ('v10',   {'typeOfLevel': 'heightAboveGround', 'level': 10}, 'y_wind', 'm s-1', '.amv'),
    'Pres0': ('sp',    {'typeOfLevel': 'surface'}, 'air_pressure', 'Pa', '.amp'),
    'Presair':        ('prmsl', {'typeOfLevel': 'meanSea'}, 'air_pressure', 'Pa', '.amp'),
    'Cloud':        ('tcc',   {'typeOfLevel': 'atmosphere'}, 'cloudiness', '%', '.amc'),
}

def parse_gfs_datetime(filename):
    """Извлекает дату и время из имени файла GFS."""
    match = re.search(r'(\d{10})\.f\d{3}', filename)
    if match:
        date_str = match.group(1)
        return datetime.strptime(date_str, '%Y%m%d%H')
    return None

def process_all_gribs():
    # Находим все файлы grib2 в папке indata
    file_pattern = os.path.join(INPUT_DIR, 'gfs.0p25.*.f000.grib2')
    files = sorted(glob.glob(file_pattern))

    if not files:
        print(f"Ошибка: В папке '{INPUT_DIR}' не найдены файлы GRIB2.")
        return

    print(f"Найдено файлов для обработки: {len(files)}")

    # Создаем папку для результатов, если ее нет
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)
        print(f"Создана папка для результатов: {OUTPUT_DIR}")

    # Определяем базовое время по первому файлу
    base_time = parse_gfs_datetime(os.path.basename(files[0]))
    base_time_str = base_time.strftime('%Y-%m-%d %H:%M:%S')
    print(f"Базовое время отсчета (TIME = 0.0): {base_time_str}")

    # Очищаем старые файлы результатов перед началом работы
    #output_files = list(extraction_plan.keys()) + ['coords']
    #for out_name in output_files:
    for out_name, (_, _, _, _, ext) in extraction_plan.items():
        filename = os.path.join(OUTPUT_DIR, f"{out_name}{ext}")
        if os.path.exists(filename):
            os.remove(filename)
            print(f"Старый файл {filename} удален.")

    # Также очищаем файл координат
    coords_path = os.path.join(OUTPUT_DIR, 'Node_coordinates.txt')
    if os.path.exists(coords_path):
        os.remove(coords_path)

    # Переменные для хранения параметров сетки (вычисляются один раз)
    grid_info = {}
    lats, lons = None, None

    # Цикл по всем файлам GRIB
    for file_idx, file_path in enumerate(files):
        filename_base = os.path.basename(file_path)
        current_time = parse_gfs_datetime(filename_base)
        
        if not current_time:
            print(f"[Уведомление] Не удалось прочесть дату из {filename_base}, пропускаем.")
            continue

        # Вычисляем разницу в часах
        hours_since = (current_time - base_time).total_seconds() / 3600.0
        time_marker = f"TIME = {hours_since:.1f} hours since {base_time_str}"
        
        print(f"\n=== Обработка файла [{file_idx+1}/{len(files)}]: {filename_base} ===")
        print(f"Маркер времени: {time_marker}")

        # Удаляем индексный файл cfgrib
        idx_file = file_path + '.idx'
        if os.path.exists(idx_file):
            try: os.remove(idx_file)
            except Exception: pass

        # Перебираем переменные по плану
        for out_name, (grib_var, filters, quantity1, unit1, ext) in extraction_plan.items():
            try:
                ds = xr.open_dataset(
                    file_path, 
                    engine='cfgrib', 
                    backend_kwargs={'filter_by_keys': filters, 'indexpath': ''}
                )

                # Инициализация параметров сетки (один раз за скрипт)
                if lats is None:
                    lats = ds.latitude.values
                    lons = ds.longitude.values
                    
                    # Расчет параметров для заголовка
                    grid_info['n_cols'] = len(lons)
                    grid_info['n_rows'] = len(lats)
                    grid_info['x_llcorner'] = float(np.min(lons))
                    grid_info['y_llcorner'] = float(np.min(lats))
                    
                    # Шаг сетки (абсолютное значение, чтобы избежать отрицательного dy)
                    grid_info['dx'] = float(abs(lons[1] - lons[0])) if len(lons) > 1 else 0.25
                    grid_info['dy'] = float(abs(lats[1] - lats[0])) if len(lats) > 1 else 0.25
                    
                    # Сохраняем файл координат (старый формат "W H" в первой строке для coords.txt оставляем)
                    #coords_path = os.path.join(OUTPUT_DIR, 'Node_coordinates.txt')
                    lon_matrix, lat_matrix = np.meshgrid(lons, lats)#lat_matrix if 'lat_matrix' in locals() else lats)
                    with open(coords_path, 'w') as f:
                        f.write(f"{grid_info['n_cols']} {grid_info['n_rows']}\n")
                        np.savetxt(f, lat_matrix, fmt='%.3f')
                        np.savetxt(f, lon_matrix, fmt='%.3f')
                    print(f"[INFO] Сетка определена: {grid_info['n_cols']}x{grid_info['n_rows']}. Координаты сохранены.")

                # Поиск переменной в наборе данных
                target_var = None
                if grib_var in ds.data_vars:
                    target_var = grib_var
                elif grib_var.startswith('u') and 'u' in ds.data_vars:
                    target_var = 'u'
                elif grib_var.startswith('v') and 'v' in ds.data_vars:
                    target_var = 'v'
                elif len(ds.data_vars) == 1:
                    target_var = list(ds.data_vars)[0]

                if target_var:
                    data = ds[target_var].values
                    
                    # Выравнивание до 2D (широта х долгота)
                    if data.ndim > 2:
                        data = data.reshape(-1, grid_info['n_rows'], grid_info['n_cols'])[0]
                    
                    # Конвертация температуры Кельвины -> Цельсии
                    if out_name == 'Tair':#'TMP_2m':
                        # GFS отдает температуру в К, вычитаем 273.15
                        data = data - 273.15

                    out_filename = os.path.join(OUTPUT_DIR, f"{out_name}{ext}")
                    is_new_file = not os.path.exists(out_filename) or os.path.getsize(out_filename) == 0

                    with open(out_filename, 'a') as f:
                        # Если файл только создается, пишем мета-заголовок
                        if is_new_file:
                            header_text = (
                                f"FileVersion = 1.03\n"
                                f"filetype = meteo_on_equidistant_grid\n"
                                f"NODATA_value = -999.000\n"
                                f"n_cols = {grid_info['n_cols']}\n"
                                f"n_rows = {grid_info['n_rows']}\n"
                                f"grid_unit = degree\n"
                                f"x_llcorner = {grid_info['x_llcorner']:.3f}\n"
                                f"y_llcorner = {grid_info['y_llcorner']:.3f}\n"
                                f"dx = {grid_info['dx']:.3f}\n"
                                f"dy = {grid_info['dy']:.3f}\n"
                                f"n_quantity = 1\n"
                                f"quantity1 = {quantity1}\n"
                                f"unit1 = {unit1}\n"
                            )
                            f.write(header_text)
                        
                        # Пишем временной маркер перед блоком данных
                        f.write(time_marker + "\n")
                        # Пишем саму матрицу
                        np.savetxt(f, data, fmt='%.3f')
                        
                    print(f"[OK] Данные добавлены в {out_filename}")
                else:
                    print(f"[!] Ошибка: Переменная {out_name} не найдена в {filename_base}")

                ds.close()

            except Exception as e:
                print(f"[ERROR] Критическая ошибка {out_name} в {filename_base}: {e}")

    print("\n--- Все файлы успешно обработаны! ---")

if __name__ == "__main__":
    process_all_gribs()
