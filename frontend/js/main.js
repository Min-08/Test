import { api } from './api.js';
import { renderQuestList } from './quest.js';
import { initTimerControls, resetAll as resetTimerUI } from './timer.js';

const state = {
  userId: 'u1',
  quests: [],
};

export async function loadQuests() {
  state.quests = await api.get(`/quests?user_id=${state.userId}`);
  renderQuestList(state.quests);
}

window.addEventListener('DOMContentLoaded', async () => {
  await loadQuests();
  initTimerControls({ userId: state.userId });
  const resetBtn = document.getElementById('reset-all');
  if (resetBtn) {
    resetBtn.addEventListener('click', async () => {
      if(!confirm('정말 전체 초기화하시겠어요? 모든 데이터가 삭제됩니다.')) return;
      try {
        await api.post('/admin/reset_all?seed=true');
        await loadQuests();
        await resetTimerUI();
        alert('초기화 완료');
      } catch (e) { console.error(e); alert('초기화 실패'); }
    });
  }
  // refresh quest list when timer creates/updates a quest
  window.addEventListener('quest-sync', async () => { try { await loadQuests(); } catch(e){} });
});

export { state };
