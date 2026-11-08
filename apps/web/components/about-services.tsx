"use client";

import { useRef } from "react";

import { Button } from "@/components/ui/button";

export function AboutServices({ className }: { className?: string }) {
  const dialog = useRef<HTMLDialogElement>(null);
  return (
    <>
      <Button
        variant="outline"
        size="sm"
        className={className}
        onClick={() => dialog.current?.showModal()}
      >
        About local services
      </Button>
      <dialog
        ref={dialog}
        aria-labelledby="about-services-title"
        className="bg-popover text-popover-foreground border-border m-auto w-[calc(100%-2rem)] max-w-md space-y-3 rounded-2xl border p-6 shadow-lg backdrop:bg-black/50"
      >
        <h2
          id="about-services-title"
          className="font-serif text-[22px] leading-tight font-normal tracking-tight"
        >
          About local services
        </h2>
        <p className="text-sm leading-relaxed">
          The interface, API and workers run natively on this Mac. Requests
          never own long-running work, so closing this page does not stop a run.
        </p>
        <form method="dialog" className="flex justify-end pt-2">
          <Button type="submit" variant="outline">
            Close
          </Button>
        </form>
      </dialog>
    </>
  );
}
