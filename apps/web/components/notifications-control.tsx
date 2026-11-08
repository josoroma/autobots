"use client";

import { useState, useSyncExternalStore } from "react";

import { Choice } from "@/components/ui/field";
import {
  chooseNotify,
  notificationsSupported,
  notifyChosen,
} from "@/lib/notify";

const subscribe = () => () => undefined;

type Permission = "granted" | "denied" | "default" | "unsupported";

function permission(): Permission {
  return notificationsSupported() ? Notification.permission : "unsupported";
}

const PERMISSION_TEXT: Record<Permission, string> = {
  granted: "This browser allows the app's notifications.",
  denied:
    "This browser blocks the app's notifications, so none is shown. Allow them in the browser's settings for this site.",
  default: "The browser asks for permission when you turn this on.",
  unsupported: "This browser can't show notifications.",
};

// PRD-Studio SE-05. Stored in this browser; the notifier in the app shell reads it.
export function NotificationsControl() {
  const mounted = useSyncExternalStore(
    subscribe,
    () => true,
    () => false,
  );
  const [on, setOn] = useState<boolean | null>(null);
  const [allowed, setAllowed] = useState<Permission | null>(null);
  const checked = on ?? (mounted ? notifyChosen() : false);
  const state = allowed ?? (mounted ? permission() : "default");

  async function toggle(next: boolean): Promise<void> {
    setOn(next);
    if (
      next &&
      notificationsSupported() &&
      Notification.permission === "default"
    )
      setAllowed(await Notification.requestPermission());
    chooseNotify(next);
  }

  return (
    <fieldset className="min-w-0 space-y-2.5">
      <legend className="mb-1 text-sm font-semibold">Runs</legend>
      <label className="border-border has-[:checked]:border-primary/65 flex max-w-lg cursor-pointer items-center gap-2 rounded-lg border px-3 py-2 text-[13px] has-[:disabled]:cursor-default">
        <Choice
          type="checkbox"
          checked={checked}
          disabled={!mounted || state === "unsupported"}
          onChange={(event) => void toggle(event.target.checked)}
        />
        Tell me when a run waits for me
      </label>
      <p
        data-field="notify-permission"
        className="text-muted-foreground max-w-lg text-[12.5px] leading-relaxed"
      >
        {PERMISSION_TEXT[state]}
      </p>
      <p className="text-muted-foreground max-w-lg text-[12.5px] leading-relaxed">
        A notification appears when a run starts waiting for your approval or
        input, only while the app is open in this browser. Nothing is sent off
        this Mac.
      </p>
    </fieldset>
  );
}
