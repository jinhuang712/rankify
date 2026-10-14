# Step 4 scripts and logs

The scripts behind [the step 4 report](../2026-10-14-step4-fit-and-repeats.md), kept as they were run. They are one-off analyses, not maintained code: they reach into rankify's internals and set its switches (`service.EP_FIT`, `planner.ASK_AGAIN`) directly. All use practice lists (seeds 70000 + 1000 × items + list number), never the benchmark's test lists.

Run each from the repository root, with the root as the first argument, for example:

```sh
uv run python experiments/2026-10-14-step4/sigma_check.py . normal,careless,perfect,human,noisy 20 quick 10
```

The ones with a `[workers]` argument use at most that many processes (2 here), at low priority.

## What each one measured

Section numbers refer to the report.

| Script | Measures | Arguments used | Output | Section |
|---|---|---|---|---|
| `lag_diag.py` | rounds asked after the ranking was already right, and which stopping rule held on longest | `normal,perfect,careless,human 20 quick,stable 10` | `lag20.log` | 1 |
| `couldbe_mass.py` | how often Could be holds the true rank, against what rankify's own draws claim | `normal,perfect,human,noisy 20 quick,stable 10` | `couldbe20.log` | 1 |
| `reach_diag.py` | the items holding up the stop, their looks, and the joint chance that one belongs higher | `normal,perfect,careless,human 20 quick,stable 10` | `reach20.log` | 1 |
| `sigma_check.py` | the prior width the Laplace fit learns against the true spread, and how squeezed the gaps are | `normal,careless,perfect,human,noisy 20 quick 10` | `sigma20.log` | 1 |
| `hyper_check.py` | the learned width with the starting belief as shipped and nearly flat | `normal,perfect,human 20 quick 10` | below | 1 |
| `ep_check.py` | Laplace against `choix`'s EP on the same answers (plain pairs, flat belief) | `normal,perfect,human 20 quick 10` | below | 2 |
| `tilted_check.py` | the new fit's per-answer moments against brute-force integrals | (none) | below | 2 |
| `ep_vs_choix.py` | the new fit against `choix`'s EP, plain pairs, fixed width | (none) | below | 2 |
| `ep_check2.py` | Laplace against the new fit on the full model, shipped starting belief | `normal,perfect,careless,human,noisy 20 quick 10` | below | 2 |
| `spread_seeds.py` | learned width over 8 seeds of random pairs, both fits, both beliefs | (none) | below | 2 |
| `ep_profile.py`, `ep_profile2.py` | where the new fit's time goes, per outer round | a judge: `normal`, `perfect` or `human` | below | 2 |
| `ep_eval.py` | shipped fit against the new fit in sessions, both score shapes | `laplace,ep t3,normal normal,perfect,careless,human,noisy 20 quick,stable 10 2` | `ep_eval20.log` | 3 |
| `repeat_check.py` | how often sessions ask a pair already asked | `normal,perfect,careless,human,noisy 20 quick 10 2` | below | 4 |
| `perfect_norepeat.py` | the failing planner tests' setting with the repeat rule on | (none) | below | 4 |
| `norep_eval.py` | repeats allowed against "only when contradicted", old and new fit | `old,old-norep,new-norep normal,perfect,careless,human,noisy 20 quick,stable 10 2` | `norep20.log` | 4 |
| `sort_eval.py` | one re-check per pair, and rankify against Just Sort It and Ford–Johnson | `perfect,normal,careless,human,noisy 20 quick,stable 10 2` | `sort20.log` | 5 |

`sigma20.log` was rerun when these files were saved, because the first run's output wasn't kept; the report uses the rerun.

## Outputs printed to the screen

These scripts printed to the terminal only. Their output is copied here as it appeared.

`hyper_check.py`:

```text
normal   answers 70; true sd 9.58; learned sigma shipped 1.94, flat 2.05
perfect  answers 58; true sd 9.58; learned sigma shipped 2.05, flat 2.21
human    answers 105; true sd 2.56; learned sigma shipped 1.60, flat 1.62
```

`ep_check.py`:

```text
normal   decided pairs 70; true sd 9.58; spread learned: Laplace 1.92, EP 10.13; #1-#4 gap / true: Laplace 0.49, EP 2.04
perfect  decided pairs 58; true sd 9.58; spread learned: Laplace 2.05, EP 58.12; #1-#4 gap / true: Laplace 0.49, EP 9.05
human    decided pairs 102; true sd 2.56; spread learned: Laplace 1.50, EP 2.66; #1-#4 gap / true: Laplace 0.80, EP 1.00
```

`tilted_check.py` (largest errors; the keys are the model and the answer: 0 = first item wins, 1 = second, 2 = can't decide):

```text
('plain', 0) mean/sd 4.0e-12, var rel 7.7e-12
('plain', 1) mean/sd 1.4e-08, var rel 1.6e-07
('ties', 0) mean/sd 1.0e-12, var rel 2.1e-12, dlogZ/dlam 1.1e-10, d2logZ/dlam2 9.5e-08, dmean/dlam 2.2e-10
('ties', 1) mean/sd 1.7e-08, var rel 1.9e-07, dlogZ/dlam 3.3e-10, d2logZ/dlam2 3.0e-07, dmean/dlam 1.4e-08
('ties', 2) mean/sd 8.0e-10, var rel 5.4e-09, dlogZ/dlam 1.1e-10, d2logZ/dlam2 2.5e-07, dmean/dlam 1.2e-10
```

`ep_vs_choix.py` (before the fit's speed-ups, which change the passes and times, not the results):

```text
n=8 m=30 sigma=1.5: max |mean diff| 1.64e-03 (scale 2.32); max |cov diff| 1.80e-03 (scale 1.04); sweeps 27; 5.6 ms
n=12 m=300 sigma=1.5: max |mean diff| 6.99e-04 (scale 1.94); max |cov diff| 3.51e-04 (scale 0.33); sweeps 26; 35.3 ms
n=20 m=70 sigma=10.0: max |mean diff| 1.97e-03 (scale 14.71); max |cov diff| 9.70e-03 (scale 34.99); sweeps 108; 32.4 ms
n=20 m=60 sigma=30.0: max |mean diff| 4.87e-03 (scale 45.47); max |cov diff| 5.18e-02 (scale 307.73); sweeps 116; 38.2 ms
```

`ep_check2.py` (before the speed-ups; the widths, gaps and tie weights are the same after them, the times and passes are not):

```text
normal   answers 70; true sd 9.58; spread: Laplace 1.94, EP 4.80; #1-#4 gap / true: Laplace 0.52, EP 0.94; tie weight Laplace 0.057, EP 0.082; EP 297 ms, 493 passes (median)
perfect  answers 58; true sd 9.58; spread: Laplace 2.05, EP 6.33; #1-#4 gap / true: Laplace 0.51, EP 1.31; tie weight Laplace 0.063, EP 0.101; EP 172 ms, 582 passes (median)
careless answers 80; true sd 9.58; spread: Laplace 1.85, EP 3.56; #1-#4 gap / true: Laplace 0.36, EP 0.51; tie weight Laplace 0.049, EP 0.058; EP 256 ms, 326 passes (median)
human    answers 105; true sd 2.56; spread: Laplace 1.60, EP 2.51; #1-#4 gap / true: Laplace 0.86, EP 1.04; tie weight Laplace 0.095, EP 0.106; EP 314 ms, 302 passes (median)
noisy    answers 108; true sd 2.56; spread: Laplace 1.62, EP 2.49; #1-#4 gap / true: Laplace 1.12, EP 1.51; tie weight Laplace 0.039, EP 0.044; EP 283 ms, 264 passes (median)
```

`spread_seeds.py`:

```text
true sd 1.5, 150 answers: learned / real, min-median-max over 8 seeds
   EP flat          0.87 1.00 1.24
   Laplace flat     0.72 0.82 1.02
   EP shipped       0.88 1.00 1.23
   Laplace shipped  0.74 0.85 1.03
true sd 3.0, 150 answers: learned / real, min-median-max over 8 seeds
   EP flat          0.80 0.96 1.28
   Laplace flat     0.61 0.69 0.83
   EP shipped       0.80 0.89 1.13
   Laplace shipped  0.59 0.67 0.79
true sd 8.0, 120 answers: learned / real, min-median-max over 8 seeds
   EP flat          0.46 0.75 1.04
   Laplace flat     0.25 0.32 0.49
   EP shipped       0.38 0.58 0.82
   Laplace shipped  0.24 0.30 0.46
true sd 8.0, 400 answers: learned / real, min-median-max over 8 seeds
   EP flat          0.63 0.88 1.00
   Laplace flat     0.50 0.60 0.76
   EP shipped       0.57 0.75 0.89
   Laplace shipped  0.46 0.54 0.71
```

`ep_profile.py`, first line of each run. The fit took 176 ms and 514 passes on the normal judge's session as first written; then 81 ms and 222 passes with inexact inner solves; then, with Anderson acceleration:

```text
56 answers; 59 ms; 129 passes; sigma 4.561        (normal)
57 answers; 59 ms; 172 passes; sigma 6.175        (perfect)
143 answers; 116 ms; 96 passes; sigma 1.787       (human)
```

and with the peak search capped at 12 steps, the human judge's session took 57 ms (96 passes, sigma 1.787).

`repeat_check.py` ("old" is the shipped fit, "new" the new fit; repeats were allowed in both):

```text
normal   quick  old:  41% of rounds repeat a pair (288 of 708); after one-sided answers 199; most times one pair was asked: median 8, max 25
normal   quick  new:  40% of rounds repeat a pair (249 of 623); after one-sided answers 177; most times one pair was asked: median 8, max 16
perfect  quick  old:  31% of rounds repeat a pair (183 of 590); after one-sided answers 183; most times one pair was asked: median 5, max 6
perfect  quick  new:  24% of rounds repeat a pair (107 of 441); after one-sided answers 107; most times one pair was asked: median 4, max 4
careless quick  old:  43% of rounds repeat a pair (361 of 839); after one-sided answers 230; most times one pair was asked: median 8, max 17
careless quick  new:  45% of rounds repeat a pair (331 of 737); after one-sided answers 207; most times one pair was asked: median 8, max 15
human    quick  old:  51% of rounds repeat a pair (529 of 1040); after one-sided answers 234; most times one pair was asked: median 14, max 25
human    quick  new:  50% of rounds repeat a pair (468 of 943); after one-sided answers 208; most times one pair was asked: median 12, max 23
noisy    quick  old:  49% of rounds repeat a pair (522 of 1062); after one-sided answers 268; most times one pair was asked: median 16, max 26
noisy    quick  new:  51% of rounds repeat a pair (502 of 984); after one-sided answers 272; most times one pair was asked: median 13, max 21
```

`perfect_norepeat.py` (repeat rule "contradicted"):

```text
old formula, quick : stopped by 'nothing worth asking' after 31 rounds; rankify thinks target holds: False; really right: True
old formula, stable: stopped by 'nothing worth asking' after 35 rounds; rankify thinks target holds: False; really right: True
old formula, exact : stopped by 'nothing worth asking' after 36 rounds; rankify thinks target holds: False; really right: True
new formula, quick : stopped by 'nothing worth asking' after 27 rounds; rankify thinks target holds: False; really right: True
new formula, stable: stopped by 'nothing worth asking' after 35 rounds; rankify thinks target holds: False; really right: True
new formula, exact : stopped by 'nothing worth asking' after 33 rounds; rankify thinks target holds: False; really right: True
```
