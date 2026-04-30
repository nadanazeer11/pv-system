import type { HTMLAttributes, ReactNode } from 'react';

type CardProps = HTMLAttributes<HTMLDivElement> & {
  children: ReactNode;
};

function classes(...parts: Array<string | false | null | undefined>) {
  return parts.filter(Boolean).join(' ');
}

export function Card({ children, className, ...rest }: CardProps) {
  return (
    <div
      {...rest}
      className={classes(
        'rounded-card border-2 border-border bg-bg p-6 shadow-card transition-shadow hover:shadow-card-hover',
        className,
      )}
    >
      {children}
    </div>
  );
}

export function HighlightCard({ children, className, ...rest }: CardProps) {
  return (
    <div
      {...rest}
      className={classes(
        'rounded-card border-2 border-border bg-accent p-6 shadow-card transition-shadow hover:shadow-card-hover',
        className,
      )}
    >
      {children}
    </div>
  );
}
