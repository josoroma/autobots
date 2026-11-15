"use client";

import {
  type ComponentProps,
  type ReactNode,
  type RefObject,
  useLayoutEffect,
  useRef,
} from "react";

import { closesDialog, type Spot, spotOf } from "@/lib/dialog-press";
import { cn } from "@/lib/utils";

// DS-03: dialogs use the popover pair over one backdrop. `page` is the Tools page's guide, whose cards
// use the card pair: popover and card share one value in both themes, so on a popover surface the
// cards' edges would vanish. The guide keeps the page surface and its darker backdrop as the one
// documented exception (WTAP-12).
const SURFACES = {
  popover: "bg-popover text-popover-foreground backdrop:bg-black/50",
  page: "bg-background text-foreground backdrop:bg-black/60",
} as const;

const SIZES = { md: "max-w-md", xl: "max-w-xl", "3xl": "max-w-3xl" } as const;

const PLACEMENTS = { center: "m-auto", top: "mx-auto mt-[12vh]" } as const;

function spot(event: {
  target: EventTarget;
  currentTarget: HTMLDialogElement;
  clientX: number;
  clientY: number;
}): Spot {
  return spotOf(
    event.currentTarget.getBoundingClientRect(),
    { x: event.clientX, y: event.clientY },
    event.target === event.currentTarget,
  );
}

/**
 * A modal on the native `<dialog>`, so the page behind it is inert and the browser traps focus
 * (Decision 0026 G3). Escape, a `<form method="dialog">` button and a click outside its box close it
 * (Decision 0026 G2), and `onClose` hears each. A press that began inside never closes it
 * (lib/dialog-press.ts). Focus then returns to `returnFocus()` when given, or
 * else to whatever had it when the dialog opened. Name it with `aria-labelledby` or `aria-label`; with
 * both, the label names it until the element `aria-labelledby` points to exists.
 */
export function Dialog({
  open,
  onClose,
  surface = "popover",
  size = "md",
  placement = "center",
  initialFocus,
  returnFocus,
  className,
  children,
  ...props
}: {
  open: boolean;
  onClose: () => void;
  surface?: keyof typeof SURFACES;
  size?: keyof typeof SIZES;
  placement?: keyof typeof PLACEMENTS;
  /** Takes focus as the dialog opens, instead of its first focusable element. */
  initialFocus?: RefObject<HTMLElement | null>;
  /** Where focus goes once it closes. Null leaves focus where the browser puts it. */
  returnFocus?: () => HTMLElement | null | undefined;
  children: ReactNode;
} & Omit<ComponentProps<"dialog">, "open" | "onClose" | "children">) {
  const dialog = useRef<HTMLDialogElement>(null);
  const opener = useRef<HTMLElement | null>(null);
  const press = useRef<Spot | null>(null);

  useLayoutEffect(() => {
    const element = dialog.current;
    if (element === null) return;
    if (open && !element.open) {
      opener.current =
        document.activeElement instanceof HTMLElement
          ? document.activeElement
          : null;
      element.showModal();
      initialFocus?.current?.focus();
    } else if (!open && element.open) {
      element.close();
    }
  }, [open, initialFocus]);

  function closed(): void {
    const back = returnFocus === undefined ? opener.current : returnFocus();
    opener.current = null;
    onClose();
    if (back?.isConnected) back.focus();
  }

  return (
    <dialog
      ref={dialog}
      onClose={closed}
      onPointerDown={(event) => {
        press.current = spot(event);
      }}
      onClick={(event) => {
        const began = press.current;
        press.current = null;
        if (closesDialog(began, spot(event))) event.currentTarget.close();
      }}
      className={cn(
        "border-border w-[calc(100%-2rem)] rounded-2xl border shadow-lg",
        SURFACES[surface],
        SIZES[size],
        PLACEMENTS[placement],
        className,
      )}
      {...props}
    >
      {children}
    </dialog>
  );
}
