import { useCallback, useEffect, useRef } from 'react';
import { getExplainer } from '@/content/explainers';

type KnowMoreModalProps = {
  id: string;
  open: boolean;
  onClose: () => void;
};

/**
 * Reusable modal that reads its content from the explainers registry.
 *
 * Accessibility:
 * - role="dialog" + aria-modal so screen readers announce it as a modal.
 * - Focus is moved to the close button on open and restored on close.
 * - Escape key closes the modal; clicking the backdrop closes it.
 * - Focus is trapped within the dialog while open (Tab cycles inside).
 */
export function KnowMoreModal({ id, open, onClose }: KnowMoreModalProps) {
  const explainer = getExplainer(id);
  const dialogRef = useRef<HTMLDivElement>(null);
  const previousFocus = useRef<HTMLElement | null>(null);
  const closeButtonRef = useRef<HTMLButtonElement>(null);

  const handleKeyDown = useCallback(
    (event: KeyboardEvent) => {
      if (!open) return;
      if (event.key === 'Escape') {
        event.preventDefault();
        onClose();
        return;
      }
      if (event.key === 'Tab' && dialogRef.current) {
        const focusables = dialogRef.current.querySelectorAll<HTMLElement>(
          'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])',
        );
        if (focusables.length === 0) return;
        const first = focusables[0];
        const last = focusables[focusables.length - 1];
        if (event.shiftKey && document.activeElement === first) {
          event.preventDefault();
          last.focus();
        } else if (!event.shiftKey && document.activeElement === last) {
          event.preventDefault();
          first.focus();
        }
      }
    },
    [open, onClose],
  );

  useEffect(() => {
    if (!open) return;
    previousFocus.current = document.activeElement as HTMLElement | null;
    closeButtonRef.current?.focus();
    document.addEventListener('keydown', handleKeyDown);
    document.body.style.overflow = 'hidden';
    return () => {
      document.removeEventListener('keydown', handleKeyDown);
      document.body.style.overflow = '';
      previousFocus.current?.focus();
    };
  }, [open, handleKeyDown]);

  if (!open) return null;

  if (!explainer) {
    return (
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="know-more-missing-title"
        className="fixed inset-0 z-50 flex items-center justify-center bg-ink/60 p-4"
        onClick={onClose}
      >
        <div
          ref={dialogRef}
          className="w-full max-w-md rounded-card-lg border-2 border-border bg-bg p-6"
          onClick={(event) => event.stopPropagation()}
        >
          <h2 id="know-more-missing-title" className="text-2xl font-semibold">
            Explainer not found
          </h2>
          <p className="mt-2 text-ink-soft">
            No registry entry found for id <code>{id}</code>.
          </p>
          <button
            ref={closeButtonRef}
            type="button"
            onClick={onClose}
            className="mt-4 inline-flex items-center justify-center rounded-card border-2 border-border bg-ink px-4 py-2 font-display text-sm font-semibold text-bg"
          >
            Close
          </button>
        </div>
      </div>
    );
  }

  const titleId = `know-more-title-${explainer.id}`;

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby={titleId}
      className="fixed inset-0 z-50 flex items-center justify-center bg-ink/60 p-4"
      onClick={onClose}
    >
      <div
        ref={dialogRef}
        className="max-h-[90vh] w-full max-w-2xl overflow-y-auto rounded-card-lg border-2 border-border bg-bg p-8 shadow-card"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="flex items-start justify-between gap-4">
          <h2 id={titleId} className="font-display text-2xl font-semibold leading-tight">
            {explainer.title}
          </h2>
          <button
            ref={closeButtonRef}
            type="button"
            onClick={onClose}
            aria-label="Close"
            className="shrink-0 rounded-card border-2 border-border bg-ink px-3 py-1 font-display text-sm font-semibold text-bg hover:bg-ink-soft"
          >
            ✕
          </button>
        </div>

        <section className="mt-6 space-y-3">
          {explainer.plainEnglish.map((para, idx) => (
            <p key={idx} className="text-base leading-relaxed text-ink-soft">
              {para}
            </p>
          ))}
        </section>

        {explainer.math && explainer.math.length > 0 && (
          <section className="mt-6">
            <h3 className="font-display text-lg font-semibold">The math</h3>
            <pre className="mt-2 overflow-x-auto rounded-card border-2 border-border bg-surface p-4 font-mono text-sm">
              {explainer.math.join('\n')}
            </pre>
          </section>
        )}

        {explainer.variables && explainer.variables.length > 0 && (
          <section className="mt-6">
            <h3 className="font-display text-lg font-semibold">Values used</h3>
            <ul className="mt-2 space-y-1 text-sm">
              {explainer.variables.map((v) => (
                <li key={v.label} className="flex justify-between gap-4">
                  <span className="text-ink-soft">{v.label}</span>
                  <span className="font-medium">{v.value}</span>
                </li>
              ))}
            </ul>
          </section>
        )}

        <section className="mt-6">
          <h3 className="font-display text-lg font-semibold">Sources</h3>
          <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-ink-soft">
            {explainer.sources.map((source, idx) => (
              <li key={idx}>
                {source.href ? (
                  <a className="underline" href={source.href} target="_blank" rel="noreferrer">
                    {source.label}
                  </a>
                ) : (
                  source.label
                )}
              </li>
            ))}
          </ul>
        </section>
      </div>
    </div>
  );
}
