"use client";

import { useTheme } from "next-themes";
import { useState, useSyncExternalStore } from "react";
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

function Pane({
  theme,
  className,
}: {
  theme: keyof typeof PREVIEWS;
  className?: string;
}) {
  const tone = PREVIEWS[theme];
  return (
    <span className={cn("grid grid-cols-[28%_1fr]", tone.surface, className)}>
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

function ThemePreview({ theme }: { theme: "system" | "light" | "dark" }) {
  return (
    <span
      aria-hidden="true"
      className="border-border mb-1.5 grid h-[78px] overflow-hidden rounded-[7px] border"
    >
      {theme === "system" ? (
        // Half of each, as it follows the OS.
        <span className="grid grid-cols-2">
          <Pane theme="light" />
          <Pane theme="dark" />
        </span>
      ) : (
        <Pane theme={theme} />
      )}
    </span>
  );
}

const THEMES = [
  { value: "system", label: "System" },
  { value: "light", label: "Light" },
  { value: "dark", label: "Dark" },
] as const;

const CARD =
  "border-border has-[:checked]:border-primary/65 has-[:checked]:ring-primary/15 block min-w-0 cursor-pointer rounded-[10px] border p-1.5 text-[13px] has-[:checked]:ring-[3px] has-[:disabled]:cursor-default";
const OPTION =
  "border-border has-[:checked]:border-primary/65 flex min-w-0 cursor-pointer items-center gap-2 rounded-lg border px-3 py-2 text-[13px] has-[:disabled]:cursor-default";

// PRD-Studio SE-03: presentation only, stored in this browser. The page applies a saved choice before
// paint (see app/layout.tsx), and each change here sets the same attribute on the root element.
type Preference = "serif" | "density" | "motion" | "stream";
const DEFAULTS: Record<Preference, string> = {
  serif: "on",
  density: "comfortable",
  motion: "system",
  stream: "on",
};
const ATTRIBUTE_VALUE: Record<Preference, string> = {
  serif: "off",
  density: "compact",
  motion: "reduce",
  stream: "off",
};

function read(preference: Preference): string {
  try {
    const stored = window.localStorage.getItem(`autobots.${preference}`);
    return stored === ATTRIBUTE_VALUE[preference]
      ? stored
      : DEFAULTS[preference];
  } catch {
    // Unreadable storage: whatever the page shows now, which the default or this session's choice set.
    return document.documentElement.dataset[preference] ===
      ATTRIBUTE_VALUE[preference]
      ? ATTRIBUTE_VALUE[preference]
      : DEFAULTS[preference];
  }
}

function apply(preference: Preference, value: string): void {
  const root = document.documentElement;
  if (value === ATTRIBUTE_VALUE[preference]) root.dataset[preference] = value;
  else delete root.dataset[preference];
  try {
    if (value === DEFAULTS[preference])
      window.localStorage.removeItem(`autobots.${preference}`);
    else window.localStorage.setItem(`autobots.${preference}`, value);
  } catch {
    // Storage that can't be written keeps the choice for this page only.
  }
}

function usePreference(
  preference: Preference,
  mounted: boolean,
): [string, (value: string) => void] {
  const [chosen, setChosen] = useState<string | null>(null);
  const value = chosen ?? (mounted ? read(preference) : DEFAULTS[preference]);
  return [
    value,
    (next: string) => {
      apply(preference, next);
      setChosen(next);
    },
  ];
}

// The checked state depends on the browser, so it renders only after mount, and no hydration warning is hidden.
export function AppearanceControl() {
  const { theme, setTheme } = useTheme();
  const mounted = useSyncExternalStore(
    subscribe,
    () => true,
    () => false,
  );
  const current = mounted ? theme : undefined;
  const [serif, setSerif] = usePreference("serif", mounted);
  const [density, setDensity] = usePreference("density", mounted);
  const [motion, setMotion] = usePreference("motion", mounted);
  const [stream, setStream] = usePreference("stream", mounted);
  return (
    <div className="min-w-0 space-y-6">
      <fieldset className="min-w-0">
        <legend className="mb-2.5 text-sm font-semibold">Theme</legend>
        <div className="grid max-w-lg grid-cols-1 gap-2.5 sm:grid-cols-3">
          {THEMES.map(({ value, label }) => (
            <label key={value} className={CARD}>
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
        <p className="text-muted-foreground mt-2 text-[12.5px]">
          System follows this Mac&apos;s setting. Until you choose, the app is
          dark.
        </p>
      </fieldset>

      <fieldset className="min-w-0">
        <legend className="mb-2.5 text-sm font-semibold">Documents</legend>
        <label className={cn(OPTION, "max-w-lg")}>
          <Choice
            type="checkbox"
            checked={serif === "on"}
            disabled={!mounted}
            onChange={(event) => setSerif(event.target.checked ? "on" : "off")}
          />
          Serif for documents
        </label>
        <label className={cn(OPTION, "mt-2.5 max-w-lg")}>
          <Choice
            type="checkbox"
            checked={stream === "on"}
            disabled={!mounted}
            onChange={(event) => setStream(event.target.checked ? "on" : "off")}
          />
          Stream text as it&apos;s written
        </label>
        <p
          data-field="document-sample"
          className="font-document mt-2.5 max-w-lg text-[15px] leading-relaxed"
        >
          A run&apos;s goal and its evidence read like this.
        </p>
      </fieldset>

      <fieldset className="min-w-0">
        <legend className="mb-2.5 text-sm font-semibold">Density</legend>
        <div className="grid max-w-lg grid-cols-1 gap-2.5 sm:grid-cols-2">
          {(
            [
              { value: "comfortable", label: "Comfortable" },
              { value: "compact", label: "Compact" },
            ] as const
          ).map(({ value, label }) => (
            <label key={value} className={OPTION}>
              <Choice
                type="radio"
                name="density"
                value={value}
                checked={density === value}
                disabled={!mounted}
                onChange={() => setDensity(value)}
              />
              {label}
            </label>
          ))}
        </div>
      </fieldset>

      <fieldset className="min-w-0">
        <legend className="mb-2.5 text-sm font-semibold">Motion</legend>
        <div className="grid max-w-lg grid-cols-1 gap-2.5 sm:grid-cols-2">
          {(
            [
              { value: "system", label: "Follow this Mac" },
              { value: "reduce", label: "Always reduce motion" },
            ] as const
          ).map(({ value, label }) => (
            <label key={value} className={OPTION}>
              <Choice
                type="radio"
                name="motion"
                value={value}
                checked={motion === value}
                disabled={!mounted}
                onChange={() => setMotion(value)}
              />
              {label}
            </label>
          ))}
        </div>
      </fieldset>
    </div>
  );
}
