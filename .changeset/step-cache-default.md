---
"everystate": patch
---

The step cache is on by default with the compiled evaluator. It keeps, for an action instance, what the evaluation read of the state and the successors it produced, and reuses them in later states where the same things have the same values (every hit is compared in full, so results do not change). Whether it is used for a given action is measured during the run, on the time per state with and without it, so models where it does not pay run as before; on models built from many small local steps (actor-style specifications) checking takes about 10 to 20 % less CPU time and less memory. The table has a fixed size, 32 MB per worker by default (`EVERYSTATE_STEP_CACHE_MB`). `EVERYSTATE_STEP_CACHE=off` turns it off. It is off in the WebAssembly build.
