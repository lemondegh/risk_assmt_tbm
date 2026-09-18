@echo off
chcp 65001 > nul
echo =====================================================================
echo  세이프티 TBM 코파일럿 - 산업 현장 위험성평가표 및 TBM 일지 생성기
echo =====================================================================
echo.
echo [1/2] 가상환경 및 의존성 확인 중...
python -m pip install -r requirements.txt -q

echo.
echo [2/2] 세이프티 TBM 웹 서버 시작 중 (http://localhost:8089)...
start http://localhost:8089
python main.py
pause
