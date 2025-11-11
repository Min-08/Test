import { api } from './api.js';

let ticking = null;
let pendingDelta = 0;
let lastSent = Date.now();
let userIdRef = null;
let currentSubjectLabel = null;
let currentSubjectKey = null;

const SUBJECT_LABELS = {
  korean: '국어',
  math: '수학',
  english: '영어',
};

const LABEL_TO_KEY = Object.fromEntries(
  Object.entries(SUBJECT_LABELS).map(([key, label]) => [label, key])
);

const STUDY_TAG = 'study';
const STUDY_TAG_KO = '학습';
const studyQuestIds = {};

const formatTime = seconds => new Date(seconds * 1000).toISOString().slice(11, 19);

export function initTimerControls({ userId }) {
  userIdRef = userId;
  document.getElementById('pause').addEventListener('click', pause);
  document.getElementById('stop').addEventListener('click', stop);
  document.querySelectorAll('.subject-buttons .subject').forEach(btn => {
    btn.addEventListener('click', () => selectSubject(btn.dataset.subject, btn));
  });
}

async function selectSubject(subjectKey, button) {
  const label = SUBJECT_LABELS[subjectKey] || subjectKey;
  if (ticking && currentSubjectLabel && currentSubjectLabel !== label) {
    await flushWithSubject(currentSubjectLabel);
  }
  currentSubjectKey = subjectKey;
  currentSubjectLabel = label;
  document.querySelectorAll('.subject-buttons .subject').forEach(btn => {
    btn.classList.toggle('active', btn === button);
  });
  if (!ticking) start();
  try {
    const quest = await api.post('/timer/update', {
      user_id: userIdRef,
      subject: currentSubjectLabel,
      delta_seconds: 0,
    });
    trackStudyQuest(quest);
    await updateStudyStatus(currentSubjectLabel, 'in_progress');
    updateProgressUI(quest);
    window.dispatchEvent(new CustomEvent('quest-sync'));
    window.dispatchEvent(new CustomEvent('global-subject-changed', { detail: { subject: currentSubjectLabel } }));
  } catch (error) {
    console.error(error);
  }
}

function updateProgressUI(quest) {
  if (!quest.goal_value) return;
  const totalSeconds = quest.progress_seconds ?? quest.progress_value * 60;
  const percent = Math.min(100, Math.round((totalSeconds / (quest.goal_value * 60)) * 100));
  document.getElementById('progress-bar').style.width = `${percent}%`;
  document.getElementById('current-quest-label').textContent = `${quest.title} · ${percent}%`;
}

function start() {
  if (ticking || !currentSubjectLabel) {
    if (!currentSubjectLabel) alert('과목 버튼을 먼저 선택하세요.');
    return;
  }
  ticking = setInterval(async () => {
    pendingDelta += 1;
    const elapsedLabel = document.getElementById('elapsed');
    const total = parseTime(elapsedLabel.textContent) + 1;
    elapsedLabel.textContent = formatTime(total);
    if (Date.now() - lastSent >= 5000) {
      await flushCurrent();
      lastSent = Date.now();
    }
  }, 1000);
}

function parseTime(value) {
  const [h, m, s] = value.split(':').map(Number);
  return h * 3600 + m * 60 + s;
}

async function pause() {
  if (!ticking) return;
  clearInterval(ticking);
  ticking = null;
  const subject = currentSubjectLabel;
  await flushCurrent();
  if (subject) await updateStudyStatus(subject, 'paused');
}

async function stop() {
  const subject = currentSubjectLabel;
  await pause();
  document.getElementById('elapsed').textContent = '00:00:00';
  currentSubjectLabel = null;
  currentSubjectKey = null;
  document.querySelectorAll('.subject-buttons .subject').forEach(btn => btn.classList.remove('active'));
  document.getElementById('current-quest-label').textContent = '진행 중인 퀘스트 없음';
  document.getElementById('progress-bar').style.width = '0%';
  if (subject) await updateStudyStatus(subject, 'paused');
}

async function flushCurrent() {
  if (pendingDelta <= 0 || !currentSubjectLabel) return;
  const subject = currentSubjectLabel;
  try {
    const quest = await api.post('/timer/update', {
      user_id: userIdRef,
      subject: currentSubjectLabel,
      delta_seconds: pendingDelta,
    });
    pendingDelta = 0;
    trackStudyQuest(quest);
    updateProgressUI(quest);
    window.dispatchEvent(new CustomEvent('quest-sync'));
    if (quest.status === 'completed') {
      clearStudyQuest(subject);
      await stop();
      alert('퀘스트 완료!');
    }
  } catch (error) {
    console.error(error);
  }
}

async function flushWithSubject(subject) {
  if (pendingDelta <= 0) return;
  try {
    await api.post('/timer/update', {
      user_id: userIdRef,
      subject,
      delta_seconds: pendingDelta,
    });
    pendingDelta = 0;
    await updateStudyStatus(subject, 'paused');
    window.dispatchEvent(new CustomEvent('quest-sync'));
  } catch (error) {
    console.error(error);
  }
}

export async function resetAll() {
  await stop();
}

export function isGlobalRunning() {
  return !!ticking;
}

export function ensureGlobalFor(subject) {
  const key = LABEL_TO_KEY[subject] || subject;
  if (ticking) return;
  const button = Array.from(document.querySelectorAll('.subject-buttons .subject')).find(btn => btn.dataset.subject === key);
  if (button) selectSubject(key, button);
}

export function setGlobalSubject(subject) {
  const key = LABEL_TO_KEY[subject] || subject;
  const button = Array.from(document.querySelectorAll('.subject-buttons .subject')).find(btn => btn.dataset.subject === key);
  if (button) selectSubject(key, button);
}

export function hardResetTimers() {
  if (ticking) {
    clearInterval(ticking);
    ticking = null;
  }
  pendingDelta = 0;
  lastSent = Date.now();
  currentSubjectLabel = null;
  currentSubjectKey = null;
  document.getElementById('elapsed').textContent = '00:00:00';
  document.querySelectorAll('.subject-buttons .subject').forEach(btn => btn.classList.remove('active'));
  const label = document.getElementById('current-quest-label');
  if (label) label.textContent = '진행 중인 퀘스트 없음';
  const bar = document.getElementById('progress-bar');
  if (bar) bar.style.width = '0%';
}

function trackStudyQuest(quest) {
  if (!quest) return;
  const tags = quest.tags || [];
  const tagsKo = quest.tags_ko || [];
  if (tags.includes(STUDY_TAG) || tagsKo.includes(STUDY_TAG_KO)) {
    studyQuestIds[quest.subject] = quest.id;
  }
}

function clearStudyQuest(subject) {
  if (subject && studyQuestIds[subject]) {
    delete studyQuestIds[subject];
  }
}

async function updateStudyStatus(subject, status) {
  const questId = studyQuestIds[subject];
  if (!questId) return;
  try {
    await api.patch(`/quests/${questId}`, { status });
  } catch (error) {
    console.error(error);
  }
}
