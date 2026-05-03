# Methodology

> **Status:** Day-19 deliverable — academic, LaTeX-ready.
> **Pairs with:** `validation.md` (Day 20), `limitations.md` (Day 21),
> `references.bib` (Day 21). All citations below resolve against
> `references.bib`.

This chapter documents the analytical and computational methodology
behind the *AI-Assisted Rooftop Solar Potential Estimation and
Financial Analysis System*. Each section maps one-to-one to a backend
service module under `backend/app/services/`, so an examiner can read
the chapter top-to-bottom and audit each step against the Python
source. Equations are written in LaTeX so the chapter is drop-in
ready for the thesis manuscript without re-typing.

---

## 1. Data Sources

### 1.1 Solar irradiance — PVGIS Typical Meteorological Year

The system consumes hourly typical-meteorological-year (TMY) records
from the European Commission's Photovoltaic Geographical Information
System (PVGIS) v5.2 [@pvgis], retrieved via the public REST endpoint
`https://re.jrc.ec.europa.eu/api/v5_2/`. For every site
$(\varphi, \lambda)$ supplied as latitude / longitude in decimal
degrees, PVGIS returns 8 760 hourly tuples
$\{(\text{GHI}_h, \text{DNI}_h, \text{DHI}_h, T_{\text{air},h},
v_{\text{wind},h})\}_{h=1}^{8760}$ in W·m⁻², °C, and m·s⁻¹
respectively. The TMY series is constructed by PVGIS's typical-month
selection algorithm, applied to ERA-5 reanalysis aggregated over the
2005–2020 period at $\sim$5 km grid resolution.

A TMY is, by construction, a *typical* climatic year — not a forecast
of any specific calendar year. A single PV simulation against a TMY
therefore captures the *expected* generation under climatologically
representative weather. Year-to-year weather variability is restored
explicitly in §6 via the Monte Carlo `annual_yield_factor`
distribution.

### 1.2 Roof geometry — OpenStreetMap + Google Maps Static

Building footprints come from the OpenStreetMap Overpass API
[@osm-overpass]. For a query point $(\varphi_0, \lambda_0)$ the
client retrieves every closed `way` tagged `building=*` whose
centroid lies within the configured search radius
$r_{\text{search}} = 50\,\mathrm{m}$ (Egypt-tuned default; bounded
above at $500\,\mathrm{m}$ to protect the public Overpass instance).
Satellite raster tiles for the same coordinate come from the Google
Maps Static API at zoom 20 with `scale=2`, giving an effective ground
resolution of $\sim$0.14 m·pixel⁻¹ at Cairo's latitude — sufficient
for roof-edge gradient extraction (§5).

### 1.3 Egypt-specific operating constants

| Symbol | Description | Value | Source |
|---|---|---|---|
| $\eta_{\text{inv}}$ | Inverter efficiency (constant) | 0.96 | Modern grid-tied c-Si default; IRENA [@irena2023] |
| $f_{\text{util}}$ | Roof utilisation factor | 0.70 | Egyptian rooftop PV pre-feasibility convention; Mahmoud & El-Nokali [@mahmoud2023] |
| $\beta_{\text{def}}$ | Default tilt | $26°$ | Cairo latitude optimum |
| $A_{\text{def}}$ | Default azimuth | $180°$ (south) | Northern-hemisphere optimum |
| $\eta_{\text{soil}}$ | Soiling loss range | 2 – 8 % | Egyptian PV literature; site-dependent |
| $\varepsilon_{\text{grid}}$ | Grid emission factor | $0.46\,\mathrm{kg\,CO_2 / kWh}$ | EEHC Annual Report 2022/2023 [@eehc_emissions] |
| $C_{\text{kW}}$ | Installed cost | $35\,000\,\mathrm{EGP/kW}$ | Egyptian solar market 2024 |
| $r_{\text{disc}}$ | Real discount rate | 0.04 | Standard project finance |
| $i_{\text{tar}}$ | Tariff escalation (mean) | 0.08 yr⁻¹ | EgyptERA decade trend [@egyptera_tariff] |
| $d$ | Module degradation rate | 0.005 yr⁻¹ | NREL median for mono-Si [@jordan2013] |
| $f_{\text{O\&M}}$ | Annual O&M as fraction of capex | 0.01 | IRENA residential rooftop benchmark [@irena2023] |

Every constant in this table is exposed as a Pydantic-validated
override on the corresponding endpoint, so a methodology-aware caller
can substitute a site-specific value without touching the source.

---

## 2. PV Modelling

### 2.1 System sizing

The sizing kernel converts a roof area $A_{\text{roof}}$ in $\mathrm{m^2}$
into a discrete panel count $N$ and a nameplate DC capacity
$P_{\text{sys}}$ in kW:

$$
A_{\text{usable}} = f_{\text{util}} \cdot A_{\text{roof}}, \qquad
N = \left\lfloor \frac{A_{\text{usable}}}{A_{\text{panel}}} \right\rfloor,
\qquad
P_{\text{sys}} = \frac{N \cdot P_{\text{panel}}}{1000} \;[\mathrm{kW}].
$$

Three design choices warrant explicit justification:

1. **Floor, not round.** A fractional panel is physically meaningless;
rounding *down* is the conservative, installer-realistic choice that
prevents an upward bias from propagating through every downstream
financial metric.
2. **Lumped utilisation factor.** The factor $f_{\text{util}}=0.70$
absorbs edge setbacks (Egyptian fire and maintenance codes), inter-row
walkways for cleaning (a relevant loss in Cairo's high-soiling
environment), inter-row shading spacing for tilted mounts at $\beta=26°$,
and roof-mounted obstructions (water tanks, satellite dishes,
parapets, HVAC condensers) without explicit geometric modelling. The
factor is the central value reported by Egyptian rooftop PV
pre-feasibility studies [@mahmoud2023].
3. **Hardware defaults reflect the 2024 Egyptian residential market.**
$P_{\text{panel}} = 450\,\mathrm{W}$ on $A_{\text{panel}} = 1.8\,\mathrm{m^2}$
is the dominant module configuration; the kernel echoes the
assumptions in the response so the JSON itself is self-auditing.

### 2.2 Energy generation — pvlib model (industry-standard reference)

The reference energy chain is implemented with `pvlib` Python
[@pvlib], using the individual building blocks rather than the
high-level `ModelChain` so each step is explicit and traceable in
this chapter:

1. **Solar geometry.**
   $\theta_z, \gamma_s = \mathrm{NREL\,SPA}(\varphi, \lambda, t)$
   via `pvlib.solarposition.get_solarposition`.
2. **Plane-of-array (POA) irradiance.** Hay–Davies sky-diffuse
   transposition (`pvlib.irradiance.get_total_irradiance`):
   $$
   G_{\text{POA}} = G_{\text{beam}} \cos\theta_i + G_{\text{diff}} R_d^{\text{HD}}(\theta_z, \gamma_s, \beta) + \rho \, G_{\text{horiz}} \frac{1-\cos\beta}{2},
   $$
   with surface tilt $\beta$, surface azimuth $\gamma_p$, ground
   albedo $\rho=0.20$ (PVWatts default for mixed urban surfaces).
3. **Cell temperature.** SAPM open-rack glass-polymer parameter set
   (`pvlib.temperature.sapm_cell`). The thermal model is the standard
   choice for free-standing rooftop installations of crystalline-
   silicon modules — the dominant technology in the Egyptian market.
4. **DC power.** Linear PVWatts equation
   (`pvlib.pvsystem.pvwatts_dc`):
   $$
   P_{\text{dc}} = \frac{G_{\text{POA}}}{1000\,\mathrm{W/m^2}} \, P_{\text{dc0}} \, \bigl[1 + \gamma_{\text{P}}(T_{\text{cell}} - 25\,°\mathrm{C})\bigr],
   $$
   with $\gamma_{\text{P}} = -0.0035\,/\,°\mathrm{C}$ (typical for
   monocrystalline silicon) [@pvwatts2014].
5. **System DC losses.** A single combined-losses factor folds in
   soiling, mismatch, wiring, and module-nameplate tolerance.
   PVWatts canonical default $\eta_{\text{loss}} = 0.14$:
   $$
   P_{\text{dc, net}} = (1 - \eta_{\text{loss}}) \, P_{\text{dc}}.
   $$
6. **AC conversion.** `pvlib.inverter.pvwatts` clips at the inverter
   nominal AC capacity using the constant efficiency
   $\eta_{\text{inv}}=0.96$; the DC : AC ratio is held at unity in
   the baseline.

The annual energy, monthly energy, capacity factor, performance
ratio, and specific yield are aggregated from the resulting hourly
$P_{\text{ac}}$ series in the standard textbook fashion. The
"Cairo sanity band" for the headline specific yield is
$1\,700 \le P_{\text{ac, ann}} / P_{\text{sys}} \le 1\,900\,\mathrm{kWh/kWp}$;
agreement within this band is the first internal validation gate
(Validation §1, Day 20).

### 2.3 Energy generation — Manual physics model (independent twin)

The methodology's first defensible academic contribution is the
**dual-energy backbone**: alongside `pvlib` we ship a from-first-
principles chain that uses no `pvlib` calls. The two chains share
inputs and outputs but disagree, by design, at two intermediate
steps; cross-validating their headline numbers tells the reader how
much of the predicted yield is robust across modelling assumptions
and how much is parameter-sensitive.

| Step | pvlib chain | Manual chain |
|---|---|---|
| Solar geometry | NREL SPA [@nrel-spa] | Cooper (1969) declination + Spencer (1971) equation of time + classical hour-angle formulas [@duffie] |
| Sky-diffuse model | Hay–Davies (anisotropic) | Liu–Jordan (isotropic) [@liu1960] |
| Cell temperature | SAPM open-rack glass-polymer | NOCT model: $T_{\text{cell}} = T_{\text{air}} + \frac{NOCT-20}{800} \cdot G_{\text{POA}}$ with $NOCT = 45\,°\mathrm{C}$ |
| DC power | Linear PVWatts | Same equation, parameter-identical $\gamma_{\text{P}}$ |
| DC losses | PVWatts canonical $\eta_{\text{loss}} = 0.14$ | Same |
| AC conversion | `pvlib.inverter.pvwatts` | Constant $\eta_{\text{inv}}$, clip at $P_{\text{sys}}$ |

The two intermediate disagreements (Hay–Davies vs Liu–Jordan, SAPM
vs NOCT) are deliberate. They span the methodological choices a
practitioner would actually make; the residual between the two annual
energies is therefore an honest *methodological-uncertainty* number
rather than an artefact of two implementations of the same paper.

The cross-validation classification used in the dashboard is

$$
\Delta_{\text{rel}} = \frac{E_{\text{manual}} - E_{\text{pvlib}}}{E_{\text{pvlib}}},
\qquad
\text{verdict} =
\begin{cases}
\text{strong agreement} & |\Delta_{\text{rel}}| < 5\% \\
\text{reasonable agreement} & 5\% \le |\Delta_{\text{rel}}| < 10\% \\
\text{material divergence} & |\Delta_{\text{rel}}| \ge 10\%
\end{cases}
$$

The 5 % strong-agreement threshold matches the documented pvlib-vs-PVSyst band for c-Si rooftop installations [@pvlib].

### 2.4 Loss decomposition

The DC-side loss factor $\eta_{\text{loss}} = 0.14$ used by both
energy chains decomposes into the components published in the NREL
PVWatts Version 5 manual [@pvwatts2014]:

| Component | Loss |
|---|---|
| Soiling | 2 % |
| Shading | 3 % |
| Snow | 0 % (Egypt) |
| Mismatch | 2 % |
| Wiring | 2 % |
| Connections | 0.5 % |
| Light-induced degradation (LID) | 1.5 % |
| Nameplate rating | 1 % |
| Availability | 3 % |
| **Total (combined)** | **$\approx 14\%$** |

The Egypt context would usually argue for a higher soiling allowance
than 2 % — Cairo's PM₁₀ load is $\sim 3 \times$ the European
average, and field studies have reported $5$ – $8\%$ soiling losses
during the long dry season [@elsayed2017]. The 14 % default is
therefore a deliberately conservative *floor*; the Monte Carlo
engine (§6) treats the lumped loss as part of the
`annual_yield_factor` distribution, so both the headline number and
the uncertainty interval reflect the realistic spread.

---

## 3. Roof Detection (Contribution A)

The first thesis contribution is to **eliminate the roof area
question**: a homeowner who does not know their roof area to within
$\pm 10\,\mathrm{m^2}$ would otherwise propagate that uncertainty
straight through to the headline payback. The detection pipeline is
two-stage by design: a vector OSM stage (§3.1) gives an analytically
defensible footprint for every successfully tagged building, and a
raster CV stage (§3.2) refines the polygon and assigns a
confidence score. A satellite tile that cannot be loaded triggers a
graceful fall-through to OSM-only with $\text{conf}=0$, so the
pipeline always produces a result.

### 3.1 OSM footprint retrieval and selection (Day 10)

For a query point $(\varphi_0, \lambda_0)$ the orchestrator issues an
Overpass `way[building]` query within the configured search radius
and ranks the returned polygons by a deterministic two-stage rule:

1. **Containment first.** Even a 1-cm offset from a building edge is
   far stronger evidence of identity than centroid distance — a user
   who drops a pin on their roof is almost always inside the polygon.
2. **Smallest area among containers.** Egyptian residential parcels
   are sometimes nested inside a larger `building=apartments`
   polygon that wraps a courtyard and several units; picking the
   *innermost* container disambiguates correctly.

When **no** polygon contains the pin (rural plot, mis-mapped
building, or sparse OSM coverage), the orchestrator falls back to the
building with the closest centroid; the result schema flags
`contains_query_point = False` so the dashboard can warn the user
that the match is heuristic.

For local distance and area we use a small-region equirectangular
projection centred on the user's pin:
$$
x = (\lambda - \lambda_0) \cos\varphi_0 \cdot R_{\oplus} \cdot \frac{\pi}{180}, \qquad
y = (\varphi - \varphi_0) \cdot R_{\oplus} \cdot \frac{\pi}{180},
$$
with $R_{\oplus} = 6\,378\,137\,\mathrm{m}$ (WGS84 semi-major axis).
At the building scale ($< 200\,\mathrm{m}$ diagonal) the maximum
area distortion versus a UTM-quality projection is below $0.05\%$ at
Cairo's latitude — well inside the roof-utilisation-factor
uncertainty downstream. We deliberately avoid pulling in `pyproj`
to keep the dependency surface small.

### 3.2 CV regularisation, confidence, and orientation (Day 11)

The OSM polygon is digitised by hand and routinely off by 1–2 m at
corners [@osm-quality]. The Day-11 refinement combines the OSM
prior with the satellite tile to produce two outputs:

**Polygon regularisation.** Real residential rooftops are almost
always rectangular, and OSM contributors often capture noisy traces
of an essentially rectangular building. The kernel computes the
*minimum-rotated rectangle* of the OSM polygon
(`shapely`'s ``minimum_rotated_rectangle``) and emits that as the
refined geometry. A regularised polygon collapses the digitisation
noise back to the underlying rectangle so the energy model receives
a clean shape and a single dominant orientation.

**Confidence score.** A polygon's segmentation confidence is the
*fraction* of polygon-perimeter pixels whose local Sobel gradient
magnitude exceeds the image's median, normalised to $[0, 1]$. Roof–
ground transitions show up as strong intensity gradients (concrete
vs ground, shingle vs lawn), so a polygon whose edges trace those
gradients gets a high score; one that floats inside a uniform region
gets a low one. Concretely, for an image $I$ with Sobel magnitude
$|\nabla I|$ and median $m_\nabla$, and a polygon perimeter sampled
into pixel-band coordinates $\mathcal{B}$ of width
$w_b = 1.0\,\mathrm{m}$ (≈ 7 px at zoom 20 / scale 2),
$$
\text{conf} = \frac{1}{|\mathcal{B}|} \sum_{(u,v) \in \mathcal{B}} \mathbb{1}\bigl[|\nabla I|(u, v) > m_\nabla\bigr] \in [0, 1].
$$
The 1.0 m band width is wide enough to absorb GPS jitter and OSM
digitisation noise (typical 0.5 – 1.5 m positional error per OSMF
accuracy studies [@osm-quality]) without bleeding into neighbouring
rooftops.

**Orientation inference.** The polygon's principal axis (long edge
of the regularised rectangle) gives a panel azimuth estimate
modulo $180°$. If the long-edge azimuth is within
$\delta_{\text{snap}} = 8°$ of a cardinal heading, the kernel
*snaps* to that heading — installers almost always orient panels
along the building's primary edges, and OSM digitisation jitter can
rotate a square footprint by $1$ – $2°$. The tilt is taken from
OSM `roof:angle` tags when present (validated against
$0° \le \beta \le 60°$), else inferred from `roof:shape`: flat for
a flat slab (the dominant Egyptian residential roof type, in which
case the panel-tilt prior reverts to the latitude optimum
$\beta = 26°$), $30°$ for pitched, $15°$ for shed.

**Why classical CV over a deep segmenter?** A pre-trained Mask R-CNN
or SAM model would push the headline number on benchmark datasets,
but (i) it would add $\sim 500\,\mathrm{MB}$ of model weights, GPU
dependence, and a reproducibility burden incompatible with a one-
laptop thesis demo; (ii) the marginal gain on dense urban Egyptian
rooftops — already well-represented in OSM — is bounded by the OSM
positional accuracy itself ($0.5$–$1.5\,\mathrm{m}$), which classical
regularisation already matches; (iii) confidence calibration of CNN
segmenters in the Egyptian residential domain has not been published
and would be a thesis in its own right [@vargas-munoz2021].

---

## 4. Tiered-tariff billing and PV-size optimisation (Contribution B)

### 4.1 EgyptERA progressive marginal block tariff

Egypt's residential bill is a *progressive marginal block* tariff,
not a flat rate. For the post-July 2023 EgyptERA reform schedule
[@egyptera_tariff], the upper kWh/month bound and EGP/kWh price for
each tier $i = 1 \dots K$ are

| $i$ | Upper bound (kWh / mo) | Price (EGP / kWh) |
|---|---|---|
| 1 | 50 | 0.58 |
| 2 | 100 | 0.68 |
| 3 | 200 | 0.83 |
| 4 | 350 | 1.25 |
| 5 | 650 | 1.40 |
| 6 | 1 000 | 1.45 |
| 7 | $\infty$ | 1.55 |

For a household with monthly consumption $C\,\mathrm{kWh/mo}$, with
$U_0 = 0$ and $U_i$ the upper bound of tier $i$, the *progressive
marginal* monthly bill is

$$
B(C) = \sum_{i=1}^{K} p_i \cdot \min\bigl(U_i - U_{i-1}, \max(0, C - U_{i-1})\bigr).
$$

**Why marginal, not inclusive?** Egypt's published tariff is widely
reported in two forms in consumer-facing press: *inclusive*
(exceeding a threshold reverts the *whole* month's consumption to
the higher tier) and *marginal* (each band charges only the kWh
that fall inside it — the canonical "progressive" tariff used in
most economics texts). The official EgyptERA bill statement uses
the marginal interpretation (tier amounts on the bill add up to the
total), and it is the conservative choice for the *PV value* claim:
under an inclusive schedule PV would look even *more* valuable,
since saving one kWh near a band edge could shift the whole month
down a tier. Choosing the marginal schedule means our payback
claims hold under the worst of the two reasonable readings.

### 4.2 Self-consumption-first PV netting

The kernel models the *self-consumption-first* metering convention,
which matches Egypt's residential default (no export credit). For a
household with monthly consumption $C_m$ and PV generation $G_m$,
the post-PV monthly consumption is
$$
C^{\text{PV}}_m = \max\bigl(0, C_m - G_m\bigr),
$$
and the surplus generation $\max(0, G_m - C_m)$ is awarded an
optional export credit of $p_{\text{exp}}$ EGP/kWh (default 0).
Annual savings are
$$
S_{\text{ann}} = \sum_{m=1}^{12} \bigl[ B(C_m) - B(C^{\text{PV}}_m) + p_{\text{exp}} \cdot \max(0, G_m - C_m) \bigr].
$$

The dashboard's headline `average_savings_egp_per_kwh` is
$S_{\text{ann}} / \sum_m G_m$ — the *effective* per-kWh savings rate
the household actually realises, which under the EgyptERA schedule
can be 2–3 × the household's flat-tariff *average* rate. This
gap is the numerical backbone of Contribution B: a flat-tariff PV
calculator systematically under-counts Egyptian payback by exactly
this factor.

### 4.3 PV-size optimisation under the tier schedule

A flat-tariff calculator says "more generation is always better".
Under the marginal block tariff the optimum is finite: once
consumption is pulled down into the cheap tiers, additional
generation has near-zero value (because the export credit is zero).
The optimiser sweeps a candidate grid of system sizes
$\{P_k\}_{k=1}^{N_{\text{cand}}}$ (linear sweep between user-supplied
bounds), evaluates each candidate with the deterministic financial
kernel (§5), and returns the size that maximises NPV:

$$
P^\star = \arg\max_{P_k} \;\mathrm{NPV}(P_k).
$$

The full set of candidates is returned alongside $P^\star$ so the
methodology section's NPV-vs-size curve can be plotted directly
from the API response.

---

## 5. Financial Modelling

### 5.1 Year-by-year cash-flow chain

Year 0 is the moment of installation (capex paid). Year $t \ge 1$
is the $t$-th full year of operation. For an analysis horizon of
$T$ years, year-1 generation $E_1$, year-1 effective tariff
$p_1$, system size $P_{\text{sys}}$, installed cost $C_{\text{kW}}$
(EGP/kW), discount rate $r$, tariff escalation rate $i$, module
degradation rate $d$, and O&M as a fraction $f$ of capex:

$$
\begin{aligned}
\text{Capex}                   &= P_{\text{sys}} \cdot C_{\text{kW}} \\
E_t                            &= E_1 \cdot (1 - d)^{t-1} \\
p_t                            &= p_1 \cdot (1 + i)^{t-1} \\
S_t                            &= E_t \cdot p_t \quad &\text{(year-}t\text{ savings)}\\
\text{O\&M}_t                  &= f \cdot \text{Capex} \\
\text{Net}_t                   &= S_t - \text{O\&M}_t \\
\mathrm{NPV}                   &= -\,\text{Capex} + \sum_{t=1}^{T} \frac{\text{Net}_t}{(1+r)^t} \\
\mathrm{LCOE}                  &= \frac{\text{Capex} + \sum_{t=1}^{T} \text{O\&M}_t / (1+r)^t}{\sum_{t=1}^{T} E_t / (1+r)^t}
\end{aligned}
$$

The simple payback is the textbook
$\text{Capex} / (S_1 - \text{O\&M}_1)$, capped at $T$ if the project
fails to recover within the horizon. The *discounted* payback is
the year at which the discounted cumulative cash flow first turns
non-negative, with linear interpolation between bracketing years:

$$
t^\star = \min\bigl\{ t : \mathrm{CCF}_t \ge 0 \bigr\}, \qquad
\hat{t} = (t^\star - 1) + \frac{|\mathrm{CCF}_{t^\star - 1}|}{\mathrm{CCF}_{t^\star} - \mathrm{CCF}_{t^\star - 1}},
\quad
\mathrm{CCF}_t = -\,\text{Capex} + \sum_{s=1}^{t} \frac{\text{Net}_s}{(1+r)^s}.
$$

**Why both simple and discounted payback?** Simple payback is
widely criticised in the energy-finance literature for ignoring the
time value of money and the post-payback period, yet it is the
single number every PV brochure quotes. A defensible thesis must
report it (so the result is comparable to the literature and to
consumer-facing tools) **and** report NPV/LCOE/discounted payback
alongside, so the reader can see the gap that the naïve metric
hides. The kernel returns both.

### 5.2 Egypt-specific economic constants

The default values for $r, i, d, f, C_{\text{kW}}, T$ are listed in
§1.3. The 25-year horizon $T$ matches the standard PV module
performance warranty and is the analysis period adopted in most
Egyptian PV pre-feasibility studies [@mahmoud2023].

---

## 6. Uncertainty Quantification — Monte Carlo (Contribution C)

The deterministic financial kernel returns a *point* estimate of
payback, NPV, and LCOE. The third thesis contribution treats the
seven parameters with the largest real-world uncertainty as
*probability distributions* and re-evaluates the same kernel
$N_{\text{sim}}$ times to produce *distributions* of the headline
metrics. The default $N_{\text{sim}} = 1\,000$ delivers
$\pm 0.05$-year confidence on the median payback by Hoeffding's
inequality at the observed sample standard deviation.

### 6.1 Parametric distributions and priors

Each uncertain input gets a prior anchored in the published
literature. Two families are supported (normal and triangular),
because they cover the academically relevant cases without forcing
the API surface to grow as new parameters are added.

| Parameter | Distribution | Source / justification |
|---|---|---|
| Module degradation $d$ | $\mathrm{Triangular}(0.002, 0.005, 0.010)\,/\mathrm{yr}$ | NREL bounds for mono-Si under standard warranty terms [@jordan2013] |
| Tariff inflation $i$ | $\mathrm{Normal}(0.08, 0.03)\,/\mathrm{yr}$, clipped at $0$ | EgyptERA decade trend [@egyptera_tariff] |
| O&M fraction $f$ | $\mathrm{Triangular}(0.005, 0.010, 0.020)$ | IRENA residential rooftop benchmark range [@irena2023] |
| Installed cost $C_{\text{kW}}$ | $\mathrm{Triangular}(30\,000, 35\,000, 45\,000)\,\mathrm{EGP/kW}$ | Egyptian market 2024 spread |
| Annual yield factor (weather + soiling) | $\mathrm{Normal}(1.0, 0.05)$, clipped to $[0.5, 1.5]$ | Egyptian PV field studies — TMY-vs-actual residual variance |
| Inverter replacement year | $\mathrm{Triangular}(10, 12, 15)$ | IEA-PVPS Task 13 inverter service-life [@ieapvps2021] |
| Inverter cost fraction | $\mathrm{Triangular}(0.07, 0.10, 0.15)$ of original capex | Egyptian installer quotes |

**Why parametric and not bootstrap?** A homeowner deciding on PV
at $t = 0$ has no historical sample of *their own* future panel
performance — only published priors on degradation, on tariff
policy, on weather. The right uncertainty model is therefore
parametric, with priors anchored in the literature. The kernel
exposes every distribution as a request-level override so a
sensitivity-aware caller can collapse any distribution to a
deterministic constant or substitute a site-specific prior.

**Why per-year, per-simulation yield noise?** Annual irradiance in
Egypt varies $\sim \pm 5\%$ around the TMY mean (Egyptian PV field
studies), and that variability *does not* average out over the
analysis horizon for the *payback* metric — early bad years push
payback later in nonlinear ways. The kernel therefore samples a
fresh yield factor for each $(\text{simulation}, \text{year})$
pair, giving a $(N_{\text{sim}}, T)$ matrix.

**Why one inverter replacement event, not zero or two?** Modern
string inverters in Egypt's climate carry $10$ – $12$ year warranties
and see a typical $12$ – $15$ year service life [@ieapvps2021]. A
25-year analysis horizon therefore captures one replacement;
modelling two would over-attribute uncertainty to the inverter
alone and is left for the sensitivity tornado (§7).

### 6.2 Sampling and aggregation

Sampling uses a NumPy `Generator` with an optional caller-supplied
`random_seed` so any reported figure is byte-reproducible. Each
distribution is drawn with the requested shape (scalar per
simulation, except for `annual_yield_factor` which is per
$(N_{\text{sim}}, T)$); clipping is applied as a last step. The
cash-flow simulation is fully vectorised in NumPy along the
simulation axis: a $1\,000\times25$ ensemble runs in under
$100\,\mathrm{ms}$ on a laptop, which matters because the
dashboard re-runs the engine on every user input change.

The reported aggregates per metric are
$\{\mathrm{mean}, \mathrm{std}, p_{05}, p_{10}, p_{25}, p_{50}, p_{75}, p_{90}, p_{95}, \min, \max\}$.
Reporting both $\mathrm{mean} \pm \mathrm{std}$ and the 5–95 %
percentile band makes the asymmetry of the simulated distribution
visible: payback in particular is heavily right-skewed (a fat tail
of "never recovers" runs) and a Gaussian-style $\mathrm{mean} \pm \mathrm{std}$
would mis-represent it on its own.

### 6.3 Cumulative-cash-flow trajectory bands (Day-16 fan chart)

Beyond per-metric percentiles, the engine also returns the *year-
by-year* percentile bands of the discounted cumulative cash flow.
For each year $t \in \{0, 1, \dots, T\}$ and percentile
$q \in \{5, 25, 50, 75, 95\}$,
$$
\mathrm{CCF}^{(q)}(t) = \mathrm{percentile}_q\bigl\{ \mathrm{CCF}^{(k)}(t) \,:\, k = 1\dots N_{\text{sim}}\bigr\}.
$$
The bands are *envelope* percentiles, not the trajectory of any
single simulation. Reporting bands rather than a single mean curve
is the whole point of the contribution: a homeowner sees not just
"the median crosses zero in year 7" but also "the worst-case 5 %
of futures still owe money in year 12" and "the best 5 % of
futures double their money by year 15".

---

## 7. Sensitivity Tornado (Day 18)

The tornado is the *attribution* counterpart to the Monte Carlo
*total-uncertainty* view. For each input parameter $\theta_p$
($p = 1\dots P$), one keeps every other parameter at its baseline
and re-runs the deterministic financial kernel at
$\theta_p \in \{\theta_p^{\text{low}}, \theta_p^{\text{high}}\}$,
recording the resulting metric values
$M_p^{\text{low}}, M_p^{\text{high}}$. The tornado bar for parameter
$p$ has length $|M_p^{\text{high}} - M_p^{\text{low}}|$; rows are
sorted by that absolute swing descending.

The seven parameters swung — `annual_kwh`, `tariff_egp_per_kwh`,
`cost_egp_per_kw`, `discount_rate`, `tariff_inflation_rate`,
`annual_degradation_rate`, `om_cost_fraction` — exactly mirror the
Monte Carlo stochastic inputs (§6) plus the household-level levers
(tariff, generation) that turn project-level uncertainty into
household-level decision support. The swing endpoints default to
literature-anchored low/high values for each parameter; callers
can supply explicit ranges per parameter via the API surface.

**Why OAT and not Sobol or variance decomposition?** Sobol indices
give a more complete picture of joint sensitivity but are not
directly interpretable as "this parameter changes my NPV by
$\pm X\,\mathrm{EGP}$" — they are *fractional contributions to
output variance* and require a non-trivial statistical literacy to
read. The OAT tornado is the standard reporting format in the
rooftop-PV pre-feasibility literature [@nrel-sam, @ieapvps-task7]
and the format the bachelor-thesis dashboard's homeowner audience
can read in a single pass. The Day-9 Monte Carlo engine, which
*does* model joint uncertainty, is the complementary figure —
together they cover both sensitivity questions a methodology
section is expected to address.

---

## 8. CO₂ Avoidance (Day 18)

For year-1 generation $E_1$, analysis horizon $T$, degradation
rate $d$, and grid emission factor $\varepsilon_{\text{grid}}$
(EEHC 2022/2023, $0.46\,\mathrm{kg\,CO_2 / kWh}$):

$$
\mathrm{CO_2}_t = E_1 \cdot (1 - d)^{t-1} \cdot \varepsilon_{\text{grid}}, \qquad
\mathrm{CO_2}_{\text{lifetime}} = \sum_{t=1}^{T} \mathrm{CO_2}_t.
$$

**Why a marginal grid-average emission factor and not a true
marginal-dispatch factor?** The Egyptian grid's marginal-dispatch
emission factor (the kg CO₂ avoided by displacing the *next* kWh
the grid would have generated) varies by hour, season, and merit-
order conditions. Public, peer-reviewed Egyptian time-resolved
marginal data is not available, so the standard practice in
Egyptian PV pre-feasibility literature [@mahmoud2023] is to use
the EEHC published *grid-average* annual emission factor. This
biases the result conservatively whenever PV displaces high-merit
gas peakers — the marginal factor is typically $10$ – $20\%$
higher than the grid-average in gas-dominated systems. The kernel
exposes the factor as an override so a methodology-aware user can
substitute a marginal number when one becomes available.

**Why no embodied-carbon subtraction?** A complete LCA would net
off the embodied carbon of the modules, inverter, and balance-of-
system (typically $30$ – $50\,\mathrm{g\,CO_2/kWh}$ amortised over a
25-year horizon, IEA-PVPS Task 12 [@ieapvps2020]). Including a
half-modelled LCA in the headline number would over-claim
precision the dataset does not support; we flag this in
`limitations.md` as future work.

**Homeowner-friendly equivalences.** The lifetime kg figure is also
reported as
- equivalent passenger-car kilometres at $0.12\,\mathrm{kg/km}$
  (EEA fleet-average tail-pipe);
- equivalent litres of petrol burnt at $2.31\,\mathrm{kg/L}$
  (EPA Greenhouse Gas Equivalencies Calculator);
- equivalent urban trees grown over the analysis horizon at
  $\sim 21\,\mathrm{kg\,CO_2/tree/yr}$ (US EPA midpoint).
The two anchors have very different orders of magnitude so no single
equivalence dominates the reader's intuition.

---

## 9. Reproducibility

All deterministic kernels (sizing, energy, financial, tariff, CO₂,
sensitivity) are pure functions of their request payloads — no
hidden state, no environment variables consumed inside the kernel.
The Monte Carlo engine accepts a `random_seed` that threads into
the underlying NumPy `Generator`; the test suite relies on this for
byte-identical re-runs and the API surface exposes it so any
reported figure in this thesis can be reproduced with a single
documented `curl` invocation.

External-API services (PVGIS, Overpass, Google Maps Static) are
hidden behind small adapter modules with explicit retry, timeout,
and error-translation behaviour. The full unit-test suite (358
tests as of Day 19) mocks every external call so a clean checkout
runs end-to-end without network access; the validation chapter
(Day 20) re-runs the same suite against live PVGIS for ten
representative Egyptian sites and reports the residuals.

The runtime environment is pinned to Python 3.12 with the
`requirements.txt` shipping pinned versions for `pvlib`, `pandas`,
`numpy`, `scipy`, `pillow`, `shapely`, `httpx`, `fastapi`, and
`pydantic`. The full thesis result set can be re-derived from the
repository at any commit by running

```bash
cd backend
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/uvicorn app.main:app --reload
# … then the documented curl invocations in each chapter
```

---

## 10. Summary

The four academic claims of the thesis decompose along the chapter
layout above:

| Claim | Section(s) |
|---|---|
| Dual energy model is the methodological backbone | §2.2, §2.3 |
| AI-assisted roof detection eliminates the most error-prone user input | §3.1, §3.2 |
| Egypt's tiered tariff is what a flat-tariff calculator gets wrong | §4.1, §4.2, §4.3 |
| Monte Carlo + tornado make uncertainty an artefact, not a postscript | §6, §7 |

Every constant in §1.3 is exposed as a Pydantic-validated override so
a methodology-aware caller can substitute a site-specific value
without touching the source. Every kernel is pure and deterministic
(except the Monte Carlo engine, which accepts a seed). Every figure
in this chapter resolves either to one of the seven backend service
modules or to one of the five frontend chart components — a one-to-
one mapping that makes the methodology auditable end-to-end.
