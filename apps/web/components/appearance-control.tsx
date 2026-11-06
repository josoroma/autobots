"use client";

import { Moon, Sun } from "lucide-react";
import { useTheme } from "next-themes";
import { useSyncExternalStore } from "react";
import { Choice } from "@/components/ui/field";

const subscribe = () => () => undefined;

// The checked state depends on the browser, so it renders only after mount, and no hydration warning is hidden.
export function AppearanceControl() {
  const { resolvedTheme, setTheme } = useTheme();
  const mounted = useSyncExternalStore(
    subscribe,
    () => true,
    () => false,
  );
  const current = mounted ? resolvedTheme : undefined;
  return (
    <fieldset className="space-y-2">
      <legend className="text-sm font-medium">Theme</legend>
      {[
        { value: "dark", label: "Dark", Icon: Moon },
        { value: "light", label: "Light", Icon: Sun },
      ].map(({ value, label, Icon }) => (
        <label key={value} className="flex w-fit items-center gap-2 text-sm">
          <Choice
            type="radio"
            name="appearance"
            value={value}
            checked={current === value}
            disabled={!mounted}
            onChange={() => setTheme(value)}
          />
          <Icon aria-hidden="true" className="size-4" />
          {label}
        </label>
      ))}
    </fieldset>
  );
}
