@echo off
echo ============================================================
echo   Surplus Food Redistribution System (FoodShare)
echo   MCA Project Academic Implementation
echo ============================================================
echo.

cd /d "%~dp0"

echo Activating Python Virtual Environment...
call .\venv\Scripts\activate

echo.
echo Running Priority Recalculation Check...
python manage.py recalculate_priorities

echo.
echo Starting Django Web Server on http://127.0.0.1:8000/ ...
echo Press CTRL+C to stop the server.
echo.
python manage.py runserver 127.0.0.1:8000
pause
