@echo off
echo ====================================================
echo Starting Yasso (Django) and FlowNest (Flask) Apps
echo ====================================================

:: Activating Virtual Environment
call myenv\Scripts\activate

:: Checking if the required packages are installed
echo.
echo Installing dependencies for Yasso (Django)...
python -m pip install -q groq chromadb sentence-transformers "Django<5.1" psycopg2-binary pdfplumber openpyxl

echo.
echo Installing dependencies for FlowNest Dashboard...
python -m pip install -q -r flownest_dashboard\flownest\requirements.txt

echo.
echo ====================================================
echo Both applications will now start in separate windows
echo ====================================================

:: Start FlowNest Dashboard in a new CMD window
echo Starting FlowNest Dashboard (Flask) on http://127.0.0.1:5050
start cmd /k "title FlowNest Dashboard (Flask) & call myenv\Scripts\activate & cd flownest_dashboard\flownest & python app.py"

:: Start Yasso (Django) in a new CMD window
echo Starting Yasso Backend (Django) on http://127.0.0.1:8000
start cmd /k "title Yasso Backend (Django) & call myenv\Scripts\activate & cd myenv\yasso & python manage.py runserver"

echo Done!
pause
