export function renderQuestList(quests){
  const el = document.getElementById('quest-list');
  el.innerHTML = '';
  quests.forEach(q => {
    const card = document.createElement('div');
    card.className = 'quest-card';
    card.innerHTML = `
      <div>
        <div class="title">${q.title}</div>
        <div class="meta">${q.subject} · 목표 ${q.goal_value}분</div>
      </div>
      <div class="meta">${q.status}</div>
    `;
    el.appendChild(card);
  });
}
