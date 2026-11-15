/**
 * A filter control that shows what a person typed at once and keeps the URL in step after a pause
 * (XWEB-13, WTAP-15). Its own write coming back doesn't undo later typing, and a change from
 * outside, such as Back or the sidebar's link, replaces what the box shows.
 */
import assert from "node:assert/strict";
import { test } from "node:test";

import {
  followUrl,
  pendingWrite,
  startDraft,
  typed,
  wrote,
} from "../../lib/url-draft.ts";

const trim = (raw: string): string => raw.trim();

test("a draft starts from the URL and writes nothing until it changes", () => {
  const draft = startDraft("calc");
  assert.equal(draft.draft, "calc");
  assert.equal(pendingWrite(draft, trim), null);
  assert.equal(pendingWrite(typed(draft, "calc "), trim), null);
  assert.equal(pendingWrite(typed(draft, "calcu"), trim), "calcu");
});

test("its own write coming back keeps what was typed after it", () => {
  let draft = wrote(typed(startDraft(""), "ful"), "ful");
  assert.equal(pendingWrite(draft, trim), null);
  draft = wrote(typed(draft, "fully"), "fully");
  // The first write's echo arrives while the second is on its way: the box keeps "fully".
  draft = followUrl(draft, "ful");
  assert.equal(draft.draft, "fully");
  assert.equal(pendingWrite(draft, trim), null);
  draft = followUrl(draft, "fully");
  assert.deepEqual(draft, { draft: "fully", followed: "fully", sent: [] });
});

test("a change from outside replaces the box, and typing the old value again writes it", () => {
  let draft = followUrl(wrote(typed(startDraft(""), "calc"), "calc"), "calc");
  draft = followUrl(draft, "");
  assert.deepEqual(draft, startDraft(""));
  draft = typed(draft, "calc");
  assert.equal(pendingWrite(draft, trim), "calc");
});

test("a write normalized on its way out still reads as its own echo", () => {
  let draft = typed(startDraft(""), "fully ");
  const next = pendingWrite(draft, trim);
  assert.equal(next, "fully");
  draft = followUrl(wrote(draft, "fully"), "fully");
  assert.equal(draft.draft, "fully ");
  draft = typed(draft, "fully reported");
  assert.equal(pendingWrite(draft, trim), "fully reported");
});

test("following the URL it already follows changes nothing", () => {
  const draft = typed(startDraft("a"), "ab");
  assert.equal(followUrl(draft, "a"), draft);
});

test("only the newest writes are remembered", () => {
  let draft = startDraft("");
  for (let index = 0; index < 30; index += 1) {
    draft = wrote(draft, `v${index}`);
  }
  assert.ok(draft.sent.length <= 16);
  assert.equal(draft.sent.at(-1), "v29");
});
