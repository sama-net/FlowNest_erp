@echo off
title FlowNest ERP - Database Fix & Restart
color 0A
echo.
echo  ========================================
echo   FlowNest ERP - Applying All Migrations
echo  ========================================
echo.

cd /d "C:\Users\win\Desktop\myenv\myenv\yasso"

echo [1/4] Creating migrations for products app...
call "C:\Users\win\Desktop\myenv\myenv\Scripts\python.exe" manage.py makemigrations products
echo.

echo [2/4] Creating migrations for chat app...
call "C:\Users\win\Desktop\myenv\myenv\Scripts\python.exe" manage.py makemigrations chat
echo.

echo [3/4] Applying ALL migrations to database...
call "C:\Users\win\Desktop\myenv\myenv\Scripts\python.exe" manage.py migrate
echo.

echo [4/4] Starting Development Server...
echo  ----------------------------------------
echo   FlowNest is running at http://127.0.0.1:8000
echo  ----------------------------------------
echo.
call "C:\Users\win\Desktop\myenv\myenv\Scripts\python.exe" manage.py runserver

pause
