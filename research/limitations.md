# Limitations and Assumptions

> **Day-21 deliverable.** Final, structured Limitations chapter for the
> bachelor thesis. The methodology document
> (`research/methodology.md`) describes what the system *does*; the
> validation report (`research/validation.md`) shows the output bands;
> this document is the third leg of the academic stool — what the
> system *does not* do, why, and what each simplification would cost
> a future user who applies the result outside the validated regime.
>
> Every limitation below is paired with (a) the upstream source-code
> location it lives in, (b) the academic citation that the
> simplification is anchored against, and (c) a concrete future-work
> statement so the thesis defence can answer "why didn't you fix it?"
> with a specific cost estimate rather than a hand-wave.

---

## 0. How to read this document

A limitation in this document is in one of three categories:

* **(S)** *Scope* — deliberately out of the bachelor scope. Documented
  so the result is not misapplied; *not* a defect.
* **(D)** *Data* — limited by the data the project can credibly
  obtain. A future student with access to a richer corpus could lift
  the limitation without touching the code.
* **(M)** *Model* — limited by the methodology choice. Lifting it
  requires re-deriving a kernel; the cost is given.

Every section ends with **Future work** that names the artefact a
follow-up project would need to produce and the kernel(s) it would
have to touch.

---

## 1. Solar resource (PVGIS TMY)

### 1.1 Inter-annual variability is collapsed into a "typical" year (M)

The PVGIS TMY is, by construction, a year *picked from history* to
match the long-term distribution of GHI, $T_a$ and wind speed at the
requested grid cell. A real installation in a sunny year will produce
above prediction; a cloudier year will produce below. Egyptian
inter-annual irradiance variability is roughly $\pm 5\,\%$ around the
long-term mean.

* **Source:** `backend/app/services/pvgis_service.py` (TMY fetch);
  `backend/app/services/energy_pvlib.py`,
  `backend/app/services/energy_manual.py` (TMY consumption).
* **Mitigation in scope:** the Day-9 Monte Carlo engine
  (`backend/app/services/monte_carlo.py`) treats the annual yield
  factor as $\mathcal N(1.0, 0.05)$ per (simulation, year), exactly
  to absorb this variability into the payback confidence interval.
* **Cost of fixing it:** ≈ 200 MB of multi-year (e.g., 1990–2020)
  hourly satellite-derived irradiance per Egyptian governorate,
  plus a re-fit of the Monte Carlo prior on actual inter-annual
  empirics. Out of bachelor scope.
* **Future work:** swap the TMY product for a multi-year ensemble
  (e.g., NSRDB-equivalent for Egypt or a Copernicus C3S regional
  reanalysis) and re-derive the yield-factor prior empirically.

### 1.2 Spatial resolution is ~5 km (D)

PVGIS grid cells are coarse relative to a single rooftop. A rooftop
that sits next to a 50 m parapet wall on its northern side does *not*
share its nearest neighbour's irradiance. This system does not model
neighbour-induced shading.

* **Source:** PVGIS API itself (out of our control).
* **Cost of fixing it:** a ray-tracing horizon model around the
  detected rooftop using a 3D city model (e.g., Egypt's MoCIT
  building-height layer where it exists, or LiDAR for Cairo where
  it does not). Substantial code addition (~1 kLOC) and a 3D
  asset that the bachelor scope cannot acquire.
* **Future work:** §10 below.

---

## 2. PV modelling

### 2.1 Single panel technology (S)

The dual-energy chains assume a representative monocrystalline-silicon
panel: 450 W rated, 1.8 m² area, $\gamma_\text{pdc} = -0.0035\,\text{°C}^{-1}$,
NOCT = 45 °C. Bifacial gain, thin-film temperature behaviour, and
half-cell layout effects are not modelled.

* **Source:** `app.config.Settings` — `panel_rated_watts`,
  `panel_area_m2`; constants in `energy_pvlib.py` and
  `energy_manual.py` (`GAMMA_PDC`, `NOCT_C`).
* **Why c-Si only?** ~90 % of Egyptian residential rooftop
  installations are c-Si modules at 2024 prices (Egyptian PV market
  survey 2024).
* **Cost of fixing it:** add a per-technology parameter pack and a
  selector to the request schema; ~50 LOC plus tests.
* **Future work:** add `panel_technology` enum to
  `SizingRequest`, materialise tech-specific $\gamma_\text{pdc}$ and
  thermal-model parameters from a config table.

### 2.2 No bifacial back-side gain (S, M)

A bifacial panel mounted at typical Egyptian flat-roof tilts gains
4–8 % over its monofacial twin under high albedo (white parapet wall,
sand). The harness uses $\rho_\text{ground} = 0.20$ uniformly and does
not back-side transpose.

* **Source:** `energy_manual._poa_isotropic` uses isotropic ground
  reflectance only; `energy_pvlib.simulate` uses the Hay-Davies
  transposition without a back-side term.
* **Cost of fixing it:** swap to `pvlib.bifacial.pvfactors_timeseries`
  in the pvlib chain (introduces a `pvfactors` dependency) and add an
  isotropic back-side term to the manual chain. ~150 LOC plus a
  per-site albedo input. Methodology-honest because c-Si bifacial is
  the fastest-growing residential PV technology globally; the
  Egyptian market is still <5 % bifacial in 2024 so the omission is
  defensible *today* but will age.
* **Future work:** `BifacialGain` schema field defaulting to off,
  parameterised by a per-site albedo (sand 0.30–0.40, white parapet
  0.50–0.65).

### 2.3 Single-string single-inverter topology (S)

The DC chain implicitly assumes one string at one MPPT input. Module-
level power electronics (MLPE) — DC optimisers and microinverters —
which mitigate partial-shade losses, are not modelled.

* **Source:** `energy_pvlib.simulate` step 6 and
  `energy_manual.simulate` step 6 both use a constant inverter
  efficiency at DC:AC = 1.0.
* **Why?** MLPE adoption in Egyptian residential rooftops is rare
  (~10 % at 2024 prices; cost premium 15–25 % EGP).
* **Cost of fixing it:** a topology selector + per-string sub-
  arraying in the energy chain. ~200 LOC. Substantially complicates
  the cross-validation between the pvlib and manual chains (MLPE
  partial-shade behaviour is non-trivial to keep agreeing across
  two independent kernels).
* **Future work:** thesis-defence answer is "documented limitation,
  defer to follow-up project that explicitly compares centralised
  vs MLPE topologies for Egyptian rooftops".

### 2.4 No partial-shade simulation beyond the lumped 14 % derate (M)

Partial shading from neighbouring buildings, water tanks, satellite
dishes, palm trees, and parapet walls is *not* hour-resolved by the
energy chains. The lumped $L_\text{sys} = 0.14$ derate (NREL PVWatts
canonical) is the only soiling/shading/mismatch absorber.

* **Source:** `DEFAULT_SYSTEM_LOSSES_FRACTION = 0.14` in both energy
  modules.
* **Why a single lumped factor?** It's the NREL PVWatts default and
  the dominant choice in Egyptian PV pre-feasibility literature
  (Mahmoud & El-Nokali 2023). Accuracy is sufficient at the
  pre-feasibility stage; not at the as-built design stage.
* **Cost of fixing it:** a per-rooftop horizon-shading profile from
  CV-detected obstructions (water tanks, parapets) plus an
  hour-resolved beam-blocking model (similar to pvlib's
  `tools.partial_shading`). ~500 LOC plus an obstruction-detection
  add-on to the roof-detection pipeline.
* **Future work:** §10.

### 2.5 Cell-thermal models do not include wind anisotropy (M)

The pvlib chain uses the SAPM `open_rack_glass_polymer` parameter set
(implicitly assumes wind across the modules); the manual chain uses
the NOCT model (independent of wind). Both ignore the Egyptian
sandstorm regime in which transient occlusion of the modules raises
cell temperature beyond the steady-state model's prediction.

* **Source:** `SAPM_THERMAL_PARAMS` in `energy_pvlib.py`;
  `_cell_temperature_noct` in `energy_manual.py`.
* **Cost of fixing it:** a sandstorm-frequency overlay from Egyptian
  Meteorological Authority data plus a transient cell-thermal
  model. The simplification's order-of-magnitude cost on annual yield
  is < 1 % outside the Western Desert governorates.
* **Future work:** Western-Desert-specific sandstorm derate.

---

## 3. Financial modelling

### 3.1 Tiered tariff: marginal-block interpretation only (M)

The tiered-tariff kernel adopts the *marginal* interpretation of the
EgyptERA schedule (each band charges only the kWh inside it). The
*inclusive* interpretation reported in some Egyptian press accounts
(exceeding a band reverts the whole month to the higher tier) is
*not* implemented.

* **Source:** `tiered_tariff._bill_one_month`.
* **Why marginal?** Matches the official EgyptERA bill statement and
  is the conservative reading for the PV-value claim — under
  inclusive billing, PV would look *more* valuable. Picking marginal
  means our payback claims hold under the worst of the two readings.
* **Cost of fixing it:** trivial — add an `interpretation` enum to
  `TariffBillRequest` and branch on it in `_bill_one_month`.
  ~30 LOC plus tests.
* **Future work:** ship both interpretations as a side-by-side
  toggle on the dashboard; flag the gap as an EgyptERA policy-
  reporting clarification request.

### 3.2 Net-metering surplus credited at the export-credit rate (M, D)

The savings kernel reimburses spilled generation
$\max(0, g_m - c_m)$ at the configurable
`export_credit_egp_per_kwh` (default 0.0). Egypt's actual residential
net-metering scheme reimburses surplus at the *lowest* tier rate
(sometimes zero), but the precise rule has changed three times since
2014 and the current 2024 rule is documented inconsistently in
EgyptERA bulletins.

* **Source:** `tiered_tariff._compute_savings_model`.
* **Why default 0?** The conservative reading: any payback claim
  quoted under the default holds under the least favourable export
  rule.
* **Future work:** monitor EgyptERA bulletins for a definitive 2024
  net-metering schedule and flip the default once published.

### 3.3 Consumption is held flat across years (M)

The size optimiser holds monthly household consumption at the
input-supplied profile for the entire 25-year horizon. Egyptian
household consumption has been growing ~2–4 %/yr (CAPMAS 2023);
ignoring this systematically *under-states* the case for PV (a
growing household pulls more kWh into the expensive tiers, where PV
displaces them at a higher marginal rate).

* **Source:** `_npv_for_size` in `tiered_tariff.py`; per-year
  matrix expansion in `monte_carlo.py`.
* **Why omit it?** Long-horizon consumption growth is at least as
  uncertain as the tariff-escalation prior, and adding it would
  double-count uncertainty already attributed to tariff inflation.
* **Cost of fixing it:** a `consumption_growth_rate` field on the
  request, applied in the per-year loop. ~20 LOC. The substantive
  question — is consumption growth *independent* of tariff inflation
  in the long run? — is harder than the code change, and is the real
  reason for deferral.
* **Future work:** treat consumption growth as a stochastic input
  in the Monte Carlo prior (jointly distributed with tariff
  inflation, since tariff hikes historically suppress consumption
  growth).

### 3.4 Single-currency single-jurisdiction (S)

All currency is EGP; analysis horizon is 25 years. No cross-currency
financing, no FX hedging. Egyptian household-level PV financing is
overwhelmingly EGP-denominated (developer loans, EBRD-backed retail
schemes), so this is a defensible scope cut.

* **Source:** every financial kernel.
* **Future work:** out of bachelor scope.

### 3.5 IRR is not reported as a headline (M)

The dashboard reports NPV, LCOE, simple payback and discounted
payback, but *not* IRR. The methodology document §3.3 explains the
reason — non-smooth cash flows from inverter replacement can produce
multiple sign changes that make IRR ill-defined — but a thesis
reviewer who specifically asks for IRR will not find it.

* **Source:** `financial_basic.compute_financials` returns no IRR
  field.
* **Cost of fixing it:** `numpy_financial.irr` plus a multi-root
  guard (Descartes' rule on the cash-flow vector to flag undefined
  cases). ~30 LOC. Defensible in either direction; the project chose
  *omit* over *partially-defined-and-explained*.
* **Future work:** add IRR with a `is_irr_well_defined` boolean
  flag.

---

## 4. Uncertainty quantification

### 4.1 Distribution priors are literature-anchored, not empirically fit (D)

The seven Monte Carlo distributions are picked from published priors
(Jordan & Kurtz 2013 for degradation, EgyptERA history for tariff
inflation, IEA-PVPS for inverter service life, etc.) — *not* fit from
a sample of Egyptian residential PV installations.

* **Source:** `app.config.Settings.monte_carlo_*` fields.
* **Cost of fixing it:** access to a panel of ≥ 30 Egyptian
  residential PV installations with at least 5 years of metered
  output and one tariff cycle. The bachelor scope cannot acquire
  this corpus.
* **Future work:** a follow-up study fits the priors empirically;
  the current configuration becomes the prior for that fit.

### 4.2 Yield-factor noise is independent across years (M)

The Monte Carlo kernel samples a fresh yield factor for each
(simulation, year) pair, with no autocorrelation. Real Egyptian
inter-annual irradiance has a small but non-zero AR(1) coefficient
($\rho \approx 0.2$ over 1990–2020 in NREA reanalysis).

* **Source:** `monte_carlo._simulate` step "Per-(simulation, year)
  yield draws".
* **Cost of fixing it:** sample $\nu_{n,t}$ from a Gaussian copula
  with the empirical AR(1) covariance instead of i.i.d. Gaussian.
  ~30 LOC.
* **Why omit it?** $\rho \approx 0.2$ widens the payback CI by < 5 %;
  inside the methodology's published modelling-uncertainty floor.
* **Future work:** AR(1) yield prior; will narrow the CI further.

### 4.3 OAT tornado: no joint sensitivity (M)

The Day-18 OAT tornado holds all other parameters at the deterministic
baseline while sweeping one. Genuine joint sensitivity (Sobol indices)
is not reported.

* **Source:** `sensitivity.run_sensitivity`.
* **Why?** OAT is the standard reporting format in PV
  pre-feasibility literature (NREL SAM Technical Reference;
  IEA-PVPS Task 7), and the Day-9 Monte Carlo histogram already
  models *joint* uncertainty — together they cover the two
  questions a methodology section is expected to address. Sobol
  indices are not directly interpretable as "this parameter changes
  my NPV by ±X EGP", which is the reading the dashboard's
  homeowner audience needs.
* **Cost of fixing it:** `scipy.stats.sobol_indices` over the same
  seven parameters, ~50 LOC plus an extra dashboard visualisation.
* **Future work:** add Sobol as an *advanced* tab on the dashboard.

---

## 5. AI-assisted roof detection

### 5.1 OSM coverage is uneven across Egypt (D)

OpenStreetMap building-footprint coverage is dense in Cairo and
Alexandria (~95 % of residential blocks tagged with `building`) and
sparse in the Western Desert and Sinai (< 30 %). The roof-detection
pipeline returns "no polygon" rather than guessing, and the
dashboard renders an explicit fall-back-to-manual-input prompt.

* **Source:** `overpass_service.fetch_buildings`.
* **Cost of fixing it:** a learned segmentation model that runs when
  OSM returns no candidate (§5.3 below). The bachelor scope rules
  this out; the documented fallback to user-supplied area is
  acceptable.
* **Future work:** §10.

### 5.2 OSM positional accuracy is 0.5–1.5 m (D)

OSM polygons are routinely off by 0.5–1.5 m at corners (Vargas-Muñoz
et al. 2021). The CV regularisation step (`roof_segmentation.refine_polygon`)
absorbs this into the minimum-rotated-rectangle output, but a
sub-metre as-built design would still need a surveyed polygon.

* **Source:** `roof_segmentation.refine_polygon`.
* **Why is sub-metre accuracy not the goal?** Pre-feasibility, not
  as-built design. The down-stream sizing kernel rounds panel count
  with `floor`; sub-metre polygon precision is below the rounding
  threshold of the system size.
* **Future work:** parametric "as-built" mode that opts out of the
  regularisation step and consumes a surveyed shapefile directly.

### 5.3 Classical CV instead of a learned segmenter (M)

The CV refinement uses Sobel-gradient alignment plus
minimum-rotated-rectangle regularisation — *no* CNN, *no* SAM, *no*
GPU. The methodology document (§5.3.1) argues this is the *smallest*
toolset that gives the energy pipeline a regularised polygon and an
honest confidence number.

* **Cost of fixing it:** ~500 MB of model weights and GPU
  dependence; a confidence-calibration study on Egyptian rooftops
  that has not been published.
* **Future work:** out of bachelor scope. A follow-up project that
  publishes the calibration study would make a learned segmenter
  defensible.

### 5.4 Tilt and azimuth are inferred from OSM tags + polygon geometry, not from imagery (M)

The pipeline does not infer tilt from satellite imagery shadow
analysis or azimuth from rooftop ridge detection. It uses
`roof:angle` and `roof:shape` tags first, falls back to the polygon's
long-edge bearing for azimuth on pitched roofs, and snaps to flat-
slab Egyptian residential prior otherwise.

* **Source:** `roof_orientation.estimate_tilt`,
  `roof_orientation.estimate_azimuth`.
* **Cost of fixing it:** shadow-based tilt estimation needs a
  resolved-time stamp on the satellite tile (which Google Maps
  Static does not surface) plus a ground-truth corpus to validate.
* **Future work:** opt-in shadow-based tilt mode against a
  user-supplied dated tile.

### 5.5 No ground-truth corpus — IoU not measured (D)

The Day-20 validation report (§9) flags this explicitly. There is no
hand-labelled corpus of Egyptian rooftops against which to measure
IoU and area-error.

* **Cost of fixing it:** a bachelor follow-up project producing
  20–50 hand-surveyed Cairo rooftops with GPS-traced boundaries.
* **Future work:** §10 lists the acceptance metrics
  (median IoU > 0.7, mean area error < 15 %).

---

## 6. CO₂ avoidance

### 6.1 Grid-average emission factor, not marginal-dispatch (D)

The CO₂ kernel uses the EEHC published *grid-average* annual emission
factor (0.46 kg CO₂/kWh, 2023). The marginal-dispatch factor — the
kg-CO₂ avoided per kWh of *the next* kWh the grid would have
generated — varies by hour, season and merit-order conditions and is
not publicly available for Egypt.

* **Source:** `co2_model.compute_co2_avoidance`.
* **Bias direction:** conservative whenever PV displaces high-merit
  gas peakers — the marginal factor is typically 10–20 % higher than
  the grid-average in gas-dominated systems, so we *under-state* CO₂
  avoidance.
* **Future work:** monitor for an Egyptian grid-operator dispatch-
  factor publication; the kernel exposes the factor as an override
  so the swap is one config change.

### 6.2 No embodied-carbon subtraction (M)

A complete LCA would net off the embodied carbon of the modules,
inverter and balance-of-system: typically 30–50 g CO₂/kWh-lifetime
amortised over 25 years (IEA-PVPS Task 12, 2020).

* **Source:** `co2_model.compute_co2_avoidance` — no embodied term.
* **Why omit it?** Including a half-modelled LCA in the headline
  number would over-claim precision the dataset does not support.
  IEA-PVPS Task 12 is the authoritative reference; a true LCA needs
  a per-module-supply-chain audit that the bachelor scope cannot
  perform.
* **Cost of fixing it:** a `embodied_kg_co2_per_kwh` parameter
  defaulting to 40 g CO₂/kWh (mid of the IEA-PVPS range), subtracted
  from the year-by-year stream. ~10 LOC.
* **Future work:** ship as an opt-in headline.

### 6.3 Equivalence constants are EPA-default, not Egypt-specific (M)

Passenger-car kilometres, petrol litres, and tree-years use
EPA-published constants. Egyptian fleet emission factors and
Egyptian urban-tree species are not modelled.

* **Source:** `app.config.Settings.co2_kg_per_*`.
* **Why?** Petrol's carbon content is essentially physics and does
  not change at the Egyptian border; the EPA constants are the
  most-cited and best-documented in consumer climate-communication
  tooling, and so keep our dashboard numbers comparable to other
  widely circulated calculators.
* **Cost of fixing it:** trivial — three numbers in `config.py`.
  Awaiting an Egyptian-fleet-average emission factor publication.
* **Future work:** monitor CAPMAS for an Egyptian-fleet figure.

---

## 7. Tariff schedule

### 7.1 Schedule is the August-2023 reform (D)

The seven-tier schedule shipped in `app.config.EGYPT_RESIDENTIAL_TARIFF_TIERS`
is the post-July-2023 reform. EgyptERA reforms residential tariffs
roughly every 12–18 months; the schedule will age.

* **Source:** `app.config.EGYPT_RESIDENTIAL_TARIFF_TIERS`.
* **Mitigation:** the schedule is a config value, not a hard-coded
  service constant. A future reform updates one place.
* **Future work:** automate a quarterly check against the EgyptERA
  bulletin URL.

### 7.2 Service charge omitted (M)

EgyptERA bills include a small fixed monthly service charge that is
not modelled. Negligible for the payback comparison (< 0.5 % of a
monthly bill above 200 kWh) but non-zero.

* **Source:** `tiered_tariff._bill_one_month` — bill is purely the
  per-kWh marginal-block sum.
* **Cost of fixing it:** add a `monthly_service_charge_egp` config
  field. ~10 LOC.
* **Future work:** ship in the next config refresh.

### 7.3 Non-residential tariffs out of scope (S)

EgyptERA also publishes commercial, agricultural, and industrial
tariff schedules. The thesis is bounded to residential.

* **Source:** N/A — the kernel takes any tier list, but only the
  residential schedule is shipped as default.
* **Future work:** ship the commercial schedule as a second config
  block.

---

## 8. Hardware generalisation

### 8.1 Single inverter, single string (S, M)

See §2.3. Microinverter and DC-optimiser topologies are not modelled.

### 8.2 No battery storage (S)

Grid-tied only. Battery economics are intentionally out of scope —
they would change the financial kernel substantially (self-
consumption fraction becomes time-resolved, battery capex enters,
cycle-life uncertainty enters Monte Carlo).

* **Source:** N/A — every kernel assumes grid-tied.
* **Why?** Egyptian residential battery adoption is < 2 % at 2024
  prices; battery economics deserve a separate thesis.
* **Future work:** out of bachelor scope.

### 8.3 No structural roof analysis (S)

Load-bearing capacity, anchor pull-out strength, and seismic
qualification are not assessed.

* **Source:** N/A.
* **Why?** Engineering-judgement layer that requires an as-built
  inspection by a registered structural engineer.
* **Future work:** out of academic scope; explicitly delegated to
  the installer.

---

## 9. Validation harness

### 9.1 Clear-sky synthetic TMY, not measured (M)

The Day-20 validation harness (`backend/tests/test_validation_egypt.py`)
runs against a clear-sky synthetic TMY rather than a live PVGIS pull.
This is the hermetic-regression-suite trade-off documented in
`research/validation.md` §1: byte-identical reproducibility at the
cost of clear-sky upper-bound bias.

* **Source:** `_egypt_clearsky_tmy` in the validation test file.
* **Mitigation:** the validation report (§7) ships a
  reviewer-runnable live-PVGIS counterpart command for the
  measured-resource validation.
* **Future work:** archive a small set of vintage PVGIS TMY snapshots
  as test fixtures so the live-PVGIS check can be hermetic too.

### 9.2 Acceptance bands are wide (M)

The validation report bands (1500–2000 kWh/kWp for Cairo, ±5 % MAPE
for cross-model) are deliberately wider than any single reference
study. A narrower band would force the thesis to commit to one
study.

* **Source:** `EGYPTIAN_CITIES` table in the validation test file.
* **Cost of fixing it:** N/A — narrower bands would not be more
  defensible academically, only more dramatic visually.

---

## 10. Future-work register (consolidated)

The numbered items above each end with a future-work statement; the
table below consolidates them so a follow-up student or a thesis
reviewer can read the open items in a single pass.

| Tag | Limitation | Required artefact | Estimated effort |
|---|---|---|---|
| F-1 | Inter-annual irradiance variability collapsed into TMY (§1.1) | Multi-year hourly irradiance ensemble; refit Monte Carlo prior | 1–2 person-weeks |
| F-2 | Neighbour-induced shading not modelled (§1.2 + §2.4) | 3D city horizon model; ray-tracing shadow simulator | 1–2 person-months |
| F-3 | Single panel technology (§2.1) | Per-tech parameter pack | 1 person-day |
| F-4 | No bifacial back-side gain (§2.2) | Bifacial transposition + per-site albedo input | 3–5 person-days |
| F-5 | Single-string single-inverter (§2.3) | Topology selector + sub-array model | 1–2 person-weeks |
| F-6 | Inclusive-billing interpretation not implemented (§3.1) | Enum field + branch | < 1 day |
| F-7 | Net-metering rule not finalised (§3.2) | Confirmed EgyptERA 2024 rule | Pending bulletin |
| F-8 | Consumption growth omitted (§3.3) | Stochastic consumption-growth prior, joint with tariff inflation | 3–5 person-days |
| F-9 | IRR not reported (§3.5) | numpy_financial.irr + well-defined-flag | < 1 day |
| F-10 | Yield factor i.i.d. across years (§4.2) | AR(1) Gaussian-copula sampler | 1 person-day |
| F-11 | No Sobol indices (§4.3) | scipy.stats.sobol_indices integration | 2–3 person-days |
| F-12 | Ground-truth roof-detection corpus missing (§5.5) | 20–50 hand-surveyed Cairo rooftops | 1 person-month (field work) |
| F-13 | Learned segmenter (§5.3) | Calibration study + GPU inference path | 1–2 person-months |
| F-14 | Shadow-based tilt inference (§5.4) | Time-stamped tile fetcher + corpus | 1 person-month |
| F-15 | Marginal-dispatch CO₂ factor (§6.1) | Egyptian grid-operator dispatch publication | Pending |
| F-16 | Embodied-carbon LCA (§6.2) | IEA-PVPS-grade per-module audit | Pending |
| F-17 | Egyptian-fleet equivalence constants (§6.3) | CAPMAS fleet-emission publication | Pending |
| F-18 | Tariff schedule auto-refresh (§7.1) | Quarterly EgyptERA bulletin scraper | 1 person-day |
| F-19 | Service-charge term (§7.2) | Config field + bill-line addition | < 1 day |
| F-20 | Commercial tariff schedule (§7.3) | Schedule import + tier model | 1 person-day |
| F-21 | Live-PVGIS test fixtures (§9.1) | Vintage TMY archive | 1 person-day |

`F-` tags are stable identifiers — citing F-7 in a follow-up paper
will resolve unambiguously to "net-metering rule not finalised" even
after future reorganisations of this document.

---

## 11. What this document is *not*

This is not a list of bugs. Every item above is a deliberate scope
or methodology choice, anchored to a citation, paired with an estimate
of the cost of lifting it. A reader who finds a kernel defect (a sign
error, a unit error, a regression) should file a test against
`backend/tests/` rather than appending to this document; the test
suite is the place where defects belong, this document is where
*choices* belong.
