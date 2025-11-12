# 개인화 학습 퀘스트 플래너 (Alpha/MVP)

- 프론트엔드: `frontend/` (HTML/CSS/JS, 정적 서버로 제공)
- 백엔드: `backend/` (FastAPI + SQLite via SQLAlchemy)
- 시드 데이터: `data/seed_quests.json`

## 실행 방법

### 의존성 설치
```bash
pip install -r requirements.txt
```

### 환경 변수(.env) 설정 (ChatGPT 연동용 - 선택)
```bash
cp .env.example .env
# .env 파일을 열고 OPENAI_API_KEY 입력
# 필요시 모델 교체
#   OPENAI_MODEL_CLASSIFY=gpt-5-nano
#   OPENAI_MODEL_MINI=gpt-5-mini
#   OPENAI_MODEL_FULL=gpt-5
```

### 서버 실행
```bash
uvicorn backend.app:app --reload --port 8000
```
또는 Windows에서 `start_server.bat` (포트 인자: `start_server.bat 9000`)

### 프론트 실행
```bash
python -m http.server 5500 -d frontend
```
또는 Windows에서 `start_frontend.bat` (포트 인자: `start_frontend.bat 5600`)

### 양쪽 모두 실행 (Windows)
`start_all.bat` → 백엔드/프론트 각각 새 콘솔 창에서 실행됩니다.

## 주요 기능

- **전역 타이머 (국어/수학/영어 학습)**
  - 버튼 클릭 즉시 학습 퀘스트 생성/재사용 (과목당 1개, 태그=학습)
  - 시간은 25/50/90 중 목표치에 가장 가까운 값 자동 배치
  - 5초마다 서버에 누적 저장, 완료되면 서버가 즉시 정리
- **퀘스트 목록**
  - 학습 퀘스트 3종이 항상 상단 고정, 하단에 퍼센트/게이지 표시
  - 비학습 퀘스트(복습/문제풀이/암기 등)는 카드 클릭으로 퀘스트 전용 타이머 시작 (동시에 1개만 가능)
  - 문제형(시간제약=0)은 카드 안에서 성공/실패 버튼으로 로그 후 삭제
- **AI 문제 퀘스트**
  - `POST /ai/quests/ai_problem?user_id=u1&subject=국어|수학|영어`
  - 과목별 1개만 활성, 태그 [`ai-problem`]/[`AI문제`], `meta`에 문제/정답/풀이 저장
- **챗봇 / 질문 로그**
  - `POST /ai/chat` → `gpt-5-nano`로 과목/난이도 분류 후 `gpt-5-mini` 또는 `gpt-5`로 답변
  - 키는 백엔드에서만 사용, 프론트에는 노출되지 않음
- **통계**
  - `GET /stats/summary` → 최근 N일 과목별 총 분, 일별 합계, 연속 학습일
- **전체 초기화**
  - `POST /admin/reset_all[?seed=true]` (프론트 우하단 빨간 버튼)
  - 시드를 포함하면 학습 3종 + 샘플 퀘스트가 항상 동일하게 로드

## API 요약
- 퀘스트: `GET /quests?user_id=u1`, `POST /quests`, `PATCH /quests/{id}`
- 타이머: `POST /timer/update` `{user_id, subject, delta_seconds}` 또는 `{user_id, quest_id, delta_seconds}`
- 플래너: `GET /ai/planner/suggest?user_id=u1`
- 질문 로그/챗봇: `POST /ai/chat`
- AI 문제 생성: `POST /ai/quests/ai_problem?user_id=u1&subject=수학`
- 통계: `GET /stats/summary?user_id=u1&days=7`
- 전체 초기화: `POST /admin/reset_all[?seed=true]`

## 주의사항
- 개발 모드에서는 `--reload`로 저장 시 자동 재시작
- SQLite 파일 위치: `backend/app.db` (스키마가 달라지면 서버 중지 후 삭제/재생성 권장)
- 브라우저 캐시 문제 시 강제 새로고침(Ctrl + F5)

## TODO / 추후 계획

1. **퀘스트 상태/표기 개선**
   - `paused` 등 내부 상태를 UI에서 한글로 명확히 표시 (예: “잠시 멈춤”).
   - 전역 학습 퀘스트와 일반 퀘스트 진행도를 동시에 시각화(예: 측면 패널).
2. **시간형 퀘스트 확장**
   - 사용자 정의 시간 옵션(25/50/90 외)을 허용하고, 목표 시간 직접 입력 기능 추가.
   - 학습 퀘스트를 과목당 여러 개 둘 수 있도록(현재는 학습 1개 + 기타 1개) 설정 옵션 제공.
3. **문제형 퀘스트 고도화**
   - 정답 제출 UI, 채점/설명 표시, 부분 점수/힌트 시스템.
   - 결과 로그에 소요 시간, 정답 여부 등 메타데이터 저장.
4. **플래너/추천 고도화**
   - 실패율/질문 패턴 가중치 반영하여 퀘스트 제안 정교화.
   - 제안 결과를 프론트에서 보여주고 “제안 적용” 버튼으로 바로 생성.
5. **통계/모니터링 강화**
   - 문제형 성공률, 과목별 학습 완료율, 주간 리포트 UI.
   - 긴급 알림/리마인더 기능(예: 일정 시간 미활동 시 알림).
6. **다중 사용자/인증**
   - 현재는 단일 사용자(u1) 기준. 추후 로그인/계정 시스템 적용 예정.
7. **테스트/배포**
   - API/프론트 단위 테스트 보강.
   - CI/CD 파이프라인과 배포 스크립트 정리.

---
현재 버전은 “학습 3종 + 시간형·문제형 퀘스트 + AI 챗봇”을 안정적으로 돌리는 MVP입니다. 위 TODO를 순차적으로 진행해 완성도를 높여 나갈 예정입니다.

# 1. get-pip.py 스크립트를 다운로드
curl https://bootstrap.pypa.io/get-pip.py -o get-pip.py

# 2. 다운로드한 스크립트를 실행하여 pip 설치
python get-pip.py

# 3. 설치가 완료되었는지 버전 확인
python -m pip --version

