# 개인화 학습 퀘스트 플래너 (MVP)

- 프론트: `frontend/` 정적 파일 (HTML/CSS/JS)
- 백엔드: `backend/` FastAPI + SQLite(SQLAlchemy)
- 데이터: `data/seed_quests.json` 초기 퀘스트

## 실행 방법
1) 가상환경 구성 후 의존성 설치
```
pip install -r requirements.txt
```
1-1) .env 설정 (선택: ChatGPT 연동)
```
cp .env.example .env
# .env를 열고 OPENAI_API_KEY를 설정하세요.
# 분류/응답 모델을 선택적으로 조정할 수 있습니다.
#   OPENAI_MODEL_CLASSIFY=gpt-5-nano
#   OPENAI_MODEL_MINI=gpt-5-mini
#   OPENAI_MODEL_FULL=gpt-5
```
2) 백엔드 실행
```
uvicorn backend.app:app --reload --port 8000
```
3) 프론트 열기
- `frontend/index.html` 파일을 브라우저에서 직접 열거나,
- 간단 서버로 정적 서빙:
```
python -m http.server 5500 -d frontend
```
(브라우저에서 http://127.0.0.1:5500/index.html 접속)

## 주요 엔드포인트
- GET `/quests?user_id=u1` : 퀘스트 목록
- POST `/timer/update` : 타이머 동기화 `{user_id, quest_id, delta_seconds}`
  - 전역 타이머 UI에서는 `{user_id, subject, delta_seconds}` 형태로 호출 (서버가 해당 과목의 활성 퀘스트를 자동 매핑/생성)
- POST `/ai/logs/questions` : 질문 로그 저장
- GET `/ai/planner/suggest?user_id=u1` : 룰 기반 퀘스트 제안
- POST `/ai/chat` : 질문 → AI 답변 (키는 백엔드 .env에서만 사용)
  - 내부에서 분류 모델(`gpt-5-nano`)로 과목/난이도 판정 → 난이도에 따라 `gpt-5-mini` 또는 `gpt-5` 선택 호출
- GET `/stats/summary?user_id=u1&days=7` : 국/영/수 집계 및 연속 학습일
- POST `/admin/reset_all` : 전체 초기화(모든 사용자/퀘스트/로그 삭제 후 기본 `u1` 재생성). 쿼리 `?seed=true` 시 시드 퀘스트 주입

## UI 개요 (알파)
- 좌측: 퀘스트 목록(축소)
- 중앙: 마스코트(보류)
- 우측: 전역 타이머(국어/수학/영어 버튼), 진행 바(퀘스트 이름 + %)
- 우측 하단 질문 버튼: 모달에서 `/ai/chat` 호출 → 응답을 모달 내 박스에 표시(키는 프런트에 노출되지 않음)

## 다음 단계
- `/ai/planner/suggest`에 실패율/질문 패턴 가중치 반영
- 프론트에 통계/제안 표시 및 “제안 적용” 버튼 연결
- 마스코트 상태 연동(연속 공부일/성공률 기반)
