# Philosophy

These are the principles behind rankify. They settle trade-offs that the design docs don't cover. [DESIGN.md](DESIGN.md) shows how the current design applies them.

## 1. Human attention is the scarce resource.

Every question costs the judge effort. Ask only what can change the result, and stop when nothing can. Efficiency is measured in the judge's time, not in compute or in the number of questions.

## 2. Answers are evidence, not facts.

People are inconsistent, and any single answer may be wrong. Conclusions come from the weight of all the evidence. No single answer settles anything.

## 3. Results must be reproducible.

The result depends only on the recorded answers. Anyone with the same record gets the same result. Nothing that goes unrecorded can affect it.

## 4. Never claim more certainty than the data supports.

Every conclusion states how sure it is. That level of certainty must hold up when checked against reality.

## 5. Proven before novel.

Build on established methods. A new idea earns its place only by measurably beating the simpler alternative.

## 6. Keep up with the judge.

The tool responds as fast as the judge answers. Slow work happens out of the way.

## When principles conflict

Reproducibility (3) and honesty (4) come before speed (6) and convenience.
