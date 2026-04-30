export function Header() {
  return (
    <header className="border-b-2 border-border bg-bg">
      <div className="mx-auto flex max-w-[1200px] items-center justify-between px-6 py-5">
        <a href="/" className="flex items-center gap-3 font-display text-xl font-semibold">
          <span
            aria-hidden="true"
            className="inline-flex h-8 w-8 items-center justify-center rounded-card bg-accent text-ink"
          >
            ☀
          </span>
          PV Estimator
        </a>
        <nav className="flex items-center gap-4 text-sm">
          <a
            href="https://github.com/nadanazeer11/pv-system"
            target="_blank"
            rel="noreferrer"
            className="rounded-card border-2 border-border bg-bg px-4 py-2 font-display font-semibold hover:bg-accent-soft"
          >
            GitHub
          </a>
        </nav>
      </div>
    </header>
  );
}
