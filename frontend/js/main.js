import { api } from './api.js';
import { renderQuestList, hardResetQuestTimer } from './quest.js';
import { initTimerControls, hardResetTimers } from './timer.js';

const state = {
  userId: 'u1',
  quests: [],
};

export async function loadQuests() {
  state.quests = await api.get(`/quests?user_id=${state.userId}`);
  renderQuestList(state.quests);
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

window.addEventListener('DOMContentLoaded', async () => {
  await loadQuests();
  initTimerControls({ userId: state.userId });
  const resetBtn = document.getElementById('reset-all');
  if (resetBtn) resetBtn.addEventListener('click', handleReset);
  window.addEventListener('quest-sync', async () => {
    try {
      await loadQuests();
    } catch (error) {
      console.error(error);
    }
  });
});

export { state };

