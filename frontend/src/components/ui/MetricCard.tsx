import type { ReactNode } from 'react';
import { Card, HighlightCard } from './Card';
import { KnowMoreButton } from './KnowMoreButton';

type MetricCardProps = {
  title: string;
  number: ReactNode;
  unit?: string;
  subtitle?: string;
  knowMoreId?: string;
  highlight?: boolean;
};

/**
 * One metric, one number. The dashboard's primary unit of information.
 *
 * Rules from the Frontend Design Brief:
 * - Every number has a unit.
 * - Every number has a "Know more →" trigger that explains its origin.
 * - The "headline" metric (typically Payback CI) uses HighlightCard.
 */
export function MetricCard({
  title,
  number,
  unit,
  subtitle,
  knowMoreId,
  highlight = false,
}: MetricCardProps) {
  const Wrapper = highlight ? HighlightCard : Card;

  return (
    <Wrapper>
      <div className="flex items-start justify-between gap-3">
        <h3 className="font-display text-base font-semibold uppercase tracking-wide text-ink">
          {title}
        </h3>
        {knowMoreId && <KnowMoreButton id={knowMoreId} />}
      </div>
      <div className="mt-4 flex items-baseline gap-2">
        <span className="font-display text-5xl font-semibold leading-none">{number}</span>
        {unit && <span className="font-display text-xl font-semibold text-ink-soft">{unit}</span>}
      </div>
      {subtitle && <p className="mt-3 text-sm text-ink-soft">{subtitle}</p>}
    </Wrapper>
  );
}
