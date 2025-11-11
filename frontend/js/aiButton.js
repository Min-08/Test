import { api } from './api.js';

const btn = document.getElementById('ai-btn');
const modal = document.getElementById('ai-modal');
const closeBtn = document.getElementById('ai-close');
const sendBtn = document.getElementById('ai-send');
const answerBox = document.getElementById('ai-answer');

btn.addEventListener('click', ()=> { modal.classList.remove('hidden'); answerBox.textContent=''; });
closeBtn.addEventListener('click', ()=> modal.classList.add('hidden'));
sendBtn.addEventListener('click', async () => {
  const text = document.getElementById('ai-question').value.trim();
  const subject = document.getElementById('ai-subject').value;
  if(!text) return;
  try {
    answerBox.textContent = '생각중...';
    const res = await api.post('/ai/chat', { user_id: 'u1', subject, text });
    answerBox.textContent = res.answer || '(응답 없음)';
  } catch (e) { console.error(e); answerBox.textContent = '오류: 응답을 가져오지 못했습니다.'; }
});
