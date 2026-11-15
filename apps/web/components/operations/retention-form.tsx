import type { RetentionSettings } from "@autobots/api-client";
import { Trash2 } from "lucide-react";
import { useState } from "react";

import { OperationsBox } from "@/components/operations/operations-box";
import { useRetentionSave } from "@/components/operations/use-retention-save";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/field";
import { retentionRequest } from "@/lib/retention";

const RETENTION_ERROR = "retention-days-error";

// The windows as typed, for the read they were typed against. A newer read, such as after a save or
// Check again, shows its own windows again.
interface Typed {
  read: number;
  run: string | null;
  receipt: string | null;
}

function WindowField({
  label,
  value,
  invalid,
  onChange,
}: {
  label: string;
  value: string;
  invalid: boolean;
  onChange: (value: string) => void;
}) {
  return (
    <label className="text-muted-foreground flex flex-wrap items-center justify-between gap-x-4 gap-y-1.5 text-ui">
      <span>{label}</span>
      <Input
        className="w-28"
        inputMode="numeric"
        value={value}
        aria-invalid={invalid || undefined}
        aria-describedby={invalid ? RETENTION_ERROR : undefined}
        onChange={(event) => onChange(event.target.value)}
      />
    </label>
  );
}

/**
 * The retention windows (WSYS-01), shown against the status read `read` counts. Nothing malformed
 * or out of range is sent, since a misread window would feed an irreversible pass.
 */
export function RetentionForm({
  retention,
  read,
  onSaved,
}: {
  retention: RetentionSettings;
  read: number;
  onSaved: () => void;
}) {
  const [typed, setTyped] = useState<Typed>({
    read: 0,
    run: null,
    receipt: null,
  });
  const [invalid, setInvalid] = useState({ run: false, receipt: false });
  const saving = useRetentionSave(onSaved);
  const own = typed.read === read ? typed : { run: null, receipt: null };
  const runDays = own.run ?? retention.run_days?.toString() ?? "";
  const receiptDays = own.receipt ?? retention.receipt_days?.toString() ?? "";

  function request(): RetentionSettings | null {
    const next = retentionRequest(runDays, receiptDays);
    setInvalid(next.invalid);
    return next.body;
  }

  return (
    <OperationsBox icon={Trash2} heading="Retention">
      <p className="text-muted-foreground text-ui leading-relaxed">
        Empty keeps everything. Expiring a finished run removes its checkpoints,
        working files and artifact bytes. Its record, activity and operation
        receipts stay, and a run with an unresolved effect is never touched.
      </p>
      <div className="space-y-2.5">
        <WindowField
          label="Run content, days after finishing"
          value={runDays}
          invalid={invalid.run}
          onChange={(value) => {
            setTyped({ ...own, read, run: value });
            setInvalid((now) => ({ ...now, run: false }));
          }}
        />
        <WindowField
          label="Retry keys, days"
          value={receiptDays}
          invalid={invalid.receipt}
          onChange={(value) => {
            setTyped({ ...own, read, receipt: value });
            setInvalid((now) => ({ ...now, receipt: false }));
          }}
        />
        {invalid.run || invalid.receipt ? (
          <p id={RETENTION_ERROR} role="alert" className="text-sm">
            Use whole days from 1 to 36,500, or leave a window empty. Nothing
            was saved.
          </p>
        ) : null}
      </div>
      <div className="flex flex-wrap items-center gap-3">
        <Button
          size="sm"
          disabled={saving.pending}
          onClick={() => void saving.save(request)}
        >
          Save retention
        </Button>
        {saving.message === null ? null : (
          <p role="status" className="text-sm">
            {saving.message}
          </p>
        )}
      </div>
    </OperationsBox>
  );
}
