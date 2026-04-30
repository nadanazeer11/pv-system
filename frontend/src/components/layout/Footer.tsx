export function Footer() {
  return (
    <footer className="mt-24 border-t-2 border-border bg-surface">
      <div className="mx-auto max-w-[1200px] px-6 py-10 text-sm text-ink-soft">
        <p className="font-display text-base font-semibold text-ink">
          Bachelor's thesis project — for educational use.
        </p>
        <p className="mt-2 max-w-3xl">
          Estimates are model outputs and not a quote. Real installations depend on roof
          structure, shading, electrical capacity and local regulation. This tool is intended
          to support an informed conversation with a licensed Egyptian PV installer, not to
          replace one.
        </p>
        <div className="mt-6 flex flex-wrap gap-x-8 gap-y-2">
          <a
            className="underline hover:text-ink"
            href="https://github.com/nadanazeer11/pv-system"
            target="_blank"
            rel="noreferrer"
          >
            Source &amp; methodology
          </a>
          <a
            className="underline hover:text-ink"
            href="https://re.jrc.ec.europa.eu/pvg_tools/en/"
            target="_blank"
            rel="noreferrer"
          >
            PVGIS (irradiance source)
          </a>
          <a
            className="underline hover:text-ink"
            href="https://egyptera.org/"
            target="_blank"
            rel="noreferrer"
          >
            EgyptERA (tariff source)
          </a>
        </div>
      </div>
    </footer>
  );
}
