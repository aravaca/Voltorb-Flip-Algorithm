# Voltorb Flip Assistant

A small helper for the 5x5 Voltorb Flip puzzle that enumerates all valid boards given row/column sums and bomb counts, computes exact posterior probabilities P(0/1/2/3) and expected values (EV) for each unopened cell, and recommends the cell with the lowest probability of being a bomb.

Key features
- Exact enumeration of all boards consistent with provided constraints.
- Per-cell posteriors and EV calculation.
- Recommends the safest next cell (min P(0), tiebreaker: max EV).
- Interactive CLI to step through a game.

Quick start
1. Inspect the main implementation and helpers in [voltorb.py](voltorb.py):
   - core enumerator: [`_enumerate_all_boards`](voltorb.py)
   - row pattern generator: [`_enumerate_row_patterns`](voltorb.py)
   - posterior & EV calculator: [`compute_posteriors`](voltorb.py)
   - choice logic: [`choose_next_safest`](voltorb.py)
   - input validation: [`sanity_check`](voltorb.py)
   - interactive loop: [`interactive_game`](voltorb.py)
   - simple board printer: [`print_board`](voltorb.py)

2. Run interactively:
```sh
python voltorb.py
```
Follow prompts to enter 5 row sums, 5 row bomb counts, 5 column sums, and 5 column bomb counts. The program verifies basic consistency (e.g. total sums and bomb counts) before enumerating solutions.

Constraints (mathematical)
- Total sum constraint: $ \sum_{r=0}^{4} \text{row\_sums}[r] = \sum_{c=0}^{4} \text{col\_sums}[c] $
- Total bombs constraint: $ \sum_{r=0}^{4} \text{row\_bombs}[r] = \sum_{c=0}^{4} \text{col\_bombs}[c] $
- Each non-bomb cell ∈ {1,2,3} so per-row/column sums must be achievable given non-bomb counts.

Notes on implementation
- The solver generates all possible length-5 row patterns that meet row sum/bomb constraints (see [`_enumerate_row_patterns`](voltorb.py)) and then composes full boards row-by-row while pruning using column partial bounds (see [`_col_bounds_so_far`](voltorb.py) inside the file).
- Because the board is fixed at 5×5, exhaustive search with pruning is practical and yields exact probabilities.

When to use
- Use this tool when you want an exact probabilistic recommendation (not a heuristic) for the next flip in Voltorb Flip given full row/column constraints and any already-opened cells.

Contributing
- Improvements welcome: add a small GUI, caching of intermediate results, or optimized pruning heuristics.

License
- MIT 