import type { ButtonHTMLAttributes, ReactNode } from 'react';

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  children: ReactNode;
};

function classes(...parts: Array<string | false | null | undefined>) {
  return parts.filter(Boolean).join(' ');
}

const base =
  'inline-flex items-center justify-center rounded-card border-2 border-border px-6 py-3 font-display text-base font-semibold transition-all disabled:cursor-not-allowed disabled:opacity-60';

export function PrimaryButton({ children, className, ...rest }: ButtonProps) {
  return (
    <button
      {...rest}
      className={classes(
        base,
        'bg-ink text-bg shadow-card hover:shadow-card-hover hover:-translate-y-[2px]',
        className,
      )}
    >
      {children}
    </button>
  );
}

export function AccentButton({ children, className, ...rest }: ButtonProps) {
  return (
    <button
      {...rest}
      className={classes(
        base,
        'bg-accent text-ink shadow-card hover:shadow-card-hover hover:-translate-y-[2px]',
        className,
      )}
    >
      {children}
    </button>
  );
}
