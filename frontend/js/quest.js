import { api } from './api.js';
import { isGlobalRunning, ensureGlobalFor, setGlobalSubject } from './timer.js';
import { getUserId } from './session.js';

const STUDY_TAG = 'study';
const STUDY_TAG_KO = '학습';
const LABEL_TO_KEY = {
  '국어': 'korean',
  '수학': 'math',
  '영어': 'english',
  korean: 'korean',
  math: 'math',
  english: 'english',
};

const BOOK_ICON = `
  <svg width="32" height="32" viewBox="0 0 32 32" fill="none" xmlns="http://www.w3.org/2000/svg">
    <path d="M5.33333 26C5.33333 25.116 5.68452 24.2681 6.30964 23.643C6.93476 23.0179 7.78261 22.6667 8.66666 22.6667H26.6667M5.33333 26C5.33333 26.8841 5.68452 27.7319 6.30964 28.357C6.93476 28.9822 7.78261 29.3333 8.66666 29.3333H26.6667V2.66667H8.66666C7.78261 2.66667 6.93476 3.01786 6.30964 3.64298C5.68452 4.2681 5.33333 5.11595 5.33333 6.00001V26Z" stroke="#1E1E1E" stroke-width="3" stroke-linecap="round" stroke-linejoin="round" />
  </svg>`;

let activeQuestTimer = null;
let activeQuestSubject = null;
let activeQuestId = null;

export function renderQuestList(quests) {
  const container = document.getElementById('quest-list');
  if (!container) return;
  container.innerHTML = '';

  const isStudy = q => (q.tags || []).includes(STUDY_TAG) || (q.tags_ko || []).includes(STUDY_TAG_KO);
  const progress = q => {
    if (!q.goal_value || q.goal_value <= 0) return 0;
    const seconds = q.progress_seconds ?? ((q.progress_value || 0) * 60);
    return Math.min(1, seconds / (q.goal_value * 60));
  };

  const timeQuests = quests
    .filter(q => q.type === 'time' && !isStudy(q))
    .sort((a, b) => progress(b) - progress(a))
    .slice(0, 4);
  const problemQuest = quests.filter(q => q.type === 'problem').slice(0, 1);
  const ordered = [...timeQuests, ...problemQuest];

  ordered.forEach(q => {
    const card = document.createElement('div');
    card.className = 'quest-card';
    card.dataset.questId = q.id;
    const pct = Math.round(progress(q) * 100);
    const isProblem = Number(q.goal_value) === 0 || q.type === 'problem';

    card.innerHTML = `
      <div class="quest-icon" aria-hidden="true">${BOOK_ICON}</div>
      <div class="quest-body">
        <div class="quest-text">
          <div class="quest-title">
            ${escapeHtml(q.title)}
            <span class="quest-active-label" data-role="active-label"></span>
          </div>
        </div>
        ${!isProblem ? progressBar(pct, q.id) : ''}
        ${isProblem ? problemInput(q.id) : ''}
      </div>
    `;

    if (!isProblem) {
      card.classList.add('clickable');
      card.addEventListener('click', () => startQuestTimer(q));
    }

    if (isProblem) {
      const input = card.querySelector(`[data-quest-input="${q.id}"]`);
      if (input) {
        input.addEventListener('keydown', event => {
          if (event.key === 'Enter') {
            const value = input.value.trim();
            if (!value) return;
            submitAnswer(q.id, value, input);
          }
        });
      }
    }

    container.appendChild(card);
  });

  markActiveCard();
}

function progressBar(percent, questId) {
  return `
    <div class="quest-progress" role="progressbar" aria-valuemin="0" aria-valuemax="100" aria-valuenow="${percent}" aria-label="퀘스트 진행도" data-quest-progress="${questId}">
      <div class="quest-progress-track"></div>
      <div class="quest-progress-filled" style="width:${percent}%"></div>
      <div class="quest-progress-footer">${percent}%</div>
    </div>
  `;
}

function problemInput(id) {
  return `
    <div class="quest-answer-input">
      <input type="text" placeholder="여기에 입력하시오." data-quest-input="${id}" aria-label="퀘스트 정답 입력" />
    </div>
  `;
}

async function submitAnswer(id, value, inputEl) {
  try {
    const res = await api.post(`/quests/${id}/answer`, { user_id: getUserId(), answer: value });
    if (res.correct) {
      alert('정답입니다!');
      if (inputEl) inputEl.value = '';
      window.dispatchEvent(new CustomEvent('quest-sync'));
    } else {
      alert(res.expected_answer ? `오답입니다. 정답: ${res.expected_answer}` : '오답입니다.');
      if (inputEl) inputEl.select();
    }
  } catch (error) {
    console.error(error);
    alert('답안을 전송하지 못했습니다.');
  }
}

function startQuestTimer(q) {
  if (activeQuestTimer && activeQuestTimer.id !== q.id) {
    stopCurrentQuestTimer('switch');
  }
  if (activeQuestTimer && activeQuestTimer.id === q.id) {
    stopCurrentQuestTimer('pause');
    return;
  }

  api.patch(`/quests/${q.id}`, { status: 'in_progress' }).catch(() => {});
  setGlobalSubject(q.subject);
  if (!isGlobalRunning()) ensureGlobalFor(q.subject);

  const state = { delta: 0, lastSent: Date.now() };
  activeQuestId = q.id;
  markActiveCard(q.id);
  const interval = setInterval(async () => {
    state.delta += 1;
    if (Date.now() - state.lastSent >= 5000) {
      const updated = await flushQuestDelta(q.id, state);
      state.lastSent = Date.now();
      if (updated && updated.status === 'completed') {
        stopCurrentQuestTimer('completed');
      }
    }
  }, 1000);

  activeQuestTimer = { id: q.id, interval, state };
  activeQuestSubject = q.subject;
}

async function flushQuestDelta(id, state) {
  if (state.delta <= 0) return null;
  try {
    const updated = await api.post('/timer/update', {
      user_id: getUserId(),
      quest_id: id,
      delta_seconds: state.delta,
    });
    state.delta = 0;
    window.dispatchEvent(new CustomEvent('quest-sync'));
    return updated;
  } catch (error) {
    console.error(error);
    return null;
  }
}

function stopCurrentQuestTimer(reason) {
  if (!activeQuestTimer) return;
  const { id, interval, state } = activeQuestTimer;
  clearInterval(interval);
  activeQuestTimer = null;
  activeQuestSubject = null;
  activeQuestId = null;
  markActiveCard(null);

  flushQuestDelta(id, state).finally(() => {
    if (reason !== 'completed') {
      api.patch(`/quests/${id}`, { status: 'paused' }).catch(() => {});
    }
    window.dispatchEvent(new CustomEvent('quest-sync'));
  });
}

window.addEventListener('global-subject-changed', event => {
  const subject = event.detail?.subject;
  if (!activeQuestTimer) return;
  if (activeQuestSubject && subject && activeQuestSubject !== subject) {
    stopCurrentQuestTimer('pause');
  }
});

export function hardResetQuestTimer() {
  if (!activeQuestTimer) return;
  clearInterval(activeQuestTimer.interval);
  activeQuestTimer = null;
  activeQuestSubject = null;
  activeQuestId = null;
  markActiveCard(null);
}

function markActiveCard(questId = activeQuestId) {
  document.querySelectorAll('.quest-card').forEach(card => {
    const label = card.querySelector('[data-role="active-label"]');
    if (!label) return;
    const isActive = questId && card.dataset.questId === questId;
    label.textContent = isActive ? '선택됨' : '';
  });
}

function escapeHtml(text) {
  if (!text) return '';
  return text.replace(/[&<>"']/g, ch => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[ch] || ch));
}
