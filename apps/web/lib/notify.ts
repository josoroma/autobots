// PRD-Studio SE-05: "Tell me when a run waits for me", stored in this browser only.
const KEY = "autobots.notify";
export const NOTIFY_CHANGED = "autobots:notify-changed";

export function notifyChosen(): boolean {
  try {
    return window.localStorage.getItem(KEY) === "on";
  } catch {
    return false;
  }
}

export function chooseNotify(on: boolean): void {
  try {
    if (on) window.localStorage.setItem(KEY, "on");
    else window.localStorage.removeItem(KEY);
  } catch {
    // Unwritable storage: the setting can't be kept, so it stays off.
  }
  window.dispatchEvent(new Event(NOTIFY_CHANGED));
}

export function notificationsSupported(): boolean {
  return typeof window !== "undefined" && "Notification" in window;
}
