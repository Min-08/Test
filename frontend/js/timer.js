import { api } from './api.js';

let ticking = null;
let pendingDelta = 0;
let lastSent = Date.now();
let elapsedSeconds = 0;
let userIdRef = null;
let currentSubjectLabel = null;
let currentSubjectKey = null;

const DEFAULT_SUBJECT_LABEL = '학습';
const DEFAULT_SUBJECT_KEY = 'study';

const SUBJECT_LABELS = {
  korean: '국어',
  math: '수학',
  english: '영어',
  [DEFAULT_SUBJECT_KEY]: DEFAULT_SUBJECT_LABEL,
};

const LABEL_TO_KEY = {
  ...Object.fromEntries(Object.entries(SUBJECT_LABELS).map(([key, label]) => [label, key])),
  korean: 'korean',
  math: 'math',
  english: 'english',
  [DEFAULT_SUBJECT_KEY]: DEFAULT_SUBJECT_KEY,
};

const STUDY_TAG = 'study';
const STUDY_TAG_KO = '학습';
const studyQuestIds = {};
const blockedSubjects = new Set();
const DEFAULT_QUEST_LABEL = '진행 중인 퀘스트가 없음';
const STOPWATCH_EVENT = 'subject-stopwatch';
const DAY_RESET_TIMEZONE = 'Asia/Seoul';
const dayFormatter = new Intl.DateTimeFormat('en-CA', {
  timeZone: DAY_RESET_TIMEZONE,
  year: 'numeric',
  month: '2-digit',
  day: '2-digit',
});
let activeDayKey = dayFormatter.format(new Date());

const dispatchStopwatchEvent = running => {
  window.dispatchEvent(new CustomEvent(STOPWATCH_EVENT, { detail: { running } }));
};

const formatTime = seconds => {
  const safe = Number.isFinite(seconds) && seconds >= 0 ? seconds : 0;
  return new Date(safe * 1000).toISOString().slice(11, 19);
};

const updateElapsedDisplay = () => {
  const label = document.getElementById('elapsed');
  if (label) label.textContent = formatTime(elapsedSeconds);
};

const getCurrentDayKey = () => dayFormatter.format(new Date());

async function maybeResetForNewDay() {
  const todayKey = getCurrentDayKey();
  if (todayKey === activeDayKey) return;
  await flushCurrent();
  pendingDelta = 0;
  elapsedSeconds = 0;
  activeDayKey = todayKey;
  lastSent = Date.now();
  updateElapsedDisplay();
  blockedSubjects.clear();
  window.dispatchEvent(new CustomEvent('global-day-reset', { detail: { day: todayKey } }));
}

export function initTimerControls({ userId }) {
  userIdRef = userId;
  const pauseBtn = document.getElementById('pause');
  const stopBtn = document.getElementById('stop');
  if (pauseBtn) pauseBtn.addEventListener('click', pause);
  if (stopBtn) stopBtn.addEventListener('click', stop);
  document.querySelectorAll('.subject-buttons .subject').forEach(btn => {
    btn.addEventListener('click', () => selectSubject(btn.dataset.subject, btn));
  });
  updateElapsedDisplay();
}

async function selectSubject(subjectKey, button = null) {
  if (!subjectKey) return;
  const label = SUBJECT_LABELS[subjectKey] || subjectKey;
  const isBlocked = blockedSubjects.has(label);
  if (ticking && currentSubjectLabel && currentSubjectLabel !== label) {
    await flushWithSubject(currentSubjectLabel);
  }
  if (currentSubjectKey === subjectKey && ticking) {
    highlightSubjectButton(button);
    return;
  }

  currentSubjectKey = subjectKey;
  currentSubjectLabel = label;
  highlightSubjectButton(button);
  if (!ticking) start();

  if (!isBlocked) {
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
    } catch (error) {
      console.error(error);
    }
  }
  window.dispatchEvent(
    new CustomEvent('global-subject-changed', { detail: { subject: currentSubjectLabel } }),
  );
}

function updateProgressUI(quest) {
  if (!quest || !quest.goal_value) return;
  const totalSeconds = quest.progress_seconds ?? (quest.progress_value || 0) * 60;
  const percent = Math.min(100, Math.round((totalSeconds / (quest.goal_value * 60)) * 100));
  const bar = document.getElementById('progress-bar');
  const label = document.getElementById('current-quest-label');
  if (bar) bar.style.width = `${percent}%`;
  if (label) label.textContent = `${quest.title} · ${percent}%`;
}

function start() {
  if (ticking) return;
  if (!currentSubjectLabel) {
    currentSubjectLabel = DEFAULT_SUBJECT_LABEL;
    currentSubjectKey = DEFAULT_SUBJECT_KEY;
  }
  ticking = setInterval(async () => {
    await maybeResetForNewDay();
    elapsedSeconds += 1;
    updateElapsedDisplay();
    if (currentSubjectLabel && !blockedSubjects.has(currentSubjectLabel)) {
      pendingDelta += 1;
      if (Date.now() - lastSent >= 5000) {
        await flushCurrent();
        lastSent = Date.now();
      }
    }
  }, 1000);
  dispatchStopwatchEvent(true);
}

async function pause() {
  if (!ticking) return;
  clearInterval(ticking);
  ticking = null;
  lastSent = Date.now();
  const subject = currentSubjectLabel;
  await flushCurrent();
  if (subject) await updateStudyStatus(subject, 'paused');
  dispatchStopwatchEvent(false);
}

async function stop() {
  await pause();
  elapsedSeconds = 0;
  updateElapsedDisplay();
  currentSubjectLabel = null;
  currentSubjectKey = null;
  document.querySelectorAll('.subject-buttons .subject').forEach(btn => btn.classList.remove('active'));
  const label = document.getElementById('current-quest-label');
  const bar = document.getElementById('progress-bar');
  if (label) label.textContent = DEFAULT_QUEST_LABEL;
  if (bar) bar.style.width = '0%';
}

async function flushCurrent() {
  if (pendingDelta <= 0 || !currentSubjectLabel || blockedSubjects.has(currentSubjectLabel)) {
    pendingDelta = 0;
    return;
  }
  const subject = currentSubjectLabel;
  try {
    const quest = await api.post('/timer/update', {
      user_id: userIdRef,
      subject: currentSubjectLabel,
      delta_seconds: pendingDelta,
    });
    pendingDelta = 0;
    lastSent = Date.now();
    trackStudyQuest(quest);
    updateProgressUI(quest);
    window.dispatchEvent(new CustomEvent('quest-sync'));
    if (quest.status === 'completed') {
      onStudyGoalCompleted(subject, quest);
    }
  } catch (error) {
    console.error(error);
  }
}

async function flushWithSubject(subject) {
  if (!subject) return;
  try {
    if (pendingDelta > 0) {
      await api.post('/timer/update', {
        user_id: userIdRef,
        subject,
        delta_seconds: pendingDelta,
      });
      pendingDelta = 0;
      lastSent = Date.now();
    }
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
  const button = Array.from(document.querySelectorAll('.subject-buttons .subject')).find(
    btn => btn.dataset.subject === key,
  );
  if (button) {
    selectSubject(key, button);
  } else {
    selectSubject(key);
  }
}

export function setGlobalSubject(subject) {
  const key = LABEL_TO_KEY[subject] || subject;
  const button = Array.from(document.querySelectorAll('.subject-buttons .subject')).find(
    btn => btn.dataset.subject === key,
  );
  if (button) {
    selectSubject(key, button);
  } else {
    selectSubject(key);
  }
}

export function hardResetTimers() {
  if (ticking) {
    clearInterval(ticking);
    ticking = null;
  }
  pendingDelta = 0;
  elapsedSeconds = 0;
  lastSent = Date.now();
  currentSubjectLabel = null;
  currentSubjectKey = null;
  activeDayKey = getCurrentDayKey();
  updateElapsedDisplay();
  document.querySelectorAll('.subject-buttons .subject').forEach(btn => btn.classList.remove('active'));
  const label = document.getElementById('current-quest-label');
  const bar = document.getElementById('progress-bar');
  if (label) label.textContent = DEFAULT_QUEST_LABEL;
  if (bar) bar.style.width = '0%';
  dispatchStopwatchEvent(false);
}

export function startGlobalStopwatch() {
  start();
}

export function pauseGlobalStopwatch() {
  pause();
}

export async function addDevTime(extraSeconds) {
  if (!ticking || !currentSubjectLabel) {
    throw new Error('No active global timer to fast-forward.');
  }
  const seconds = Number(extraSeconds) || 0;
  if (!Number.isFinite(seconds) || seconds <= 0) {
    throw new Error('extraSeconds must be a positive number.');
  }
  pendingDelta += seconds;
  elapsedSeconds += seconds;
  updateElapsedDisplay();
  await flushCurrent();
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

function highlightSubjectButton(button) {
  document.querySelectorAll('.subject-buttons .subject').forEach(btn => {
    if (button) {
      btn.classList.toggle('active', btn === button);
    } else {
      btn.classList.toggle('active', btn.dataset.subject === currentSubjectKey);
    }
  });
}

export async function forceDayReset() {
  activeDayKey = '';
  await maybeResetForNewDay();
}

function onStudyGoalCompleted(subject, quest) {
  blockedSubjects.add(subject);
  clearStudyQuest(subject);
  pendingDelta = 0;
  if (currentSubjectLabel === subject) {
    currentSubjectLabel = null;
    currentSubjectKey = null;
    highlightSubjectButton(null);
  }
  window.dispatchEvent(
    new CustomEvent('study-goal-complete', {
      detail: { subject, goalMinutes: quest?.goal_value || quest?.goal || 0 },
    }),
  );
}
