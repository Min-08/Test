const sessionState = {
  userId: 'u1',
};

export function getUserId() {
  return sessionState.userId;
}

export function setUserId(nextId) {
  if (typeof nextId === 'string' && nextId.trim()) {
    sessionState.userId = nextId;
  }
}

export function getSession() {
  return sessionState;
}
