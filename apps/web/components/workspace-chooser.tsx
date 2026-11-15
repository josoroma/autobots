"use client";

import { useState } from "react";

import { Select } from "@/components/ui/field";
import { chooseWorkspace } from "@/lib/api/browser";

type Workspace = { id: string; name: string };

// Decision 0023 E3: a member of several workspaces chooses which one the screens act on. Nothing is
// implied: until they choose, it asks. The page reloads so every screen reads the new workspace.
export function WorkspaceChooser({
  workspaces,
  current,
}: {
  workspaces: Workspace[];
  current: string | null;
}) {
  const [failed, setFailed] = useState(false);
  async function choose(id: string): Promise<void> {
    setFailed(false);
    try {
      await chooseWorkspace({ workspace_id: id });
    } catch {
      setFailed(true);
      return;
    }
    window.location.reload();
  }
  return (
    <div data-field="workspace-chooser" className="space-y-1 px-2 pb-3">
      <label
        htmlFor="workspace-choice"
        className={
          current === null
            ? "text-attention text-xs font-medium"
            : "text-muted-foreground text-xs font-medium"
        }
      >
        {current === null ? "Choose a workspace" : "Workspace"}
      </label>
      <Select
        id="workspace-choice"
        value={current ?? ""}
        onChange={(event) => void choose(event.target.value)}
      >
        {current === null ? (
          <option value="" disabled>
            Not chosen
          </option>
        ) : null}
        {workspaces.map((workspace) => (
          <option key={workspace.id} value={workspace.id}>
            {workspace.name}
          </option>
        ))}
      </Select>
      {failed ? (
        <p role="alert" className="text-destructive text-xs">
          {"That workspace couldn't be chosen. Reload and try again."}
        </p>
      ) : null}
    </div>
  );
}
