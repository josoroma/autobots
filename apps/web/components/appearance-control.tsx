"use client";

import { useTheme } from "next-themes";
import { useSyncExternalStore } from "react";
import { Choice } from "@/components/ui/field";
import { cn } from "@/lib/utils";

const subscribe = () => () => undefined;

// Fixed swatches, so each card previews its own theme whatever the page is in. Decorative: the label names
// it. Each value is the exact luma.css declaration for that theme (background, sidebar, border or muted,
// sidebar-primary), repeated because a light preview can't inherit :root inside a dark page.
const PREVIEWS = {
  dark: {
    surface: "bg-[oklch(0.145_0_0)]",
    side: "bg-[oklch(0.205_0_0)]",
    bar: "bg-[oklch(0.269_0_0)]",
    accent: "bg-[oklch(0.623_0.214_259.815)]",
  },
  light: {
    surface: "bg-[oklch(1_0_0)]",
    side: "bg-[oklch(0.985_0_0)]",
    bar: "bg-[oklch(0.922_0_0)]",
    accent: "bg-[oklch(0.546_0.245_262.881)]",
  },
} as const;

function ThemePreview({ theme }: { theme: keyof typeof PREVIEWS }) {
  const tone = PREVIEWS[theme];
  return (
    <span
      aria-hidden="true"
      className={cn(
        "border-border mb-1.5 grid h-[78px] grid-cols-[28%_1fr] overflow-hidden rounded-[7px] border",
        tone.surface,
      )}
    >
      <span className={cn("flex flex-col gap-1 px-1.5 py-[7px]", tone.side)}>
        <i className={cn("block h-[5px] w-[70%] rounded-full", tone.accent)} />
        <i className={cn("block h-[5px] rounded-full", tone.bar)} />
        <i className={cn("block h-[5px] rounded-full", tone.bar)} />
      </span>
      <span className="flex flex-col gap-[5px] p-[9px]">
        <i className={cn("block h-[5px] w-[60%] rounded-full", tone.bar)} />
        <i className={cn("block h-[5px] rounded-full", tone.bar)} />
        <i className={cn("block h-[5px] w-[80%] rounded-full", tone.bar)} />
      </span>
    </span>
  );
}

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
    <fieldset className="min-w-0">
      <legend className="mb-2.5 text-sm font-semibold">Theme</legend>
      <div className="grid max-w-md grid-cols-2 gap-2.5">
        {(
          [
            { value: "dark", label: "Dark" },
            { value: "light", label: "Light" },
          ] as const
        ).map(({ value, label }) => (
          <label
            key={value}
            className="border-border has-[:checked]:border-primary/65 has-[:checked]:ring-primary/15 block min-w-0 cursor-pointer rounded-[10px] border p-1.5 text-[13px] has-[:checked]:ring-[3px] has-[:disabled]:cursor-default"
          >
            <ThemePreview theme={value} />
            <span className="flex items-center gap-2 px-1 pb-0.5">
              <Choice
                type="radio"
                name="appearance"
                value={value}
                checked={current === value}
                disabled={!mounted}
                onChange={() => setTheme(value)}
              />
              {label}
            </span>
          </label>
        ))}
      </div>
    </fieldset>
  );
}
