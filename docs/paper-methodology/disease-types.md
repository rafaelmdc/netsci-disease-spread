# Disease types & parameters

The diseases we test, the compartmental model each uses, and the source for every
parameter. Rates are per day; **rate = 1/duration**. β is not set directly; it is set so the
within-city reproduction number equals the type's literature R₀: `β = R₀·γ` (SIR/SIS/SEIR),
or `β = R₀·(γ+κ)` for the isolation type, since isolation shortens the infectious period. No
`⟨k²⟩/⟨k⟩` correction is applied: that is for individual-contact networks, whereas here nodes
are well-mixed cities.

## The types

Five disease *types*, defined by their dynamics. We give example diseases for each and
take the parameter values from one representative exemplar (cited below).

| # | Type | Model | Example diseases | Parameters from |
|---|------|-------|------------------|-----------------|
| 1 | Immunizing, acute | SIR | measles, rubella, mumps | measles |
| 2 | Latent + immunizing | SEIR | COVID-19, SARS, chickenpox | COVID-19 |
| 3 | Lethal, isolation-controlled | SEIQR+D | Ebola, Marburg, pneumonic plague | Ebola |
| 4 | Endemic, no immunity | SIS | gonorrhea, chlamydia, common cold | gonorrhea |
| 5 | Recurrent, waning immunity | SEIRS | seasonal influenza, RSV, norovirus | seasonal influenza |

The lethal type (3) uses SEIQR+D: an SEIQR structure with an added fatal
compartment D, parameterised from Ebola.

## Parameter values (per type)

| # | Type · model | γ | σ | κ | ω | μ | R₀ |
|---|--------------|---|---|---|---|---|----|
| 1 | Immunizing · SIR | 0.13 (~8 d) | — | 0 | 0 | ≈0 | 12–18 |
| 2 | Latent · SEIR | 0.13 (~7–8 d) | 0.20 (~5.1 d) | 0 | 0 | ~0.01 | 2–3.3 |
| 3 | Lethal · SEIQR+D | 0.10 (~10 d) | 0.09 (~11.4 d) | 0.20 (~5 d) | 0 | 0.71 | 1.5–2.5 |
| 4 | Endemic · SIS | ~0.01–0.05 | — | 0 | ∞ | 0 | low (≳1) |
| 5 | Recurrent · SEIRS | 0.21 (~4.8 d) | 0.70 (~1.4 d) | 0 | ~0.001 (2–7 yr) | ~0.001 | 1.3–1.8 |

Type 4 (endemic) γ and R₀ are illustrative — no immunity and a long, variable untreated
duration; the regime is what matters, not the exact numbers. Type 3 `γ_Q` ≈ γ ≈ 0.10.

## Source for every value

γ, σ, κ come from a measured clinical duration of the exemplar; R₀ from a separate
epidemiological study; β is derived from both.

| Type | Value | Measured quantity | Source (paraphrased) | Citation |
|------|-------|-------------------|----------------------|----------|
| 1 Immunizing (measles) | γ=0.13 | infectious ~8 d | contagious 4 d before to 4 d after rash | CDC, Clinical Overview of Measles |
| 1 | R₀=12–18 | R₀ | "often cited to be 12–18" (review of 58 estimates) | Guerra et al. 2017, *Lancet Infect Dis* |
| 1 | ω=0 | immunity | natural infection confers life-long immunity | CDC |
| 2 Latent (COVID) | σ=0.20 | incubation 5.1 d | "mean incubation period 5.1 days (95% CI 4.5–5.8)" | Lauer et al. 2020, *Ann Intern Med* |
| 2 | γ=0.13 | infectious ~1 wk | infectiousness peaks near onset, low by ~7 d | He et al. 2020, *Nat Med* |
| 2 | R₀=2–3.3 | R₀ | "pooled R₀ 3.32 (95% CI 2.81–3.82)" | Alimohamadi et al. 2020, *J Prev Med Public Health* |
| 3 Lethal (Ebola) | σ=0.09 | incubation 11.4 d | "incubation period was 11.4 days" | WHO Ebola Response Team 2014, *NEJM* |
| 3 | γ, κ, structure | onset→hospital ~5 d | SEIHFR; transmission in community/hospital/burial | Legrand et al. 2007, *Epidemiol. Infect.* |
| 3 | μ=0.71 | case-fatality | "case fatality rate 70.8% (95% CI 69–73)" | WHO Ebola Response Team 2014, *NEJM* |
| 3 | R₀=1.5–2.5 | R₀ (SEIR fit) | 1.51 Guinea, 2.53 Sierra Leone, 1.59 Liberia | Althaus 2014, *PLoS Curr.* |
| 4 Endemic (gonorrhea) | SIS/ω=∞ | immunity, latency | "negligible protective immunity, negligible latent period" | Hethcote & Yorke 1984 |
| 4 | γ | untreated duration | median untreated pharyngeal gonorrhea ≈16 weeks | Barbee et al. 2021, *Clin Infect Dis* |
| 5 Recurrent (influenza) | σ=0.70 | incubation 1.4 d | "median incubation period for influenza A 1.4 days" | Lessler et al. 2009, *Lancet Infect Dis* |
| 5 | γ=0.21 | shedding 4.8 d | "viral shedding averaged 4.80 days (95% CI 4.31–5.29)" | Carrat et al. 2008, *Am J Epidemiol* |
| 5 | ω≈0.001 | immunity | influenza A immunity wanes in 2–7 yr via antigenic drift | Woolthuis et al. 2017, *BMC Infect Dis* |
| 5 | R₀=1.3–1.8 | R₀ (review) | median R ≈1.80 for 1918 pandemic (IQR 1.47–2.27) | Biggerstaff et al. 2014, *BMC Infect Dis* |

**γ and R₀ are independent; β is derived from both.** Types 1 and 3 (measles, Ebola) have
similar infectious periods (~8–10 d) but R₀ differs ~7× (≈15 vs ≈2), entirely because β
differs (airborne vs. bodily-fluid contact). The infectious period does not set R₀ — with β, it produces it.

## Out of scope

Not directly person-to-person, so they need an extra compartment: cholera (waterborne
→ add W), malaria/dengue (vector), HIV (chronic, no recovery).

## BibTeX

Model-structure refs (`kermack:sir`, `newman:spread`, `vandendriessche:r0`) are already
in `../tex/references.bib`. Add:

```bibtex
@article{guerra:measles,
  title={The basic reproduction number ($R_0$) of measles: a systematic review},
  author={Guerra, Fiona M. and Bolotin, Shelly and Lim, Gillian and Heffernan, Jane
          and Deeks, Shelley L. and Li, Ye and Crowcroft, Natasha S.},
  journal={The Lancet Infectious Diseases}, volume={17}, number={12},
  pages={e420--e428}, year={2017}, doi={10.1016/S1473-3099(17)30307-9}}

@article{lauer:incubation,
  title={The incubation period of coronavirus disease 2019 (COVID-19) from publicly
         reported confirmed cases: estimation and application},
  author={Lauer, Stephen A. and Grantz, Kyra H. and Bi, Qifang and Jones, Forrest K.
          and Zheng, Qulu and Meredith, Hannah R. and Azman, Andrew S.
          and Reich, Nicholas G. and Lessler, Justin},
  journal={Annals of Internal Medicine}, volume={172}, number={9},
  pages={577--582}, year={2020}, doi={10.7326/M20-0504}}

@article{he:shedding,
  title={Temporal dynamics in viral shedding and transmissibility of COVID-19},
  author={He, Xi and Lau, Eric H. Y. and Wu, Peng and Deng, Xilong and Wang, Jian
          and Hao, Xinxin and Lau, Yiu Chung and Wong, Jessica Y. and Guan, Yujuan
          and Tan, Xinghua and Mo, Xiaoneng and others},
  journal={Nature Medicine}, volume={26}, number={5}, pages={672--675}, year={2020},
  doi={10.1038/s41591-020-0869-5}}

@article{alimohamadi:covidr0,
  title={Estimate of the basic reproduction number for COVID-19:
         a systematic review and meta-analysis},
  author={Alimohamadi, Yousef and Taghdir, Maryam and Sepandi, Mojtaba},
  journal={Journal of Preventive Medicine and Public Health}, volume={53},
  number={3}, pages={151--157}, year={2020}, doi={10.3961/jpmph.20.076}}

@article{legrand:ebola,
  title={Understanding the dynamics of Ebola epidemics},
  author={Legrand, Judith and Grais, Rebecca F. and Boelle, Pierre-Yves
          and Valleron, Alain-Jacques and Flahault, Antoine},
  journal={Epidemiology \& Infection}, volume={135}, number={4},
  pages={610--621}, year={2007}, doi={10.1017/S0950268806007217}}

@article{whoebola2014,
  title={Ebola virus disease in West Africa---the first 9 months of the epidemic
         and forward projections},
  author={{WHO Ebola Response Team}},
  journal={New England Journal of Medicine}, volume={371}, number={16},
  pages={1481--1495}, year={2014}, doi={10.1056/NEJMoa1411100}}

@article{althaus:ebolar0,
  title={Estimating the reproduction number of Ebola virus (EBOV) during the
         2014 outbreak in West Africa},
  author={Althaus, Christian L.},
  journal={PLoS Currents Outbreaks}, year={2014},
  doi={10.1371/currents.outbreaks.91afb5e0f279e7f29e7056095255b288}}

@book{hethcote:gonorrhea,
  title={Gonorrhea Transmission Dynamics and Control},
  author={Hethcote, Herbert W. and Yorke, James A.},
  series={Lecture Notes in Biomathematics}, volume={56},
  publisher={Springer-Verlag}, year={1984}}

@article{barbee:gonorrhea,
  title={The duration of pharyngeal gonorrhea: a natural history study},
  author={Barbee, Lindley A. and Soge, Olusegun O. and Khosropour, Christine M.
          and Haglund, Micaela and Yeung, Winnie and Hughes, James and Golden, Matthew R.},
  journal={Clinical Infectious Diseases}, volume={73}, number={4},
  pages={575--582}, year={2021}, doi={10.1093/cid/ciab071}}

@article{lessler:incubation,
  title={Incubation periods of acute respiratory viral infections: a systematic review},
  author={Lessler, Justin and Reich, Nicholas G. and Brookmeyer, Ron and Perl, Trish M.
          and Nelson, Kenrad E. and Cummings, Derek A. T.},
  journal={The Lancet Infectious Diseases}, volume={9}, number={5},
  pages={291--300}, year={2009}, doi={10.1016/S1473-3099(09)70069-6}}

@article{carrat:influenza,
  title={Time lines of infection and disease in human influenza:
         a review of volunteer challenge studies},
  author={Carrat, Fabrice and Vergu, Elisabeta and Ferguson, Neil M. and Lemaitre, Magali
          and Cauchemez, Simon and Leach, Steve and Valleron, Alain-Jacques},
  journal={American Journal of Epidemiology}, volume={167}, number={7},
  pages={775--785}, year={2008}, doi={10.1093/aje/kwm375}}

@article{woolthuis:influenza,
  title={Variation in loss of immunity shapes influenza epidemics
         and the impact of vaccination},
  author={Woolthuis, Rutger G. and Wallinga, Jacco and van Boven, Michiel},
  journal={BMC Infectious Diseases}, volume={17}, pages={632}, year={2017},
  doi={10.1186/s12879-017-2716-y}}

@article{biggerstaff:influenzar0,
  title={Estimates of the reproduction number for seasonal, pandemic, and zoonotic
         influenza: a systematic review of the literature},
  author={Biggerstaff, Matthew and Cauchemez, Simon and Reed, Carrie
          and Gambhir, Manoj and Finelli, Lyn},
  journal={BMC Infectious Diseases}, volume={14}, pages={480}, year={2014},
  doi={10.1186/1471-2334-14-480}}

@misc{cdc:measles,
  title={Clinical Overview of Measles},
  author={{Centers for Disease Control and Prevention}},
  howpublished={\url{https://www.cdc.gov/measles/hcp/clinical-overview/index.html}},
  note={Accessed 2026}}
```
