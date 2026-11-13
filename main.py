import pymupdf
import tkinter as tk
from tkinter import filedialog, messagebox
import os
import sys
import shutil

MM_TO_PT = 72 / 25.4
PAGE_WIDTH = 40 * MM_TO_PT
PAGE_HEIGHT = 25 * MM_TO_PT

LEFT_MARGIN = 8 * MM_TO_PT      # Отступ слева 8 мм
RIGHT_MARGIN = 7 * MM_TO_PT     # Отступ справа 7 мм для номера страницы
VERTICAL_MARGIN = 4 * MM_TO_PT  # Отступы сверху и снизу 4 мм для 2D-кода

# Максимальная область под код: высота 17 мм (25 - 4 - 4), ширина с запасом до текста
MAX_CODE_HEIGHT = PAGE_HEIGHT - (2 * VERTICAL_MARGIN)
MAX_CODE_WIDTH = PAGE_WIDTH - LEFT_MARGIN - (11 * MM_TO_PT)

def get_base_dir():
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))

class CropSelectorWindow:
    def __init__(self, parent, pdf_path):
        self.selected_rect = None
        self.doc = pymupdf.open(pdf_path)
        self.page = self.doc[0]

        screen_h = parent.winfo_screenheight()
        max_display_h = int(screen_h * 0.75)
        self.zoom = max_display_h / self.page.rect.height
        self.zoom = max(1.0, min(self.zoom, 4.0))

        pix = self.page.get_pixmap(matrix=pymupdf.Matrix(self.zoom, self.zoom))
        img_data = pix.tobytes("ppm")

        self.win = tk.Toplevel(parent)
        filename = os.path.basename(pdf_path)
        self.win.title(f"Выделите область кода: {filename}")
        self.win.grab_set()

        lbl = tk.Label(
            self.win,
            text=f"Файл: {filename}\nЗажмите левую кнопку мыши и обведите сам 2D-код внутри рамки.\nОтпустите кнопку, чтобы подтвердить выбор.",
            font=("Arial", 10, "bold"),
            pady=8
        )
        lbl.pack()

        self.canvas = tk.Canvas(self.win, width=pix.width, height=pix.height, cursor="cross")
        self.canvas.pack()

        self.tk_img = tk.PhotoImage(data=img_data)
        self.canvas.create_image(0, 0, anchor="nw", image=self.tk_img)

        self.start_x = None
        self.start_y = None
        self.rect_id = None

        self.canvas.bind("<ButtonPress-1>", self.on_press)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_release)

        self.win.update_idletasks()
        x = (parent.winfo_screenwidth() - self.win.winfo_width()) // 2
        y = (parent.winfo_screenheight() - self.win.winfo_height()) // 2
        self.win.geometry(f"+{x}+{y}")

        parent.wait_window(self.win)
        self.doc.close()

    def on_press(self, event):
        self.start_x = event.x
        self.start_y = event.y
        if self.rect_id:
            self.canvas.delete(self.rect_id)
        self.rect_id = self.canvas.create_rectangle(
            self.start_x, self.start_y, self.start_x, self.start_y,
            outline="red", width=2, dash=(4, 2)
        )

    def on_drag(self, event):
        if self.rect_id:
            self.canvas.coords(self.rect_id, self.start_x, self.start_y, event.x, event.y)

    def on_release(self, event):
        x0 = min(self.start_x, event.x)
        y0 = min(self.start_y, event.y)
        x1 = max(self.start_x, event.x)
        y1 = max(self.start_y, event.y)

        if (x1 - x0) < 10 or (y1 - y0) < 10:
            return

        self.selected_rect = pymupdf.Rect(
            x0 / self.zoom,
            y0 / self.zoom,
            x1 / self.zoom,
            y1 / self.zoom
        )
        self.win.destroy()

def process_pdf_with_crop(input_path, output_path, crop_rect):
    src_doc = pymupdf.open(input_path)
    total_pages = len(src_doc)

    if total_pages > 999:
        src_doc.close()
        raise ValueError(f"В документе {total_pages} стр. Максимально допустимо: 999 стр.")

    out_doc = pymupdf.open()

    aspect_ratio = crop_rect.width / crop_rect.height if crop_rect.height > 0 else 1

    target_h = MAX_CODE_HEIGHT
    target_w = target_h * aspect_ratio
    if target_w > MAX_CODE_WIDTH:
        target_w = MAX_CODE_WIDTH
        target_h = target_w / aspect_ratio

    x0 = LEFT_MARGIN
    y0 = (PAGE_HEIGHT - target_h) / 2
    target_rect = pymupdf.Rect(x0, y0, x0 + target_w, y0 + target_h)

    font_size = 9
    font_name = "helv"

    for page_num in range(total_pages):
        new_page = out_doc.new_page(width=PAGE_WIDTH, height=PAGE_HEIGHT)
        new_page.show_pdf_page(target_rect, src_doc, page_num, clip=crop_rect)

        page_text = str(page_num + 1)
        text_width = pymupdf.get_text_length(page_text, fontname=font_name, fontsize=font_size)

        text_x = PAGE_WIDTH - RIGHT_MARGIN
        text_y = (PAGE_HEIGHT + text_width) / 2

        new_page.insert_text(
            pymupdf.Point(text_x, text_y),
            page_text,
            fontsize=font_size,
            fontname=font_name,
            rotate=90,
            color=(0, 0, 0)
        )

    out_doc.save(output_path)
    count = len(out_doc)
    src_doc.close()
    out_doc.close()
    return count

def main():
    root = tk.Tk()
    root.withdraw()

    base_dir = get_base_dir()
    in_dir = os.path.join(base_dir, "IN")
    out_dir = os.path.join(base_dir, "OUT")
    done_dir = os.path.join(in_dir, "Done")

    os.makedirs(in_dir, exist_ok=True)
    os.makedirs(out_dir, exist_ok=True)
    os.makedirs(done_dir, exist_ok=True)

    # Собираем все PDF-файлы непосредственно из папки IN (игнорируя подпапки)
    pdf_files = sorted([
        f for f in os.listdir(in_dir)
        if f.lower().endswith(".pdf") and os.path.isfile(os.path.join(in_dir, f))
    ])

    if not pdf_files:
        messagebox.showinfo("Информация", "В папке IN нет PDF-файлов для обработки.")
        return

    # Предупреждаем, если файлов больше 1
    if len(pdf_files) > 1:
        proceed = messagebox.askyesno(
            "Обнаружено несколько файлов",
            f"В папке IN найдено файлов: {len(pdf_files)} шт.\n"
            f"Они будут обработаны последовательно друг за другом.\n\nПродолжить?"
        )
        if not proceed:
            return

    processed_summary = []

    for filename in pdf_files:
        input_path = os.path.join(in_dir, filename)

        # Открываем окно выделения области для текущего файла
        selector = CropSelectorWindow(root, input_path)
        if not selector.selected_rect:
            # Если пользователь закрыл окно крестиком, пропускаем текущий файл
            continue

        base_name = os.path.splitext(filename)[0]
        output_path = os.path.join(out_dir, f"{base_name}_labels.pdf")
        done_path = os.path.join(done_dir, filename)

        try:
            pages_count = process_pdf_with_crop(input_path, output_path, selector.selected_rect)

            # Перемещаем исходный файл в IN\Done (если там уже есть файл с таким именем, перезаписываем)
            if os.path.exists(done_path):
                os.remove(done_path)
            shutil.move(input_path, done_path)

            processed_summary.append(f"• {filename} — {pages_count} этикеток")
        except Exception as e:
            messagebox.showerror("Ошибка обработки", f"Не удалось обработать файл {filename}:\n{e}")

    # Итоговое уведомление по всем обработанным файлам
    if processed_summary:
        summary_text = "\n".join(processed_summary)
        messagebox.showinfo(
            "Обработка завершена",
            f"Успешно обработано файлов: {len(processed_summary)}\n"
            f"Результаты сохранены в папку OUT:\n\n{summary_text}"
        )

if __name__ == "__main__":
    main()
