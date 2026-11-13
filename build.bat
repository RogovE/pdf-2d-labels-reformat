@echo off
chcp 65001 > nul
echo ==========================================
echo    Начинаю сборку Pdf2DLabelReformat.exe...
echo ==========================================

:: 1. Активируем виртуальное окружение
call venv\Scripts\activate.bat

:: 2. Удаляем старые папки сборки для чистоты
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
if exist Pdf2DLabelReformat.spec del /q Pdf2DLabelReformat.spec

:: 3. Запускаем PyInstaller с файлом версии
pyinstaller --clean --onefile --windowed --name "Pdf2DLabelReformat" --version-file version_info.txt main.py

:: 4. Проверяем результат
echo.
if exist "dist\Pdf2DLabelReformat.exe" (
    echo [УСПЕХ] Файл успешно собран: dist\Pdf2DLabelReformat.exe
) else (
    echo [ОШИБКА] Сборка не удалась. Проверьте текст выше.
)

echo.
pause
