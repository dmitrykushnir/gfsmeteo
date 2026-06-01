import os
import re
import sys
import threading
import tkinter as tk
from tkinter import messagebox, ttk

# Импортируем модули автоматизации
try:
    import gdex_get_archive
    import decode_grib_batch
    import merge_to_htc
except ImportError as e:
    print(f"[Критическая ошибка] Не удалось импортировать один из модулей: {e}")
    sys.exit(1)

CONTROL_FILE_NAME = "d084001_control_file"

# Глобальный флаг для сигнализации об отмене
stop_requested = False
# Переменная для хранения фонового потока
pipeline_thread = None


def load_dates_from_control_file():
    """Считывает текущие даты из d084001_control_file."""
    if not os.path.exists(CONTROL_FILE_NAME):
        return "202407230000", "202408230000"

    start_date = ""
    end_date = ""
    try:
        with open(CONTROL_FILE_NAME, "r", encoding="utf-8") as f:
            content = f.read()
            match = re.search(r"date=(\d{12})/to/(\d{12})", content)
            if match:
                start_date = match.group(1)
                end_date = match.group(2)
    except Exception as e:
        print(f"[Предупреждение] Не удалось прочесть даты из файла: {e}")

    return start_date or "202407230000", end_date or "202408230000"


def save_dates_to_control_file(start_date, end_date):
    """Обновляет строку 'date=' в файле конфигурации."""
    if not os.path.exists(CONTROL_FILE_NAME):
        base_content = (
            f"dataset=ds084.1\n"
            f"date={start_date}/to/{end_date}\n"
            f"datetype=init\n"
            f"param=U GRD/V GRD/PRMSL/R H/T CDC/TMP/PRES/A PCP\n"
            f"level=HTGL:2/10;SFC:0;BCY:0;EATM:0;MSL:0\n"
            f"nlat=47.375\n"
            f"slat=40.625\n"
            f"wlon=27.125\n"
            f"elon=41.875\n"
            f"product=Analysis\n"
        )
        with open(CONTROL_FILE_NAME, "w", encoding="utf-8") as f:
            f.write(base_content)
        return

    with open(CONTROL_FILE_NAME, "r", encoding="utf-8") as f:
        lines = f.readlines()

    new_lines = []
    date_found = False
    for line in lines:
        if line.strip().startswith("date="):
            new_lines.append(f"date={start_date}/to/{end_date}\n")
            date_found = True
        else:
            new_lines.append(line)

    if not date_found:
        new_lines.insert(1, f"date={start_date}/to/{end_date}\n")

    with open(CONTROL_FILE_NAME, "w", encoding="utf-8") as f:
        f.writelines(new_lines)


def check_interruption():
    """Проверяет, нажал ли пользователь кнопку Остановить."""
    global stop_requested
    if stop_requested:
        raise InterruptedError("Выполнение принудительно остановлено пользователем.")


def run_pipeline_worker(start_date, end_date):
    """Функция-воркер, выполняющаяся в отдельном фоновом потоке."""
    global stop_requested
    
    try:
        # Шаг 0: Сохранение конфигурации
        update_status("Статус: Сохранение конфигурации...", "blue")
        save_dates_to_control_file(start_date, end_date)
        check_interruption()

        # Шаг 1: Выполнение gdex_get_archive.py (очистка indata теперь внутри него)
        update_status("Статус: Загрузка архивов (gdex)...", "blue")
        print("\n>>> Запуск этапа 1: gdex_get_archive.main() <<<")
        gdex_get_archive.main()
        check_interruption()

        # Шаг 2: Выполнение decode_grib_batch.py
        update_status("Статус: Декодирование GRIB файлов...", "blue")
        print("\n>>> Запуск этапа 2: decode_grib_batch.process_all_gribs() <<<")
        decode_grib_batch.process_all_gribs()
        check_interruption()

        # Шаг 3: Выполнение merge_to_htc.py
        update_status("Статус: Сборка итогового файла...", "blue")
        print("\n>>> Запуск этапа 3: merge_to_htc.htc_file_button_click() <<<")
        merge_to_htc.htc_file_button_click(decode_grib_batch.OUTPUT_DIR)
        check_interruption()

        # Финал при успехе
        update_status("Статус: Успешно завершено!", "green")
        root.after(0, lambda: messagebox.showinfo("Успех", "Все этапы обработки данных выполнены успешно!"))

    except InterruptedError as ie:
        update_status("Статус: Остановлено пользователем", "orange")
        print(f"\n[ИНФО]: {ie}")
        root.after(0, lambda: messagebox.showwarning("Прервано", "Процесс обработки данных был успешно остановлен."))
        
    except Exception as e:
        update_status("Статус: Произошла ошибка!", "red")
        print(f"\n[КРИТИЧЕСКАЯ ОШИБКА КОНВЕЙЕРА]: {e}")
        root.after(0, lambda: messagebox.showerror(
            "Ошибка выполнения", 
            f"Выполнение конвейера аварийно прервано!\n\nОписание ошибки:\n{e}"
        ))
        
    finally:
        # Возвращаем интерфейс в исходное состояние
        root.after(0, reset_ui_buttons)


def start_pipeline():
    """Запускает фоновый поток вычислений."""
    global pipeline_thread, stop_requested
    
    start_date = start_date_entry.get().strip()
    end_date = end_date_entry.get().strip()

    if not (re.match(r"^\d{12}$", start_date) and re.match(r"^\d{12}$", end_date)):
        messagebox.showerror(
            "Ошибка валидации",
            "Даты должны быть введены строго в формате YYYYMMDDHHMM (12 цифр).\nНапример: 202407230000",
        )
        return

    # Переключаем состояние кнопок
    stop_requested = False
    start_btn.config(state=tk.DISABLED)
    stop_btn.config(state=tk.NORMAL)
    
    # Запускаем выполнение в потоке, чтобы GUI не зависал
    pipeline_thread = threading.Thread(target=run_pipeline_worker, args=(start_date, end_date), daemon=True)
    pipeline_thread.start()


def stop_pipeline():
    """Вызывается при нажатии кнопки 'Остановить'."""
    global stop_requested
    if messagebox.askyesno("Подтверждение", "Вы действительно хотите прервать обработку данных?"):
        stop_requested = True
        status_lbl.config(text="Статус: Запрос на остановку...", foreground="orange")
        stop_btn.config(state=tk.DISABLED)


# Потокобезопасные функции обновления интерфейса через главный цикл tkinter
def update_status(text, color):
    root.after(0, lambda: status_lbl.config(text=text, foreground=color))

def reset_ui_buttons():
    start_btn.config(state=tk.NORMAL)
    stop_btn.config(state=tk.DISABLED)


# === Создание графического интерфейса ===
root = tk.Tk()
root.title("Загрузка данных анализа с gdex")
root.geometry("420x280")
root.resizable(False, False)

style = ttk.Style()
style.theme_use("clam")

main_frame = ttk.Frame(root, padding="20")
main_frame.pack(fill=tk.BOTH, expand=True)

init_start, init_end = load_dates_from_control_file()

# Поле ввода Начальной даты
ttk.Label(main_frame, text="Начальная дата (YYYYMMDDHHMM):", font=("Arial", 10, "bold")).pack(anchor=tk.W, pady=(0, 2))
start_date_entry = ttk.Entry(main_frame, font=("Arial", 10))
start_date_entry.pack(fill=tk.X, pady=(0, 10))
start_date_entry.insert(0, init_start)

# Поле ввода Конечной даты
ttk.Label(main_frame, text="Конечная дата (YYYYMMDDHHMM):", font=("Arial", 10, "bold")).pack(anchor=tk.W, pady=(0, 2))
end_date_entry = ttk.Entry(main_frame, font=("Arial", 10))
end_date_entry.pack(fill=tk.X, pady=(0, 15))
end_date_entry.insert(0, init_end)

# Контейнер для кнопок управления
button_frame = ttk.Frame(main_frame)
button_frame.pack(fill=tk.X, pady=(0, 15))

start_btn = ttk.Button(button_frame, text="Начать", command=start_pipeline)
start_btn.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))

stop_btn = ttk.Button(button_frame, text="Остановить", command=stop_pipeline, state=tk.DISABLED)
stop_btn.pack(side=tk.RIGHT, fill=tk.X, expand=True, padx=(5, 0))

# Строка состояния конвейера
status_lbl = ttk.Label(main_frame, text="Статус: Ожидание запуска", font=("Arial", 10, "italic"), foreground="gray")
status_lbl.pack(anchor=tk.W)

if __name__ == "__main__":
    root.mainloop()
