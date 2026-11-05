/** A same-origin write, with a fresh double-submit token. Runs in the browser. */
export async function csrfFetch(
  path: string,
  init: RequestInit,
): Promise<Response> {
  const { header, token } = (await (
    await fetch("/api/csrf", { cache: "no-store" })
  ).json()) as {
    header: string;
    token: string;
  };
  return fetch(path, {
    ...init,
    headers: { ...init.headers, [header]: token },
  });
}
