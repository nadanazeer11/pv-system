import { useState } from 'react';
import { KnowMoreModal } from './KnowMoreModal';

type KnowMoreButtonProps = {
  id: string;
  label?: string;
};

/**
 * Pill-shaped trigger that opens the corresponding KnowMoreModal entry.
 * Owns its own open/close state so consumers do not need to manage it
 * themselves — the registry id is the only required prop.
 */
export function KnowMoreButton({ id, label = 'Know more' }: KnowMoreButtonProps) {
  const [open, setOpen] = useState(false);

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="inline-flex items-center gap-1 rounded-full border-2 border-border bg-bg px-3 py-1 font-display text-xs font-semibold text-ink hover:bg-accent-soft"
        aria-haspopup="dialog"
        aria-expanded={open}
      >
        {label} <span aria-hidden="true">→</span>
      </button>
      <KnowMoreModal id={id} open={open} onClose={() => setOpen(false)} />
    </>
  );
}
