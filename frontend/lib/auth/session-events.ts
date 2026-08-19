type SessionExpiredListener = () => void;

let listener: SessionExpiredListener | null = null;

export function onSessionExpired(fn: SessionExpiredListener): () => void {
  listener = fn;
  return () => {
    if (listener === fn) {
      listener = null;
    }
  };
}

export function notifySessionExpired(): void {
  listener?.();
}
