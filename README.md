# 세이프티 TBM 코파일럿 (Safety TBM Copilot)

> **산업 현장 작업일보 기반 중대재해 위험성평가표 및 TBM 안전일지 자동 생성기**
> (고용노동부 및 한국산업안전보건공단 KOSHA 표준 5×5 Risk Matrix 가이드라인 준수)

---

## 📌 주요 특징 및 기능

1. **일상 언어 작업일보 기반 AI 분석**:
   - 현장 관리자가 작성한 일상적인 작업 내용(예: "3공구 비계 해체 및 외벽 고소 도장 진행")을 입력하면, AI가 단위 공종을 자동 분류하고 유해·위험요인을 도출합니다.
2. **KOSHA 표준 5×5 Risk Matrix 산출**:
   - 사고 발생 빈도(1~5단계)와 강도(1~5단계)를 곱하여 위험성 등급(고위험/보통/낮음) 및 현장 즉시 조치 감소대책, 조치 담당자를 자동 매핑합니다.
3. **상단 실시간 위험도 KPI 요약**:
   - 총 평가 위험요인 수, 🔴고위험 작업 수, 🟡보통 위험 수, 🟢낮은 위험 수 요약 대시보드.
4. **당일 아침 10분 TBM 안전교육 대본 카드**:
   - 조회 시 작업자 전원에게 낭독할 수 있는 브리핑 대본 제공.
   - **TTS(음성 읽기)** 기능 지원 (현장에서 핸즈프리로 스피커 방송 가능).
   - **[오늘의 핵심 위험 3가지 및 절대 금지 수칙 (Zero Accident Rule)]** 하이라이트.
5. **모바일/태블릿 Canvas 전자서명**:
   - 작성자(안전관리자), 검토자(공사담당), 승인자(현장소장)의 터치/마우스 전자서명 지원.
   - 서명 즉시 상단 3단 결재란에 도장/서명 자동 날인.
6. **A4 인쇄 및 PDF 저장 최적화 (@media print)**:
   - 브라우저 인쇄(`Ctrl+P` 또는 [인쇄/PDF 저장] 버튼) 시 불필요한 입력 폼은 숨겨지고, 결재란과 공종별 위험성평가표만 A4 규격에 정돈되어 1장으로 출력.
7. **Dify Workflow API 완벽 연동 & 지능형 로컬 Fallback**:
   - Dify 클라우드 워크플로우 API 키 연동 지원.
   - API 키가 없거나 오프라인인 경우에도 즉시 사용 가능한 KOSHA 기준 지능형 로컬 규칙 엔진 탑재.

---

## 🚀 빠른 시작 가이드 (Quick Start)

### 1. 원클릭 실행 (Windows)

```cmd
run.bat
```

스크립트 실행 시 자동으로 의존성을 확인하고 브라우저(`http://localhost:8089`)를 엽니다.

### 2. 수동 실행 (Terminal / PowerShell)

```bash
# 의존성 패키지 설치
pip install -r requirements.txt

# 서버 기동
python main.py
```

브라우저에서 `http://localhost:8089` 접속

---

## ⚙️ Dify 워크플로우 연동 가이드

Dify Studio에서 워크플로우를 구성한 뒤 웹 화면 우측 상단의 **[API 설정]** 버튼을 눌러 API Key를 등록하면 클라우드 AI 모델과 즉시 연결됩니다.

### Dify 입출력 명세

- **시작 노드 (Inputs)**:
  - `site_name` (String): 공사/사업장 명칭
  - `work_date` (String): 작업 일자
  - `work_description` (Paragraph): 당일 예정 작업 내용 (자유 양식)
  - `worker_count` (String): 투입 예정 인원 수
- **LLM 노드 응답 포맷**:
  - `json_object` (`tbm_briefing_script`, `core_safety_rules`, `risk_assessments`)
- **종료 노드 (Outputs)**:
  - `tbm_data` (Object): 정형화된 TBM 및 평가표 데이터
  - `is_success` (Boolean): 성공 여부

---

## 📂 프로젝트 구조

```
RiskAssmtAndTBM/
├── DEV_GUIDE.docx            # 개발 가이드 원본 명세
├── requirements.txt          # Python 의존성 패키지
├── .env                      # 환경 변수 설정 (DIFY_API_KEY 등)
├── main.py                   # FastAPI 웹 서버 및 API 엔드포인트
├── run.bat                   # 윈도우 원클릭 실행 배치 파일
├── app/
│   ├── core/
│   │   └── dify_client.py    # Dify Workflow 연동 및 KOSHA Fallback 엔진
│   └── templates/
│       └── index.html        # Tailwind CSS 모던 B2B SaaS 대시보드 & 인쇄 양식
```
