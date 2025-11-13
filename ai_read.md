# AI 협업 리드북 (ai_read.md)

## 1. 프로젝트 비전 & 현재 단계
- 이름: "개인화 학습 퀘스트 플래너" (Alpha/MVP). 목표는 다마고치/메이플 퀘스트 감성으로 시간 기반 학습을 추적하고 AI가 퀘스트·플래너를 재구성하는 것.
- 현재 단일 사용자(u1) 고정, 로그인 미구현. Persistent DB(SQLite) 사용하지만 데이터 초기화/시드가 자주 필요.
- 우선순위는 **국/영/수 시간형 퀘스트 + 전역 타이머 + 기본 AI 분석 파이프라인**. 마스코트/게이미피케이션은 보류.

## 2. 리포지토리 구성
```
project_root/
├─ backend/            # FastAPI, SQLAlchemy, 서비스/라우트 계층 분리
├─ frontend/           # HTML/CSS/JS, 정적 http.server로 서빙
├─ data/seed_quests.json
├─ design/             # Figma 자료 및 export 가이드
├─ .env.example        # OpenAI 키 및 모델명 예시
├─ README.md           # 실행 안내 + 기능 목록 + TODO
└─ start_*.bat         # Win 전용 런처(front/back/both)
```

## 3. 프론트엔드 스냅샷
- **런타임**: 정적 HTML + 모듈형 JS(main/quest/timer/aiButton). CSS는 layout/quest/timer/mascot 로 분리, Figma 스타일 이식에 집중.
- **레이아웃**: 16:9 2560*1440 기준 app-shell. 좌측 상단 학습 요약, 중앙 전역 타이머, 좌측 하단 퀘스트 카드 스택, 우측 하단 reset/chatGPT 버튼 고정.
- **전역 타이머**: 국어/수학/영어 3 버튼으로 제어. 버튼 클릭 즉시 타이머 시작(시작 버튼 없음). 과목 전환 시 이전 과목 진행도는 DB에 누적되고 새 과목이 이어받음.
- **퀘스트 카드 시스템**:
  - 상단 고정 3장: 과목별 "~학습 n분" 메인형. 항상 리스트 최상단 + 메인 퀘스트 대상에서 제외.
  - 그 외 카드는 복습/문풀/듣기/AI 문제 등. 클릭 시 해당 퀘스트 전용 미니 타이머(전역과 병행 가능) 혹은 성공/실패 버튼 노출(goal_value=0).
  - 동일 과목+태그 조합은 동시에 1개만 존재(예: "국어 학습 25"와 "국어 학습 50" 동시 불가). 영어만 "독해" 태그 추가 허용.
- **상태 표시**: `pending / in_progress / paused / completed`. 전역 타이머와 연동되는 학습형 퀘스트는 자동으로 퍼센트 업데이트, 다른 타입은 카드 클릭/버튼으로 제어.
- **ChatGPT 버튼**: `frontend/assets/icons/chatgpt_button.svg`. 눌렀을 때 모달/사이드패널 UI는 추후 확장 예정(현재는 API 호출 훅만 존재).

## 4. 백엔드 & API
- **스택**: FastAPI, SQLAlchemy, SQLite(`backend/app.db`). `backend/app.py`는 앱 초기화 + 라우터(include_router) + CORS.
- **핵심 라우트**
  - `/quests` (GET/POST/PATCH): 퀘스트 CRUD + 상태 업데이트. 생성 시 과목·태그 중복 규칙을 수비, seed 로더가 사용됨.
  - `/timer/update`: 전역/퀘스트 타이머에서 델타 초 단위 progress 누적. subject 기반과 quest_id 기반 모두 처리.
  - `/ai/chat`: 입력 질문을 `gpt-5-nano`로 분류(과목/난도) → 결과에 따라 `gpt-5-mini` 또는 `gpt-5` 호출. 응답과 메타 로그 저장.
  - `/ai/quests/ai_problem`: 과목별 1개만 허용되는 AI 문제형 퀘스트 생성(tags: `ai-problem`, `AI문제`). 문제 텍스트/풀이/해설을 `meta` 필드에 JSON으로 유지.
  - `/ai/planner/suggest`: 타이머/질문 로그 기반으로 다음 퀘스트 셋 추천(규칙/LLM 하이브리드 설계 예정).
  - `/stats/summary`: 최근 N일 과목별 학습량, 연속 공부일, 태그 분포 제공.
  - `/admin/reset_all?seed=true`: 사용자 데이터/로그/퀘스트 삭제 후 `data/seed_quests.json` 재삽입. 프론트 우측 하단 빨간 버튼과 연결.
- **환경 변수(.env)**
  - `DATABASE_URL` (기본 sqlite:///../backend/app.db)
  - `OPENAI_API_KEY`, `OPENAI_MODEL_CLASSIFY`, `OPENAI_MODEL_MINI`, `OPENAI_MODEL_FULL`

## 5. 데이터/규칙 요약
- **Quest Model(요약)**: `{id, user_id, type(time|action|ai_problem ...), title, subject(국/영/수), goal_value(분 or 0), progress_value, status, tags, tags_ko, meta}`.
- **태그 매핑**:
  - 한국어 입력 → 영문 태그 저장 (예: `학습→study`, `복습→review`, `문제풀이→problem-solving`, `단어암기(영어)→english-vocabulary`, `듣기(영어)→english-listening`, `독해(영어)→english-reading`, `AI문제→ai-problem`).
  - `학습` 태그는 가장 빈번하고 전역 타이머와 직접 연결. 동일 subject+tag 조합은 동시 1개 제한, 단 "공부 n분 하기" 카드는 다른 퀘스트와 병행 허용.
- **시간 옵션**: 순공(집중 공부) 25/50/90분 세 구간을 기본값으로 사용. 타이머는 초 단위 저장, 프론트는 분/퍼센트로 변환.
- **상태 전환**
  - 전역 타이머 subject 버튼 클릭 시: 해당 subject 학습 퀘스트 `in_progress`, 이전 subject는 `paused` (퍼센트는 서버에서 누적).
  - 비학습형 카드는 클릭 시 `in_progress`, 다른 카드 클릭/전역 과목 변경 시 `paused`. goal_value 달성 또는 성공/실패 버튼으로 `completed`/`failed` 처리.

## 6. AI 연동 정책
- **Chatbot**: 프론트는 단순 입력/출력 표시 역할. 백엔드에서 모델 판단/호출/키 관리. API 실패 시 graceful fallback 메시지 필요.
- **자동 퀘스트 생성**
  - 우선 규칙 기반(seed + 과목/태그 중복 검사 + 질문 패턴 분석)으로 슬롯을 채우고, 빈 슬롯이 있으면 LLM이 세부 내용을 보강.
  - 수학 문제형은 "어떤 유형의 문제를 풀어라" 식으로 비선형 퀘스트 문장을 생성. 영어는 듣기/독해/단어암기 균형 유지.
  - Tag 기반 통계(질문 로그, 실패 이력)로 weight 조정 예정. 구현 시 DB에 태그별 실패 카운터 누적.

## 7. 실행 & 운영
- **Backend**: `uvicorn backend.app:app --reload --port 8000` 또는 `start_server.bat [port]`.
- **Frontend**: `python -m http.server 5500 -d frontend` 또는 `start_frontend.bat [port]`.
- **동시 실행**: `start_all.bat` (두 개 콘솔 자동 실행).
- **캐시 이슈**: 브라우저 강제 새로고침(Ctrl+F5) 추천. 정적 자산 경로 바뀌면 캐시된 SVG/CSS 때문에 UI가 안 바뀐 것처럼 보일 수 있음.

## 8. 알려진 한계 / TODO
1. 학습형 카드의 `pause` 표기가 아직 UI에서 덜 명확(상태 텍스트만 변경). 상태 배지/애니메이션 필요.
2. 비시간형(성공/실패) 카드의 로그 저장/재시도 UX 미완료.
3. AI Planner 추천 결과를 프론트에서 미리보기/수락 플로우로 연결 필요.
4. 챗봇 패널 UI, 질문 로그 시각화, 과목 개요 섹션 실제 데이터 연동.
5. 마스코트/레벨업 시스템 및 보상 구조는 보류 중이나 데이터 훅(연속 학습일 등)은 이미 계산되고 있음.
ㄴ 마스코드는 폐기

## 9. 협업 시 스타일
- 모든 커뮤니케이션/문서는 한국어, 기술 용어 혼용 OK.
- 프론트: 레이아웃/스타일과 로직 분리 유지(템플릿만 교체해도 동작하도록). CSS 변수/클래스로 상태 표현, JS는 DOM 조작만 담당.
- 백엔드: 라우터-서비스-DB 계층 구분. FastAPI pydantic 스키마로 입출력 명시. SQLAlchemy 세션은 `database.py`의 SessionLocal 사용.
- 테스트/디버그 시 `admin/reset_all?seed=true`로 초기 상태 보장 후 확인.
- 새 AI 기능은 `.env`/설정 키를 먼저 정의 → config.py에서 로딩 → 서비스 계층에 주입하는 순서를 지킬 것.

이 파일은 AI 파트너가 프로젝트 맥락을 빠르게 로드하고, 기능/규칙을 깨뜨리지 않도록 파수꾼 역할을 합니다.
