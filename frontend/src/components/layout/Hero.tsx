import { AccentButton } from '@/components/ui/Button';

type HeroProps = {
  onCtaClick?: () => void;
};

export function Hero({ onCtaClick }: HeroProps) {
  return (
    <section className="relative overflow-hidden">
      <div className="mx-auto max-w-[1200px] px-6 py-20 md:py-28">
        <div className="grid gap-10 md:grid-cols-[2fr_1fr] md:items-center">
          <div>
            <h1 className="font-display text-5xl font-bold leading-[1.05] tracking-tight md:text-7xl">
              How much can solar save your home in Egypt?
            </h1>
            <p className="mt-6 max-w-2xl text-lg text-ink-soft">
              Enter your roof size — we use real Egyptian weather data, the actual EgyptERA
              tariff structure, and a thousand-scenario uncertainty model to give you a
              confident answer, not a guess.
            </p>
            <div className="mt-8 flex flex-wrap gap-4">
              <AccentButton onClick={onCtaClick} type="button">
                Estimate my roof
              </AccentButton>
            </div>
          </div>
          <div className="relative hidden md:block">
            <div
              aria-hidden="true"
              className="aspect-square rounded-card-lg border-2 border-border bg-accent"
            />
            <div
              aria-hidden="true"
              className="absolute -bottom-8 -left-8 h-32 w-32 rounded-full border-2 border-border bg-bg"
            />
          </div>
        </div>
      </div>
    </section>
  );
}
