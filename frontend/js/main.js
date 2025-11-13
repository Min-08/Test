import { api } from './api.js';
import { renderQuestList, hardResetQuestTimer } from './quest.js';
import {
  initTimerControls,
  hardResetTimers,
  startGlobalStopwatch,
  pauseGlobalStopwatch,
  addDevTime,
  setGlobalSubject,
  forceDayReset,
} from './timer.js';
import { getUserId } from './session.js';

const state = {
  userId: getUserId(),
  quests: [],
};

let realClockTimer = null;

const SUBJECT_KEY_TO_LABEL = {
  korean: '국어',
  math: '수학',
  english: '영어',
};

const completedStudySubjects = new Set();
const subjectGoalMinutes = {};
const DAY_RESET_TIMEZONE = 'Asia/Seoul';
const dayFormatter = new Intl.DateTimeFormat('en-CA', {
  timeZone: DAY_RESET_TIMEZONE,
  year: 'numeric',
  month: '2-digit',
  day: '2-digit',
});
let activeDayKey = dayFormatter.format(new Date());

const STUDY_TAG = 'study';
const STUDY_TAG_KO = '학습';

const updateRealClock = () => {
  const label = document.getElementById('real-clock-label');
  if (!label) return;
  const formatter = new Intl.DateTimeFormat('ko-KR', {
    timeZone: 'Asia/Seoul',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  });
  label.textContent = formatter.format(new Date());
};

const startRealClock = () => {
  updateRealClock();
  clearInterval(realClockTimer);
  realClockTimer = setInterval(updateRealClock, 1000);
};

export async function loadQuests() {
  state.quests = await api.get(`/quests?user_id=${state.userId}`);
  renderQuestList(state.quests);
  updateSubjectProgressBars(state.quests);
}

async function handleReset() {
  if (!confirm('정말 전체 초기화하시겠어요? 모든 데이터가 삭제됩니다.')) return;
  const resetBtn = document.getElementById('reset-all');
  if (resetBtn) {
    resetBtn.disabled = true;
    resetBtn.style.opacity = '0.6';
  }
  try {
    hardResetQuestTimer();
    hardResetTimers();
    await api.post('/admin/reset_all?seed=true');
    try {
      await forceDayReset();
    } catch (resetError) {
      console.warn('Failed to force day reset after system reset', resetError);
    }
    window.location.reload();
  } catch (error) {
    console.error(error);
    alert('초기화에 실패했습니다.');
    if (resetBtn) {
      resetBtn.disabled = false;
      resetBtn.style.opacity = '1';
    }
  }
}

const getDevToastHost = () => {
  let host = document.getElementById('dev-toast-host');
  if (!host) {
    host = document.createElement('div');
    host.id = 'dev-toast-host';
    host.className = 'dev-toast-host';
    document.body.appendChild(host);
  }
  return host;
};

const showDevToast = (message, variant = 'info') => {
  const host = getDevToastHost();
  const toast = document.createElement('div');
  toast.className = `dev-toast dev-toast--${variant}`;
  toast.textContent = message;
  host.appendChild(toast);
  setTimeout(() => {
    toast.classList.add('dev-toast--hide');
    toast.addEventListener('transitionend', () => toast.remove(), { once: true });
  }, 2600);
};

async function handleDevAction(action) {
  try {
    switch (action) {
      case 'quest-refresh':
        await loadQuests();
        showDevToast('퀘스트 데이터를 새로 고쳤습니다.');
        break;
      case 'add-time':
        try {
          await addDevTime(300);
          window.dispatchEvent(new CustomEvent('quest-sync'));
          showDevToast('진행 중인 타이머에 5분을 추가했습니다.');
        } catch (error) {
          showDevToast('진행 중인 타이머가 없습니다.', 'warning');
        }
        break;
      case 'skip-day':
        try {
          await forceDayReset();
          showDevToast('하루를 강제로 넘겼습니다.');
          window.dispatchEvent(new CustomEvent('quest-sync'));
        } catch (error) {
          console.error(error);
          showDevToast('하루 넘기기에 실패했습니다.', 'warning');
        }
        break;
      case 'reset-all':
        await handleReset();
        showDevToast('전체 초기화를 실행했습니다.', 'warning');
        break;
      case 'close-dev':
        break;
      default:
        showDevToast('아직 연결되지 않은 동작입니다.', 'muted');
    }
  } catch (error) {
    console.error('[DevMode] action failed:', action, error);
    showDevToast('작업 수행 중 오류가 발생했습니다.', 'warning');
  }
}

function initApp() {
  hydrateCompletedSubjects();
  initSubjectProgressControls();
  loadQuests().catch(error => {
    console.error('[DevMode] 퀘스트 데이터를 불러오지 못했습니다.', error);
  });
  try {
    initTimerControls({ userId: state.userId });
  } catch (error) {
    console.error('[DevMode] 타이머 초기화에 실패했습니다.', error);
  }
  const resetBtn = document.getElementById('reset-all');
  if (resetBtn) resetBtn.addEventListener('click', handleReset);
  window.addEventListener('quest-sync', async () => {
    try {
      await loadQuests();
    } catch (error) {
      console.error(error);
    }
  });
  const devButton = document.getElementById('dev-toggle');
  const devPanel = document.getElementById('dev-panel');
  const handleDevKeydown = event => {
    if (event.key === 'Escape') {
      event.preventDefault();
      closeDevPanel();
    }
  };
  const openDevPanel = () => {
    if (!devPanel) return;
    devPanel.classList.remove('hidden');
    devPanel.setAttribute('aria-hidden', 'false');
    document.addEventListener('keydown', handleDevKeydown);
    const firstAction = devPanel.querySelector('[data-action]');
    if (firstAction) firstAction.focus();
    console.info('[DevMode] 개발자 도구가 열렸습니다.');
  };
  const closeDevPanel = () => {
    if (!devPanel) return;
    devPanel.classList.add('hidden');
    devPanel.setAttribute('aria-hidden', 'true');
    document.removeEventListener('keydown', handleDevKeydown);
    devButton?.focus();
  };
  if (devButton && devPanel) {
    devButton.addEventListener('click', () => {
      if (devPanel.classList.contains('hidden')) {
        openDevPanel();
      } else {
        closeDevPanel();
      }
    });
  }
  if (devPanel) {
    devPanel.addEventListener('click', event => {
      if (event.target === devPanel) {
        closeDevPanel();
        return;
      }
      const actionBtn = event.target.closest('[data-action]');
      if (!actionBtn) return;
      const action = actionBtn.dataset.action;
      if (!action) return;
      console.info(`[DevMode] ${action} 실행 요청`);
      window.dispatchEvent(new CustomEvent('dev-action', { detail: { action } }));
      handleDevAction(action);
      if (action === 'close-dev') closeDevPanel();
    });
  }
  startRealClock();
  const startBtn = document.getElementById('timer-start');
  const stopBtn = document.getElementById('timer-stop');
  if (startBtn) startBtn.addEventListener('click', () => startGlobalStopwatch());
  if (stopBtn) stopBtn.addEventListener('click', () => pauseGlobalStopwatch());

  window.addEventListener('global-day-reset', event => {
    const previousKey = activeDayKey;
    const nextKey = event.detail?.day || getCurrentDayKey();
    activeDayKey = nextKey;
    clearDailyCompletionState();
    persistCompletedSubjects();
    if (previousKey && previousKey !== nextKey) {
      removeCompletionStorageFor(previousKey);
    }
    updateSubjectProgressBars(state.quests);
  });

  window.addEventListener('study-goal-complete', event => {
    const subject = event.detail?.subject;
    const goalMinutes = event.detail?.goalMinutes;
    if (!subject) return;
    if (goalMinutes) subjectGoalMinutes[subject] = goalMinutes;
    completedStudySubjects.add(subject);
    persistCompletedSubjects();
    updateSubjectProgressBars(state.quests);
  });
}

function isStudyQuest(quest) {
  if (!quest) return false;
  const tags = quest.tags || [];
  const tagsKo = quest.tags_ko || [];
  return tags.includes(STUDY_TAG) || tagsKo.includes(STUDY_TAG_KO);
}

function initSubjectProgressControls() {
  const buttons = document.querySelectorAll('[data-subject-trigger]');
  buttons.forEach(button => {
    button.addEventListener('click', () => {
      const key = button.dataset.subjectTrigger;
      const label = SUBJECT_KEY_TO_LABEL[key] || key;
      setGlobalSubject(label);
    });
  });
}

function updateSubjectProgressBars(quests) {
  const rows = document.querySelectorAll('[data-subject-progress]');
  if (!rows.length) return;
  const studyQuestsBySubject = new Map();
  quests.forEach(q => {
    if (isStudyQuest(q)) {
      studyQuestsBySubject.set(q.subject, q);
    }
  });
  let completionStateChanged = false;
  rows.forEach(row => {
    const key = row.dataset.subjectKey;
    const label = SUBJECT_KEY_TO_LABEL[key] || key;
    const quest = studyQuestsBySubject.get(label);
    const alreadyComplete = completedStudySubjects.has(label);
    let goalMinutes = subjectGoalMinutes[label] || quest?.goal_value || 0;
    let percent = 0;
    if (alreadyComplete) {
      percent = 100;
      if (!subjectGoalMinutes[label] && quest?.goal_value) {
        subjectGoalMinutes[label] = quest.goal_value;
      }
    } else if (quest && goalMinutes > 0) {
      const progressSeconds = quest.progress_seconds ?? ((quest.progress_value || 0) * 60);
      percent = Math.min(100, Math.round((progressSeconds / (goalMinutes * 60)) * 100));
      subjectGoalMinutes[label] = goalMinutes;
    }

    const filled = row.querySelector('[data-role="progress-filled"]');
    if (filled) {
      filled.style.width = `${percent}%`;
    }

    const bar = row.querySelector('.subject-progress__bar');
    if (bar) {
      bar.setAttribute('aria-valuenow', `${percent}`);
    }

    const subjectNameEl = row.querySelector('[data-role="subject-name"]');
    if (subjectNameEl) {
      subjectNameEl.textContent = label;
    }

    const goalEl = row.querySelector('[data-role="subject-goal"]');
    if (goalEl) {
      if (percent >= 100) {
        goalEl.textContent = '목표 완료';
      } else if (goalMinutes) {
        goalEl.textContent = `${goalMinutes}분 목표`;
      } else {
        goalEl.textContent = '목표 없음';
      }
    }

    const button = row.querySelector('[data-subject-trigger]');
    const isComplete = percent >= 100;
    if (button) {
      button.classList.toggle('subject-progress__mode--disabled', isComplete);
      if (isComplete) {
        button.setAttribute('aria-disabled', 'true');
      } else {
        button.removeAttribute('aria-disabled');
      }
      button.title = isComplete ? '오늘 목표를 이미 달성했습니다.' : '현재 모드: 시계';
    }
    row.dataset.state = isComplete ? 'complete' : 'active';
    if (isComplete && !alreadyComplete) {
      completedStudySubjects.add(label);
      completionStateChanged = true;
    } else if (!isComplete && alreadyComplete) {
      completedStudySubjects.delete(label);
      completionStateChanged = true;
    }
  });
  if (completionStateChanged) {
    persistCompletedSubjects();
  }
}

function getCurrentDayKey() {
  return dayFormatter.format(new Date());
}

function getCompletedStorageKey(dayKey = activeDayKey) {
  return `study_completed_${dayKey}`;
}

function persistCompletedSubjects() {
  try {
    localStorage.setItem(getCompletedStorageKey(), JSON.stringify(Array.from(completedStudySubjects)));
  } catch (error) {
    console.warn('Failed to persist completed subjects', error);
  }
}

function hydrateCompletedSubjects() {
  activeDayKey = getCurrentDayKey();
  completedStudySubjects.clear();
  try {
    const raw = localStorage.getItem(getCompletedStorageKey());
    if (raw) {
      const parsed = JSON.parse(raw);
      if (Array.isArray(parsed)) {
        parsed.forEach(label => completedStudySubjects.add(label));
      }
    }
  } catch (error) {
    console.warn('Failed to hydrate completed subjects', error);
  }
}

function clearDailyCompletionState() {
  completedStudySubjects.clear();
  Object.keys(subjectGoalMinutes).forEach(key => delete subjectGoalMinutes[key]);
}

function removeCompletionStorageFor(dayKey) {
  if (!dayKey) return;
  try {
    localStorage.removeItem(getCompletedStorageKey(dayKey));
  } catch (error) {
    console.warn('Failed to remove completion cache', error);
  }
}


if (document.readyState === 'loading') {
  window.addEventListener('DOMContentLoaded', initApp, { once: true });
} else {
  initApp();
}
export { state };
