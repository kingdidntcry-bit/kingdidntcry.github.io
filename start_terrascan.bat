@echo off
echo Starting TerraScan Local Dashboard...
echo.
REM Check if .venv exists, if not use global python
if exist .venv\Scripts\activate.bat (
    echo Activating Virtual Environment...
    call .venv\Scripts\activate.bat
) else (
    echo [WARNING] .venv not found. Using system Python.
)
echo Launching Streamlit...
streamlit run app.py
pause
