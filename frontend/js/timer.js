import { api } from './api.js';

let ticking = null;
let delta = 0; // seconds since last flush
let lastSent = Date.now();
let format = (s)=> new Date(s*1000).toISOString().substr(11,8);
let userIdRef = null;
let currentSubject = null; // '국어' | '수학' | '영어'

export function initTimerControls({ userId }){
  userIdRef = userId;
  document.getElementById('pause').addEventListener('click', pause);
  document.getElementById('stop').addEventListener('click', stop);
  document.querySelectorAll('.subject-buttons .subject').forEach(btn => {
    btn.addEventListener('click', () => selectSubject(btn.dataset.subject, btn));
  });
}

async function selectSubject(subj, btn){
  // if switching while running, flush accumulated seconds to previous subject
  if (ticking && currentSubject && currentSubject !== subj) {
    await flushWithSubject(currentSubject);
  }
  currentSubject = subj;
  document.querySelectorAll('.subject-buttons .subject').forEach(b => b.classList.toggle('active', b===btn));
  // auto-start if not running
  if (!ticking) start();
  // ensure quest exists immediately and update UI + refresh list
  try {
    const updated = await api.post('/timer/update', {
      user_id: userIdRef,
      subject: currentSubject,
      delta_seconds: 0
    });
    updateProgressUIFromQuest(updated);
    window.dispatchEvent(new CustomEvent('quest-sync'));
  } catch (e) { console.error(e); }
}

function updateProgressUIFromQuest(q){
  const percent = Math.min(100, Math.floor((q.progress_value / q.goal_value) * 100));
  const bar = document.getElementById('progress-bar');
  bar.style.width = percent + '%';
  const label = document.getElementById('current-quest-label');
  label.textContent = `${q.title} · ${percent}%`;
}

function start(){
  if (ticking) return;
  if (!currentSubject) { alert('과목 버튼(국어/수학/영어)을 먼저 선택하세요'); return; }
  ticking = setInterval(async () => {
    delta += 1;
    const elapsed = document.getElementById('elapsed');
    const total = parseTime(elapsed.textContent) + 1;
    elapsed.textContent = format(total);
    if (Date.now() - lastSent >= 5000) {
      await flushCurrent(); lastSent = Date.now();
    }
  }, 1000);
}

function parseTime(hms){
  const [h,m,s] = hms.split(':').map(Number); return h*3600+m*60+s;
}

async function pause(){ if(!ticking) return; clearInterval(ticking); ticking=null; await flushCurrent(); }

async function stop(){
  // reset (초기화): stop ticking, flush current, reset UI and selection
  await pause();
  document.getElementById('elapsed').textContent='00:00:00';
  currentSubject = null;
  document.querySelectorAll('.subject-buttons .subject').forEach(b => b.classList.remove('active'));
  document.getElementById('current-quest-label').textContent = '진행 중인 퀘스트 없음';
  document.getElementById('progress-bar').style.width = '0%';
}

async function flushCurrent(){
  if (delta <= 0) return;
  if(!currentSubject) return;
  try {
    const updated = await api.post('/timer/update', {
      user_id: userIdRef,
      subject: currentSubject,
      delta_seconds: delta
    });
    delta = 0;
    updateProgressUIFromQuest(updated);
    window.dispatchEvent(new CustomEvent('quest-sync'));
    if (updated.status === 'completed') { await stop(); alert('퀘스트 완료!'); }
  } catch (e) { console.error(e); }
}

async function flushWithSubject(subject){
  if (delta <= 0) return;
  try {
    const updated = await api.post('/timer/update', {
      user_id: userIdRef,
      subject,
      delta_seconds: delta
    });
    delta = 0;
    // 업데이트는 이전 과목의 퀘스트에 반영되므로 UI는 다음 주기에서 갱신됨
    // 필요 시 즉시 갱신하려면 updateProgressUIFromQuest(updated) 호출 가능
    window.dispatchEvent(new CustomEvent('quest-sync'));
    return updated;
  } catch (e) { console.error(e); }
}

export async function resetAll(){
  await stop();
}
