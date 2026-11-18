/**
 * Opens one surface and waits until it shows what it's captured for, in the theme it's walked in,
 * with its modal dialog open when it has one. A surface that never gets there is reported by name
 * with the reason, rather than ending the walk (TWEB-03).
 */
import { stripVTControlCharacters } from "node:util";

import { expect, type Page, type Request } from "@playwright/test";

import type { Surface, SurfaceDialog, SurfaceIds, Theme } from "./surfaces.ts";

const IDLE_TIMEOUT = 60_000;

/** Opens the dialog, unless the path already has, and waits until it shows. */
async function openDialog(page: Page, dialog: SurfaceDialog): Promise<void> {
  await dialog.open?.(page);
  await expect(page.getByRole("dialog", { name: dialog.name })).toBeVisible();
}

/**
 * Opens `surface` on `page` and waits for it. Returns null once it's ready, or why it never was.
 * A surface with its own arrangement holds or refuses requests on purpose, so only the others
 * must reach network idle. A dialog opens after that, once the page can respond to it.
 */
export async function settle(
  page: Page,
  surface: Surface,
  ids: SurfaceIds,
  theme: Theme,
): Promise<string | null> {
  // What is still in flight, so a page that never settles names its request.
  const pending = new Set<Request>();
  let requested = 0;
  page.on("request", (request) => {
    requested += 1;
    pending.add(request);
  });
  page.on("requestfinished", (request) => pending.delete(request));
  page.on("requestfailed", (request) => pending.delete(request));
  try {
    if (surface.arrange) await surface.arrange(page);
    await page.goto(surface.path(ids));
    await surface.ready(page);
    if (!surface.arrange) {
      await page
        .waitForLoadState("networkidle", { timeout: IDLE_TIMEOUT })
        .catch(async (error: Error) => {
          const connection = await page
            .locator("[data-connection]")
            .first()
            .getAttribute("data-connection")
            .catch(() => null);
          const open = [...pending]
            .map((request) => `${request.method()} ${request.url()}`)
            .join(", ");
          throw new Error(
            `never settled after ${requested} requests, connection ${connection}, open: ${open}. ${error.message}`,
          );
        });
    }
    if (surface.dialog) await openDialog(page, surface.dialog);
    await expect(page.locator("html")).toHaveClass(new RegExp(theme));
    return null;
  } catch (error) {
    return stripVTControlCharacters(
      error instanceof Error ? error.message : String(error),
    );
  }
}
