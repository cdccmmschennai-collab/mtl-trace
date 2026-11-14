/**
 * Saving a generated file. In the desktop tool (pywebview window) the browser's download mechanism is not
 * available, so the desktop shell exposes `save_file`, which shows the Windows "Save as" dialog and writes the
 * file. In a normal browser the link's own download is used.
 */

interface DesktopApi {
  save_file: (url: string, fileName: string) => Promise<string | null>;
}

declare global {
  interface Window {
    pywebview?: { api?: Partial<DesktopApi> };
  }
}

const desktop = (): DesktopApi | null => {
  const api = window.pywebview?.api;
  return api?.save_file ? (api as DesktopApi) : null;
};

/**
 * Click handler for a download link. Resolves to a message for the user, or null when nothing was saved
 * (dialog cancelled). Outside the desktop tool the link downloads normally.
 */
export async function saveFromLink(e: { preventDefault: () => void }, url: string, fileName: string): Promise<string | null> {
  const d = desktop();
  if (!d) return `Downloaded · ${fileName}`;
  e.preventDefault();
  const saved = await d.save_file(url, fileName);
  return saved ? `Saved · ${saved}` : null;
}
