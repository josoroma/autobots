import type { ApprovalReviewDetail } from "@autobots/api-client";

/** PRD-Studio GH-06: each file's diff against the base head this approval binds. */
export function ReviewDiffs({
  approvalId,
  detail,
}: {
  approvalId: string;
  detail: ApprovalReviewDetail;
}) {
  return (
    <section
      data-field="review-detail"
      aria-labelledby={`review-${approvalId}`}
      className="space-y-2"
    >
      <h3 id={`review-${approvalId}`} className="text-sm font-semibold">
        Changes against {detail.base_branch} at{" "}
        <code className="text-[12.5px]">{detail.base_sha.slice(0, 12)}</code>
      </h3>
      {detail.files.map((file) => (
        <div
          key={file.path}
          data-diff={file.path}
          className="rounded-lg border"
        >
          <p className="flex gap-2 border-b px-3.5 py-2 text-[13px]">
            <code className="min-w-0 flex-1 break-all">{file.path}</code>
            <span className="text-muted-foreground">{file.change}</span>
          </p>
          <pre
            tabIndex={0}
            role="region"
            aria-label={`Diff of ${file.path}`}
            className="max-h-80 overflow-auto p-3.5 font-mono text-[12.5px] leading-relaxed whitespace-pre"
          >
            {file.diff === "" ? "No change." : file.diff}
          </pre>
        </div>
      ))}
    </section>
  );
}
