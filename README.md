# 📊 AI Data Insight Builder

> **공공데이터의 엄밀한 계산(Pandas)과 생성형 AI(Google Gemini)의 심층 해석이 결합된 풀스택 데이터 분석 & PWA 웹 플랫폼**

[![Python Version](https://img.shields.io/badge/Python-3.11+-3776AB?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![Flask](https://img.shields.io/badge/Framework-Flask-000000?style=flat-square&logo=flask&logoColor=white)](https://flask.palletsprojects.com/)
[![Google Gemini](https://img.shields.io/badge/AI-Google%20Gemini-4285F4?style=flat-square&logo=google&logoColor=white)](https://ai.google.dev/)
[![PWA Ready](https://img.shields.io/badge/PWA-Installable-5A0FC8?style=flat-square&logo=pwa&logoColor=white)](#-pwa-모바일-설치-안내)
[![Vercel Deployment](https://img.shields.io/badge/Deploy-Vercel-000000?style=flat-square&logo=vercel&logoColor=white)](https://vercel.com)

---

## 🌟 프로젝트 개요 (Overview)

**AI Data Insight Builder**는 복잡한 공공데이터(World Bank, 통계청 등) CSV 파일을 업로드하면, **Pandas 엔진이 수치적 오차 없이 정밀하게 계산**하고 **Google Gemini AI가 7대 분석 원칙에 입각하여 심층 보고서를 작성**해 주는 올인원 데이터 인사이트 플랫폼입니다.

단순한 데이터 조회를 넘어 **자연어 질문 시각화**, **4자리 보안 PIN 잠금**, 그리고 스마트폰 홈 화면에 단독 앱으로 설치할 수 있는 **PWA(Progressive Web App)** 기술이 탑재되어 있습니다.

---

## ✨ 핵심 기능 (Key Features)

### 1. 📁 스마트 데이터 업로드 & 무결성 자동 진단
* **다중 인코딩 지원**: UTF-8, CP949, EUC-KR 등 국내외 공공데이터 인코딩을 자동 감지하여 글자 깨짐 방지.
* **메타데이터 자동 스킵**: 헤더 위의 불필요한 기관 설명 행을 자동으로 판별하여 스킵.
* **품질 리포트**: 결측치 비율, 중복 행, 이상치 및 분석에 최적화된 권장 기준 연도 자동 추천.

### 2. 🧮 12대 전문 데이터 분석 도구 (Pandas Engine)
수치 왜곡과 AI 할루시네이션(환각)을 원천 차단하기 위해 모든 통계 계산은 검증된 Pandas 도구로 실행됩니다:
* `T1`: 와이드-롱 포맷 재구조화 (Reshape Wide-to-Long)
* `T2`: 데이터 품질 및 결측치 리포트 (Quality Report)
* `T3`: 연도별 데이터 커버리지 분석 (Year Coverage)
* `T4`: 국가 목록 내 대륙/지역 집계 행 자동 감지 및 격리 (Detect Aggregates)
* `T5`: 수치형 기술통계량 산출 (Describe Numeric)
* `T6`: 주요국 시계열 변화 추이 선 차트 (Time Series Trend Line)
* `T7`: 기준 연도 상위/하위 N 순위 가로 막대 차트 (Top/Bottom N Ranking)
* `T8`: 소득그룹 및 대륙별 그룹 요약 (Group Summary)
* `T9`: 특정 기간 대비 증감률 분석 (Change Rate)
* `T10`: 수치 분포도 및 히스토그램 (Distribution)
* `T11`: 2개 시점/지표 간 상관관계 산점도 (Correlation Scatter)
* `T12`: 한국 vs 글로벌 전체 분포 비교 (Compare One vs All)

### 3. 💬 자연어 질의 & 즉시 차트 시각화 (NLP Query-to-Chart)
* 사용자가 질문창에 *"한국 인터넷 보급률"* 또는 *"글로벌 상위 10개국 추이"*와 같이 일상 언어로 질문하면, AI가 질문의 의도를 분석하여 적절한 Pandas 도구를 매핑하거나 공인 통계 기반 차트를 즉시 렌더링합니다.
* **가로 막대 차트 (Horizontal Bar Chart)**: 긴 국가명도 겹침 없이 한눈에 읽을 수 있는 가로형 레이아웃.
* **한국 전용 붉은색 강조**: 대한민국(`Korea, Rep.`)을 선명한 빨간색(`#ef4444`)으로 하이라이트하고, 타 국가는 차분한 단일 블루로 통일.
* **동적 스케일링 (`calculateScaleLimits`)**: 상위권 데이터(90%~100%) 밀집 시 모든 막대가 100%로 가득 차 보이는 현상을 방지하기 위해 기준 축을 동적으로 확대하여 수치 격차를 직관적으로 표현.
* **실측치 라벨 표기 (`valueLabelPlugin`)**: 막대 우측 끝에 소수점 둘째 자리 공식 수치 직접 표시.

### 4. 📝 Gemini AI 7대 원칙 보고서 생성
* 도구 실행 결과 수치를 기반으로 구조화된 심층 해설 보고서 작성.
* 핵심 단어와 결론 문장을 `==형광펜 강조==` 스타일로 시각화하여 가독성 극대화.

### 5. 🔒 4자리 보안 PIN 잠금 (Deep Navy Glassmorphism)
* 서비스 접근 시 4자리 비밀번호(**기본값: `0514`**) 인증 요구.
* 고급스러운 **딥 네이비 글래스모피즘** 디자인과 발광하는 키패드 인터페이스.
* `sessionStorage` 기반 세션 유지 및 헤더의 `🔒 잠금` 버튼으로 언제든지 재잠금 가능.

### 6. 📱 PWA (Progressive Web App) 완벽 지원
* W3C Web App Manifest(`manifest.json`) 및 Service Worker v3 오프라인 캐싱 적용.
* 브라우저 프레임 없는 **독립형 네이티브 앱(Standalone)** 경험.
* 모바일 전용 플로팅 설치 배너 및 아이폰(iOS Safari) 전용 3단계 설치 가이드 모달 지원.

### 7. 💾 유틸리티 도구
* **화면 저장**: 현재 분석 내용과 Canvas 차트(Base64 인라인 이미지 변환)를 단일 HTML 파일로 아카이브 다운로드.
* **인쇄 / PDF**: 대시보드 리포트를 바로 A4 인쇄하거나 PDF로 저장.
* **링크 복사**: 원클릭 클립보드 복사.

---

## 🛠️ 기술 스택 (Tech Stack)

| 계층 | 기술 |
| :--- | :--- |
| **Backend** | Python 3.11+, Flask, Pandas, Python-dotenv |
| **AI Model** | Google Gemini (`gemini-2.5-flash` / `gemini-3.5-flash-lite`) via `google-genai` SDK |
| **Frontend** | Vanilla JavaScript (ES6+), HTML5, CSS3 (Modern Glassmorphism) |
| **Visualization** | Chart.js 4.x (Custom Horizontal Bar & Data Labels Plugin) |
| **PWA** | Service Worker (Stale-While-Revalidate), Web App Manifest, App Icons |
| **Deployment** | Vercel Serverless Functions (`vercel.json`) |

---

## 📂 프로젝트 구조 (Directory Structure)

```text
data-insight-builder/
├── app.py                  # Flask 메인 애플리케이션 (라우팅, API, Gemini 연동)
├── tools.py                # 12대 정밀 Pandas 데이터 분석 도구 모음
├── requirements.txt        # 파이썬 의존성 패키지 목록
├── vercel.json             # Vercel 배포 빌드 및 라우트 설정
├── .env.example            # 환경변수 템플릿
├── templates/
│   └── index.html          # 단일 페이지 애플리케이션 (SPA) 메인 마크업
└── static/
    ├── style.css           # 딥 네이비 글래스 테마 및 반응형 스타일
    ├── app.js              # 프론트엔드 비즈니스 로직, 차트 플러그인, PWA 컨트롤러
    ├── manifest.json       # PWA 웹앱 매니페스트 설정
    ├── service-worker.js   # PWA 오프라인 캐싱 및 백그라운드 서비스 워커
    └── icons/              # PWA 전용 고해상도 앱 아이콘 (192, 512, Maskable, Apple, Favicon)
```

---

## 🚀 로컬 실행 방법 (Local Installation)

### 1. 저장소 복제 (Clone)
```bash
git clone https://github.com/hawonjang94/data-insight-builder.git
cd data-insight-builder
```

### 2. 가상환경 생성 및 활성화
```bash
# Windows
python -m venv .venv
.\.venv\Scripts\activate

# macOS / Linux
python3 -m venv .venv
source .venv/bin/activate
```

### 3. 필수 패키지 설치
```bash
pip install -r requirements.txt
pip install Pillow
```

### 4. 환경변수 설정 (`.env`)
프로젝트 루트에 `.env` 파일을 생성하고 본인의 Google Gemini API 키를 입력합니다:
```ini
GEMINI_API_KEY=your_google_gemini_api_key_here
GEMINI_MODEL=gemini-2.5-flash
APP_PIN=0514
MAX_UPLOAD_MB=10
```

### 5. 서버 실행
```bash
python app.py
```
브라우저에서 **[http://127.0.0.1:5000](http://127.0.0.1:5000)**에 접속한 뒤 비밀번호 `0514`를 입력합니다.

---

## 📲 PWA 모바일 설치 안내 (How to Install)

### 🤖 안드로이드 (Android / Chrome)
1. Vercel 배포 주소(`https://...vercel.app`)로 접속합니다.
2. 화면 하단에 뜨는 **[앱 설치]** 플로팅 배너 또는 상단 메뉴의 **`📲 앱 설치`** 버튼을 누릅니다.
3. 팝업창에서 **[설치]**를 누르면 홈 화면에 어플이 설치됩니다.

### 🍎 아이폰 (iOS / Safari)
1. 사파리(Safari) 브라우저로 Vercel 배포 주소에 접속합니다.
2. 하단 중앙의 **공유 버튼(⎋)**을 클릭합니다.
3. 메뉴를 내려 **'홈 화면에 추가(➕)'**를 누른 뒤 우측 상단 **[추가]**를 누르면 설치가 완료됩니다.

---

## 🔐 보안 및 데이터 정책
* **무상태성(Stateless) 메모리 원칙**: 사용자가 업로드한 CSV 파일은 영구 저장 디스크가 아닌 **서버 메모리에만 임시 보관**되며, 서버 재시작 시 자동 소멸됩니다.
* **개인정보 보호**: API 키 및 설정 파일(`.env`)은 Git 추적에서 원천 제외(`.gitignore`)되어 있습니다.

---

## 📄 라이선스 (License)

This project is licensed under the MIT License.
Copyright (c) 2026 hawonjang94.
