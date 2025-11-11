# 개인화 학습 퀘스트 플래너 (Alpha/MVP)

- 프론트: `frontend/` 정적 HTML/CSS/JS
- 백엔드: `backend/` FastAPI + SQLite(SQLAlchemy)
- 데이터: `data/seed_quests.json` (초기 퀘스트 시드)

## 실행 방법
1) 의존성 설치
```
pip install -r requirements.txt
```
1-1) .env 설정(선택: ChatGPT 연동)
```
# 예시 파일 복사
cp .env.example .env
# .env 파일 열어서 OPENAI_API_KEY 입력
# (선택) 모델 변경
#   OPENAI_MODEL_CLASSIFY=gpt-5-nano
#   OPENAI_MODEL_MINI=gpt-5-mini
#   OPENAI_MODEL_FULL=gpt-5
```
2) 백엔드 실행
```
uvicorn backend.app:app --reload --port 8000
```
3) 프론트 열기
- 정적 서버: `python -m http.server 5500 -d frontend` 후 브라우저에서 http://127.0.0.1:5500 접속
- 또는 `frontend/index.html` 파일을 직접 열어도 OK

## 주요 기능
- 전역 타이머(국어/수학/영어 버튼)
  - 버튼 클릭 시 즉시 시작, 5초마다 서버에 누적
  - 과목 전환 시 이전 과목 시간 우선 기록 후 계속 측정
  - 과목별 활성(time) 퀘스트 자동 매핑/자동 생성(과목당 1개, 총 3개)
  - 자동 생성 시 목표 시간은 25/50/90분 중 목표에 가장 가까운 값으로 선택
- 퀘스트 목록
  - 서버 상태를 반영해 자동 갱신(타이머 동기화 시 이벤트로 갱신)
- 질문/챗봇
  - `/ai/chat` 호출: 분류 모델(`gpt-5-nano`)로 과목/난이도 판정 → `gpt-5-mini` 또는 `gpt-5`로 답변 생성
  - 키/모델은 백엔드에서만 사용(.env), 프론트에는 노출되지 않음
- AI 문제 퀘스트(시간 제약 없음)
  - `POST /ai/quests/ai_problem?user_id=u1&subject=수학|국어|영어`
  - 과목별로 활성 1개만 생성되며, 태그는 [`ai-problem`] / [`AI문제`]
  - `quests.meta`에 문제/정답/풀이요약이 저장됨, `goal_value=0`
- 통계
  - `/stats/summary`: 최근 N일 과목별 총 분, 일별 합계, 연속 학습일
- 전체 초기화
  - `/admin/reset_all` (프론트 우하단 빨간 버튼)
  - `?seed=true`로 초기 퀘스트 시드 재주입
  - 시드 파일은 `tags_ko`(한글 태그)와 `tags`(영문 번역)를 포함합니다. 예) 문제풀이→problem-solving, 단어암기(영어)→english-vocabulary, 복습→review, 듣기(영어)→english-listening

## API 요약
- 퀘스트: `GET /quests?user_id=u1`, `POST /quests`, `PATCH /quests/{id}`
- 타이머: `POST /timer/update` `{user_id, subject, delta_seconds}` 또는 `{user_id, quest_id, delta_seconds}`
- 플래너: `GET /ai/planner/suggest?user_id=u1`
- 질문 로그/챗봇: `POST /ai/chat`
- AI 문제 생성: `POST /ai/quests/ai_problem?user_id=u1&subject=수학`
- 통계: `GET /stats/summary?user_id=u1&days=7`
- 전체 초기화: `POST /admin/reset_all[?seed=true]`

## 주의/팁
- 개발 중에는 `--reload`로 코드 저장 시 자동 재시작
- SQLite 파일은 `backend/app.db` (스키마 변경 시 서버 중지 후 삭제/재생성 권장)
- 캐시 문제 있으면 브라우저 강력 새로고침(Ctrl+F5)
