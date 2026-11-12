import pymupdf
import tkinter as tk
from tkinter import filedialog, messagebox
import os
import sys

MM_TO_PT = 72 / 25.4
PAGE_WIDTH = 42 * MM_TO_PT
PAGE_HEIGHT = 25 * MM_TO_PT

LEFT_MARGIN = 2 * MM_TO_PT
VERTICAL_MARGIN = 2 * MM_TO_PT
MAX_CODE_SIZE = PAGE_HEIGHT - (2 * VERTICAL_MARGIN)

def get_base_dir():
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))

class CropSelectorWindow:
    def __init__(self, parent, pdf_path):
        self.selected_rect = None
        self.doc = pymupdf.open(pdf_path)
        self.page = self.doc[0]

        # Масштабируем первую страницу под экран, чтобы удобно было выделять
        screen_h = parent.winfo_screenheight()
        max_display_h = int(screen_h * 0.75)
        self.zoom = max_display_h / self.page.rect.height
        self.zoom = max(1.0, min(self.zoom, 4.0))  # Ограничиваем масштаб от 1x до 4x

        pix = self.page.get_pixmap(matrix=pymupdf.Matrix(self.zoom, self.zoom))
        img_data = pix.tobytes("ppm")

        self.win = tk.Toplevel(parent)
        self.win.title("Выделите мышкой область кода (без рамки)")
        self.win.grab_set()  # Блокируем другие окна до завершения выбора

        # Подсказка сверху
        lbl = tk.Label(
            self.win,
            text="Зажмите левую кнопку мыши и обведите сам 2D-код внутри рамки.\nОтпустите кнопку, чтобы подтвердить выбор.",
            font=("Arial", 10, "bold"),
            pady=8
        )
        lbl.pack()

        # Холст с изображением первой страницы
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

        # Центрируем окно на экране
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

        # Защита от случайного клика без протяжки
        if (x1 - x0) < 10 or (y1 - y0) < 10:
            return

        # Переводим экранные координаты обратно в координаты PDF-пунктов
        self.selected_rect = pymupdf.Rect(
            x0 / self.zoom,
            y0 / self.zoom,
            x1 / self.zoom,
            y1 / self.zoom
        )
        self.win.destroy()

def process_pdf_with_crop(input_path, output_path, crop_rect):
    src_doc = pymupdf.open(input_path)
    out_doc = pymupdf.open()

    aspect_ratio = crop_rect.width / crop_rect.height if crop_rect.height > 0 else 1

    if aspect_ratio >= 1:
        target_w = min(MAX_CODE_SIZE, PAGE_WIDTH - 2 * LEFT_MARGIN)
        target_h = target_w / aspect_ratio
    else:
        target_h = MAX_CODE_SIZE
        target_w = target_h * aspect_ratio

    x0 = LEFT_MARGIN
    y0 = (PAGE_HEIGHT - target_h) / 2
    target_rect = pymupdf.Rect(x0, y0, x0 + target_w, y0 + target_h)

    for page_num in range(len(src_doc)):
        new_page = out_doc.new_page(width=PAGE_WIDTH, height=PAGE_HEIGHT)
        new_page.show_pdf_page(target_rect, src_doc, page_num, clip=crop_rect)

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
    os.makedirs(in_dir, exist_ok=True)

    # 1. Выбираем исходный файл из папки IN
    input_path = filedialog.askopenfilename(
        title="Выберите исходный PDF с кодами",
        initialdir=in_dir,
        filetypes=[("PDF файлы", "*.pdf")]
    )
    if not input_path:
        return

    # 2. Открываем окно ручного выделения области
    selector = CropSelectorWindow(root, input_path)
    if not selector.selected_rect:
        return  # Пользователь закрыл окно, не выделив область

    # 3. Выбираем куда сохранить результат
    default_name = os.path.splitext(os.path.basename(input_path))[0] + "_labels.pdf"
    output_path = filedialog.asksaveasfilename(
        title="Сохранить этикетки как...",
        initialdir=base_dir,
        initialfile=default_name,
        defaultextension=".pdf",
        filetypes=[("PDF файлы", "*.pdf")]
    )
    if not output_path:
        return

    # 4. Обрабатываем все страницы по выбранной области
    try:
        pages_count = process_pdf_with_crop(input_path, output_path, selector.selected_rect)
        messagebox.showinfo("Готово!", f"Успешно создано этикеток: {pages_count}")
    except Exception as e:
        messagebox.showerror("Ошибка", f"Не удалось обработать файл:\n{e}")

if __name__ == "__main__":
    main()
