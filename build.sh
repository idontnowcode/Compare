#!/bin/bash
# Linux/macOS용 빌드 스크립트

set -e

echo "[1/3] 의존성 설치 중..."
pip3 install -r requirements.txt pyinstaller

echo "[2/3] 실행 파일 빌드 중..."
pyinstaller Compare.spec --clean

echo "[3/3] 완료!"
echo "결과물: dist/Compare"
