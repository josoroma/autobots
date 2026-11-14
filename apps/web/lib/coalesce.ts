/**
 * One read at a time, with at most one more queued behind it (WRUN-04). A call made while a read is
 * in flight is answered by the next read, which starts once the current one settles, so every caller
 * sees a reply read after it asked, and calls made meanwhile share that next read. Runs in the
 * browser and under `node --test`.
 */
export function coalesce<T>(read: () => Promise<T>): () => Promise<T> {
  let running: Promise<T> | null = null;
  let queued: Promise<T> | null = null;
  const begin = (): Promise<T> => {
    queued = null;
    const flight: Promise<T> = read().finally(() => {
      if (running === flight) running = null;
    });
    running = flight;
    return flight;
  };
  return () => {
    // The queued read is checked first: between the running read settling and the queued one
    // starting, a new call joins the queued one rather than starting a third.
    if (queued !== null) return queued;
    if (running === null) return begin();
    queued = running.then(begin, begin);
    return queued;
  };
}
