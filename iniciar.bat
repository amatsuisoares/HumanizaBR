@echo off
rem Inicia o HumanizaBR sem precisar do VS Code: de dois cliques neste arquivo.
rem O app abre no navegador em http://localhost:8501. Para encerrar, feche esta janela.
chcp 65001 >nul
title HumanizaBR
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo Ambiente virtual não encontrado. Veja a seção "Instalação" do README.md.
    pause
    exit /b 1
)

rem O Ollama precisa estar rodando. Se não responder, abre o aplicativo dele
rem e espera até 30 segundos.
curl -s -o nul http://127.0.0.1:11434/api/version
if errorlevel 1 (
    echo Iniciando o Ollama...
    start "" "%LOCALAPPDATA%\Programs\Ollama\ollama app.exe"
    for /l %%i in (1,1,30) do (
        timeout /t 1 /nobreak >nul
        curl -s -o nul http://127.0.0.1:11434/api/version && goto ollama_ok
    )
    echo O Ollama não respondeu. Abra-o pelo menu Iniciar e tente de novo.
    pause
    exit /b 1
)
:ollama_ok

echo Abrindo o HumanizaBR em http://localhost:8501 ...
echo Para encerrar, feche esta janela.
".venv\Scripts\python.exe" -m streamlit run app.py
pause
