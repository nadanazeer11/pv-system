import type { ReactNode } from 'react';

type SectionProps = {
  title: string;
  subtitle?: string;
  children: ReactNode;
  id?: string;
};

export function Section({ title, subtitle, children, id }: SectionProps) {
  return (
    <section id={id} className="mx-auto max-w-[1200px] px-6 py-12">
      <div className="mb-8 flex flex-wrap items-end justify-between gap-4">
        <div>
          <span className="inline-block rounded-card border-2 border-border bg-accent px-3 py-1 font-display text-sm font-semibold text-ink">
            {title}
          </span>
          {subtitle && <p className="mt-3 max-w-2xl text-base text-ink-soft">{subtitle}</p>}
        </div>
      </div>
      {children}
    </section>
  );
}
