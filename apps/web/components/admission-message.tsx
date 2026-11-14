import Link from "next/link";
import type { ReactNode } from "react";

import { ADMISSION_FIX, type AdmissionRefusal } from "@/lib/run-admission";
import type { Outcome } from "@/lib/submit";

/**
 * What a person reads after pressing Run: a status once the run is admitted, and an alert for a
 * refusal or an unknown outcome, which ask for a decision (R-18 step 3). A refusal settings can
 * fix links there.
 */
export function AdmissionMessage({
  outcome,
  fix = null,
  className,
  children,
  ...data
}: {
  outcome: Outcome;
  fix?: AdmissionRefusal | null | undefined;
  className?: string | undefined;
  children: ReactNode;
  "data-outcome"?: string | undefined;
}) {
  const link = fix === null ? undefined : ADMISSION_FIX[fix];
  return (
    <p
      role={outcome === "accepted" ? "status" : "alert"}
      className={className}
      {...data}
    >
      {children}
      {link === undefined ? null : (
        <>
          {" "}
          <Link href="/settings/models" className="font-medium underline">
            {link}
          </Link>
        </>
      )}
    </p>
  );
}
