@echo off
setlocal enabledelayedexpansion
set BASE=%~dp0
set DATA=%BASE%..\..\data

echo === Pandahis Data Cleaning Pipeline ===
echo.
echo Step 1: Check node...
node --version >nul 2>&1 || (echo ERROR: node not found && exit /b 1)

echo Step 2: Extract index JSON from zip...
node %BASE%extract.mjs %DATA%\historiography-index.zip 001 %BASE%_index.json

echo Step 3: Validate Phase 1 index...
node %BASE%validators\validate-index.mjs --input %BASE%_index.json

echo.
echo === Done ===