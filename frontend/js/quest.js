import { api } from './api.js';
import { isGlobalRunning, ensureGlobalFor, setGlobalSubject } from './timer.js';

const STUDY_TAG = 'study';
const STUDY_TAG_KO = '학습';

let activeQuestTimer = null; // { id, interval, state }
let activeQuestSubject = null;

function isStudyQuest(q) {
  const tags = q.tags || [];
  const tagsKo = q.tags_ko || [];
  return tags.includes(STUDY_TAG) || tagsKo.includes(STUDY_TAG_KO);
}

function questProgress(q) {
  if (!q.goal_value || q.goal_value <= 0) return 0;
  const seconds = q.progress_seconds ?? ((q.progress_value || 0) * 60);
  const goalSeconds = q.goal_value * 60;
  return Math.min(1, seconds / goalSeconds);
}

export function renderQuestList(quests) {
  const container = document.getElementById('quest-list');
  if (!container) return;
  container.innerHTML = '';

  const studyQuests = quests.filter(isStudyQuest);
  const otherTimeQuests = quests.filter(q => q.type === 'time' && !isStudyQuest(q)).sort((a, b) => questProgress(b) - questProgress(a));
  const problemQuests = quests.filter(q => q.type === 'problem');

  const mainQuest = otherTimeQuests.length ? otherTimeQuests[0] : null;
  const ordered = [...studyQuests, ...otherTimeQuests, ...problemQuests];

  ordered.forEach(q => {
    const card = document.createElement('div');
    card.className = 'quest-card';
    const isProblem = Number(q.goal_value) === 0;
    const percent = Math.round(questProgress(q) * 100);
    const metaLine = isProblem ? `${q.subject}` : `${q.subject} · 목표 ${q.goal_value}분 · ${percent}%`;

    card.innerHTML = `
      <div style="flex:1">
        <div class="title">${escapeHtml(q.title)} ${(!isProblem && mainQuest && mainQuest.id === q.id) ? `<span style='color:#10a37f;font-size:12px;'>[메인]</span>` : ''}</div>
        <div class="meta">${metaLine}</div>
        ${isStudyQuest(q) ? `<div class="progress"><div class="bar" style="width:${Math.min(100, percent)}%;"></div></div>` : ''}
        ${isProblem && q.meta && q.meta.problem ? `<div class="problem">${escapeHtml(snippet(q.meta.problem, 120))}</div>` : ''}
      </div>
      <div style="display:flex; flex-direction:column; align-items:flex-end; gap:6px;">
        <div class="meta">${escapeHtml(q.status)}</div>
        ${isProblem ? `<div class="actions"><button class="mini" data-act="success">성공</button><button class="mini" data-act="failure">실패</button></div>` : ''}
      </div>
    `;

    if (isProblem) {
      const successBtn = card.querySelector('button[data-act="success"]');
      const failureBtn = card.querySelector('button[data-act="failure"]');
      successBtn.addEventListener('click', () => submitResult(q.id, 'success'));
      failureBtn.addEventListener('click', () => submitResult(q.id, 'failure'));
    } else if (!isStudyQuest(q)) {
      card.style.cursor = 'pointer';
      card.addEventListener('click', () => startQuestTimer(q));
    }

    container.appendChild(card);
  });
}

function snippet(text, max) {
  if (!text) return '';
  return text.length > max ? `${text.slice(0, max)}...` : text;
}

function escapeHtml(text) {
  if (!text) return '';
  return text.replace(/[&<>"']/g, ch => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[ch] || ch));
}

async function submitResult(id, result) {
  try {
    await api.post(`/quests/${id}/result`, { user_id: 'u1', result });
    window.dispatchEvent(new CustomEvent('quest-sync'));
  } catch (error) {
    console.error(error);
    alert('결과 저장 실패');
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

async function flushQuestDelta(questId, state) {
  if (state.delta <= 0) return null;
  try {
    const updated = await api.post('/timer/update', { user_id: 'u1', quest_id: questId, delta_seconds: state.delta });
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
}

