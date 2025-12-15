#!/bin/bash

# VC 투자 분석 에이전트 원클릭 실행 스크립트

echo "🚀 VC 투자 분석 에이전트 시작..."
echo ""

# 1. 가상환경 확인 및 생성
if [ ! -d "venv" ]; then
    echo "📦 가상환경 생성 중..."
    python3 -m venv venv
    if [ $? -ne 0 ]; then
        echo "❌ 가상환경 생성 실패. python3가 설치되어 있는지 확인하세요."
        exit 1
    fi
    echo "✅ 가상환경 생성 완료"
    echo ""
fi

# 2. 가상환경 활성화
echo "🔧 가상환경 활성화 중..."
source venv/bin/activate

# 3. 의존성 설치 확인
if [ ! -f "venv/.dependencies_installed" ]; then
    echo "📥 패키지 설치 중 (최초 1회만)..."
    pip install --upgrade pip
    pip install -r requirements.txt

    if [ $? -ne 0 ]; then
        echo "❌ 패키지 설치 실패. requirements.txt를 확인하세요."
        exit 1
    fi

    # 설치 완료 마커 생성
    touch venv/.dependencies_installed
    echo "✅ 패키지 설치 완료"
    echo ""
else
    echo "✅ 패키지 이미 설치됨"
    echo ""
fi

# 4. API 키 확인
if [ ! -f ".env" ]; then
    echo "⚠️  .env 파일이 없습니다."
    echo ""

    # .env.example이 있으면 복사
    if [ -f ".env.example" ]; then
        echo "📝 .env.example 파일을 .env로 복사합니다..."
        cp .env.example .env
        echo "✅ .env 파일 생성 완료"
        echo ""
    else
        echo "다음 명령어로 API 키를 설정하세요:"
        echo "  echo \"ANTHROPIC_API_KEY=your-api-key-here\" > .env"
        echo ""
        read -p "계속하시겠습니까? (y/n) " -n 1 -r
        echo ""
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            exit 1
        fi
    fi
fi

# 5. Streamlit 실행
echo "🌐 웹 UI 실행 중..."
echo ""
echo "브라우저가 자동으로 열립니다: http://localhost:8501"
echo "종료하려면 Ctrl+C를 누르세요"
echo ""

streamlit run app.py
