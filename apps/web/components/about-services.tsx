"use client";

import { useState } from "react";

import { Button } from "@/components/ui/button";
import { CardTitle } from "@/components/ui/card";
import { Dialog } from "@/components/ui/dialog";

export function AboutServices({ className }: { className?: string }) {
  const [open, setOpen] = useState(false);
  return (
    <>
      <Button
        variant="outline"
        size="sm"
        className={className}
        onClick={() => setOpen(true)}
      >
        About local services
      </Button>
      <Dialog
        open={open}
        onClose={() => setOpen(false)}
        aria-labelledby="about-services-title"
        className="space-y-3 p-6"
      >
        <CardTitle id="about-services-title" size="display">
          About local services
        </CardTitle>
        <p className="text-sm leading-relaxed">
          The interface, API and workers run natively on this Mac. Requests
          never own long-running work, so closing this page does not stop a run.
        </p>
        <form method="dialog" className="flex justify-end pt-2">
          <Button type="submit" variant="outline">
            Close
          </Button>
        </form>
      </Dialog>
    </>
  );
}
