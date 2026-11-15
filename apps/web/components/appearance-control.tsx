"use client";

import { useState } from "react";

import { useThemeChoice } from "@/components/theme-provider";
import { Choice } from "@/components/ui/field";
import {
  applyPreference,
  PRESENTATION,
  readPreference,
  type Preference,
  type PreferenceValue,
  type ThemeChoiceName,
} from "@/lib/preferences";
import { PREVIEWS, type PreviewTheme } from "@/lib/theme-preview";
import { useMounted } from "@/lib/use-mounted";
import { cn } from "@/lib/utils";

// Decorative: the label names the theme each pane previews.
function Pane({
  theme,
  className,
}: {
  theme: PreviewTheme;
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

function ThemePreview({ theme }: { theme: ThemeChoiceName }) {
  return (
    <span
      aria-hidden="true"
      className="border-border mb-1.5 grid h-[78px] overflow-hidden rounded-inset border"
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

// The choices lib/preferences.ts allows, in the order Settings offers them.
const THEMES: readonly { value: ThemeChoiceName; label: string }[] = [
  { value: "system", label: "System" },
  { value: "light", label: "Light" },
  { value: "dark", label: "Dark" },
];

const CARD =
  "border-border has-checked:border-primary/65 has-checked:ring-primary/15 block min-w-0 cursor-pointer rounded-lg border p-1.5 text-ui has-checked:ring-3 has-disabled:cursor-default";
const OPTION =
  "border-border has-checked:border-primary/65 flex min-w-0 cursor-pointer items-center gap-2 rounded-lg border px-3 py-2 text-ui has-disabled:cursor-default";

// PRD-Studio SE-03: presentation only, stored in this browser through lib/preferences.ts, which the
// before-paint script also reads. Each change sets the same attribute on the root element.
function usePreference<P extends Preference>(
  preference: P,
  mounted: boolean,
): [PreferenceValue<P>, (value: PreferenceValue<P>) => void] {
  const [chosen, setChosen] = useState<PreferenceValue<P> | null>(null);
  const root = () => document.documentElement;
  const storage = () => window.localStorage;
  const value =
    chosen ??
    (mounted
      ? readPreference(preference, storage, root())
      : PRESENTATION[preference].fallback);
  return [
    value,
    (next) => {
      applyPreference(preference, next, storage, root());
      setChosen(next);
    },
  ];
}

/** Density and Motion: one radio per value of a preference, fallback first. */
function PreferenceRadioGroup<P extends "density" | "motion">({
  preference,
  legend,
  labels,
  value,
  disabled,
  onChange,
}: {
  preference: P;
  legend: string;
  labels: Readonly<Record<PreferenceValue<P>, string>>;
  value: PreferenceValue<P>;
  disabled: boolean;
  onChange: (value: PreferenceValue<P>) => void;
}) {
  const { fallback, attribute } = PRESENTATION[preference];
  const values: readonly PreferenceValue<P>[] = [fallback, attribute];
  return (
    <fieldset className="min-w-0">
      <legend className="mb-2.5 text-sm font-semibold">{legend}</legend>
      <div className="grid max-w-lg grid-cols-1 gap-2.5 sm:grid-cols-2">
        {values.map((option) => (
          <label key={option} className={OPTION}>
            <Choice
              type="radio"
              name={preference}
              value={option}
              checked={value === option}
              disabled={disabled}
              onChange={() => onChange(option)}
            />
            {labels[option]}
          </label>
        ))}
      </div>
    </fieldset>
  );
}

// The checked state depends on the browser, so it renders only after mount, and no hydration warning is hidden.
export function AppearanceControl() {
  const { theme, setTheme } = useThemeChoice();
  const mounted = useMounted();
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
        <p className="text-muted-foreground mt-2 text-meta">
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
          className="font-document mt-2.5 max-w-lg text-lead leading-relaxed"
        >
          A run&apos;s goal and its evidence read like this.
        </p>
      </fieldset>

      <PreferenceRadioGroup
        preference="density"
        legend="Density"
        labels={{ comfortable: "Comfortable", compact: "Compact" }}
        value={density}
        disabled={!mounted}
        onChange={setDensity}
      />

      <PreferenceRadioGroup
        preference="motion"
        legend="Motion"
        labels={{ system: "Follow this Mac", reduce: "Always reduce motion" }}
        value={motion}
        disabled={!mounted}
        onChange={setMotion}
      />
    </div>
  );
}
