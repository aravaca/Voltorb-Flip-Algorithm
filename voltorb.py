

from __future__ import annotations
from typing import Dict, List, Tuple, Optional

# ============================================================================
# Voltorb Flip 보조 도구
#
# 목적:
# - 5x5 Voltorb Flip 퍼즐에서 '행 합/열 합'과 '행 폭탄/열 폭탄' 제약을 이용해
#   가능한 모든 보드(모든 미확정 칸의 값 조합)를 전수 탐색하고,
#   각 미확정 칸마다 P(0), P(1), P(2), P(3) 및 기대값(EV)을 계산하여
#   "P(0) 최소(즉 가장 안전한)" 칸을 추천합니다.
#
# 핵심 아이디어:
# 1) 행 단위로 가능한 패턴들을 먼저 모두 열거한다.
#    - 각 행은 5칸이며, 각 칸은 0(폭탄), 1,2,3 중 하나.
#    - 행 합(row_sums)과 행 폭탄(row_bombs), 그리고 이미 열린 칸(opened)을 고려해
#      그 행 내부에서 가능한 모든 길이-5 패턴을 생성한다.
#    - 행 내부 열거는 DFS(백트래킹)로 구현되며, 남은 합(rem_sum)과 남은 폭탄(rem_bombs)
#      에 대한 하한/상한으로 가지치기(prune)합니다.
#
# 2) 행 패턴들로부터 전체 보드를 백트래킹으로 조합하면서 열 제약으로 추가 프루닝.
#    - 각 행에 대해 사전 생성한 패턴 후보들 중 하나를 선택해 그 행을 채우고,
#      누적 열 합(col_sum)과 누적 열 폭탄(col_bz)을 갱신합니다.
#    - 각 열에 대해 앞으로 남은(미할당) 행 수를 계산하고, _col_bounds_so_far로
#      해당 열의 최종 합과 폭탄수가 가능한지 확인하여 불필요한 분기를 제거합니다.
#
# 3) 가능한 모든 완전한 보드(열 제약까지 만족)를 모아 숙고한 후
#    미확정 칸별로 값 등장 빈도에서 사후확률(posteriors)과 기대값을 계산합니다.
#
# 성능 유의점:
# - 행 패턴을 미리 생성하면 행 선택 순서에 따른 중복 계산을 줄일 수 있음.
# - 열 프루닝은 남은 행 수 기준으로 합·폭탄 범위를 검사하여 조기 종료를 유도.
# - 5x5 고정 크기이므로 브루트포스+가지치기로 충분히 빠르게 동작함.
# ============================================================================



# ==========
# Voltorb Flip 보조: P(0) 최소 추천
# (행/열 합 & 폭탄 수 제약 하에서 가능한 보드 전수 + 정확 확률)
# ==========

N = 5
Val = int
Coord = Tuple[int, int]
Grid = List[List[Val]]

# debug flag
DEBUG = False

# ---------------------------
# 열 프루닝용 보조 (부분 누적 -> 가능한 합 구간)
# ---------------------------
def _col_bounds_so_far(target_sum, target_bombs, partial_sum, partial_bombs, rows_left):
    """
    열 제약 하한/상한으로 pruning:
    - target_sum: 열의 목표(최종) 합
    - target_bombs: 열의 목표(최종) 폭탄 수
    - partial_sum: 현재까지 더해진 합(이미 채운 행들)
    - partial_bombs: 현재까지 채워진 폭탄 수(이미 채운 행들)
    - rows_left: 아직 남은(미채운) 행 수
    반환: (min_possible, max_possible) 또는 None(불가능)
    """
    bombs_left = target_bombs - partial_bombs
    if bombs_left < 0 or bombs_left > rows_left:
        return None
    nonbomb_left = rows_left - bombs_left
    min_add = nonbomb_left * 1
    max_add = nonbomb_left * 3
    min_possible = partial_sum + min_add
    max_possible = partial_sum + max_add
    return min_possible, max_possible

# ---------------------------
# 유틸
# ---------------------------
def _row_remaining(r: int, row_sums, row_bombs, opened: Dict[Coord, Val]) -> Tuple[int,int,int,List[int]]:
    """행 r의 남은 합 R, 남은 폭탄 Z, 미확정 칸 수 k, 미확정 열 인덱스 cs"""
    S = sum(v for (rr, cc), v in opened.items() if rr == r)
    Z_open = sum(1 for (rr, cc), v in opened.items() if rr == r and v == 0)
    R = row_sums[r] - S
    Z = row_bombs[r] - Z_open
    cs = [c for c in range(N) if (r, c) not in opened]
    return R, Z, len(cs), cs

# ---------------------------
# 행 패턴 전수 (행 내부 제약만)
# ---------------------------
def _enumerate_row_patterns(r: int, row_sums, row_bombs, col_sums, col_bombs,
                            opened: Dict[Coord, Val]) -> List[List[Val]]:
    """
    주어진 행 r에 대해 행 내부 제약(행 합, 행 폭탄 수, 이미 열린 칸)만을 만족하는
    가능한 길이-N 패턴들을 모두 반환.
    """
    R, Z, k, cs = _row_remaining(r, row_sums, row_bombs, opened)

    patterns: List[List[Val]] = []
    row_fixed = [opened.get((r, c)) for c in range(N)]

    def dfs(c: int, rem_sum: int, rem_bombs: int, acc: List[int]):
        # count how many unfixed (to-be-assigned) columns remain from c..N-1
        cols_unfixed_left = sum(1 for i in range(c, N) if row_fixed[i] is None)
        # infeasible bomb count
        if rem_bombs < 0 or rem_bombs > cols_unfixed_left:
            return
        # feasible sum range for remaining unfixed non-bomb slots
        nonbomb_slots = cols_unfixed_left - rem_bombs
        min_possible = nonbomb_slots * 1
        max_possible = nonbomb_slots * 3
        if rem_sum < min_possible or rem_sum > max_possible:
            return

        if c == N:
            if rem_sum == 0 and rem_bombs == 0:
                patterns.append(acc.copy())
            return

        fixed = row_fixed[c]
        if fixed is not None:
            # already opened/fixed cell: it's already accounted in R/Z, so do NOT subtract again
            v = fixed
            dfs(c+1, rem_sum, rem_bombs, acc + [v])
        else:
            # try bomb (0) if possible
            if rem_bombs > 0:
                dfs(c+1, rem_sum, rem_bombs-1, acc + [0])
            # try non-bomb values 1..3
            for v in (1, 2, 3):
                new_rem_sum = rem_sum - v
                # one fewer unfixed column after placing v
                new_cols_unfixed = cols_unfixed_left - 1
                # bombs remaining unchanged in this branch
                b_left = rem_bombs
                nonbomb_slots_after = new_cols_unfixed - b_left
                min_p = max(0, nonbomb_slots_after) * 1
                max_p = max(0, nonbomb_slots_after) * 3
                if new_rem_sum < min_p or new_rem_sum > max_p:
                    continue
                dfs(c+1, new_rem_sum, b_left, acc + [v])

    dfs(0, R, Z, [])
    return patterns

# ---------------------------
# 전체 보드 전수(행 단위 백트래킹 + 열 프루닝)
# ---------------------------
def _enumerate_all_boards(row_sums, row_bombs, col_sums, col_bombs, opened: Dict[Coord, Val]) -> List[Grid]:
    # 각 행의 가능한 패턴 미리 생성
    all_row_patterns: List[List[List[Val]]] = []
    for r in range(N):
        pats = _enumerate_row_patterns(r, row_sums, row_bombs, col_sums, col_bombs, opened)
        if not pats:
            if DEBUG: print(f"❌ 행 {r} 단계에서 전개 불가 (행 패턴 0)")
            return []
        all_row_patterns.append(pats)

    solutions: List[Grid] = []

    # 열 누적 (이미 열린 값 반영)
    col_sum = [sum(opened.get((r, c), 0) for r in range(N)) for c in range(N)]
    col_bz = [sum(1 for r in range(N) if opened.get((r, c)) == 0) for c in range(N)]

    grid: List[List[Optional[int]]] = [[opened.get((r, c)) for c in range(N)] for r in range(N)]

    def dfs_row(r: int):
        if r == N:
            # 최종 열 제약 일치해야 정답
            for c in range(N):
                if col_sum[c] != col_sums[c] or col_bz[c] != col_bombs[c]:
                    return
            solutions.append([[int(x) for x in row] for row in grid]) # type: ignore
            return

        for row_pat in all_row_patterns[r]:
            ok = True
            incr_sum = [0]*N
            incr_bz = [0]*N

            # 현재 행에 패턴 적용 가능 여부
            for c in range(N):
                v = row_pat[c]
                prev = grid[r][c]
                if prev is not None and prev != v:
                    ok = False; break
                incr_sum[c] = v - (prev or 0)
                incr_bz[c] = (1 if v == 0 else 0) - (1 if (prev == 0) else 0)

            if not ok:
                continue

            for c in range(N):
                grid[r][c] = row_pat[c]
                col_sum[c] += incr_sum[c]
                col_bz[c] += incr_bz[c]

            # 열 프루닝: 각 열별로 남은(미할당) 행 수 기준으로 최종 가능 합 구간 체크
            for c in range(N):
                # 앞으로 할당할 행들 중 이 열의 미확정(=None) 칸 수만 셈
                rows_left = sum(1 for rr in range(r+1, N) if grid[rr][c] is None)
                bnd = _col_bounds_so_far(col_sums[c], col_bombs[c], col_sum[c], col_bz[c], rows_left)
                if bnd is None:
                    ok = False
                    if DEBUG: print(f"[r={r}] 열{c} 폭탄수 불가 (partial_bombs={col_bz[c]}, target={col_bombs[c]}, rows_left={rows_left})")
                    break
                lo, hi = bnd
                if not (lo <= col_sums[c] <= hi):
                    ok = False
                    if DEBUG: print(f"[r={r}] 열{c} 합 불가: target={col_sums[c]}, 가능[{lo},{hi}] (partial_sum={col_sum[c]}, rows_left={rows_left})")
                    break

            if ok:
                dfs_row(r + 1)

            # 롤백
            for c in range(N):
                col_sum[c] -= incr_sum[c]
                col_bz[c] -= incr_bz[c]
                grid[r][c] = opened.get((r, c))

    dfs_row(0)
    if not solutions and DEBUG:
        print("❌ 보드 전개 결과: 해 0개")
    return solutions

# ---------------------------
# 사후확률/기대값 계산
# ---------------------------
def compute_posteriors(row_sums, row_bombs, col_sums, col_bombs, opened: Dict[Coord, Val]):
    sols = _enumerate_all_boards(row_sums, row_bombs, col_sums, col_bombs, opened)
    if not sols:
        return {}, 0

    targets = [(r, c) for r in range(N) for c in range(N) if (r, c) not in opened]
    counts = {rc: {0:0, 1:0, 2:0, 3:0} for rc in targets}

    for g in sols:
        for (r, c) in targets:
            counts[(r, c)][ g[r][c] ] += 1

    post = {}
    for rc, d in counts.items():
        tot = sum(d.values())
        if tot == 0:
            continue
        p0 = d[0] / tot
        p1 = d[1] / tot
        p2 = d[2] / tot
        p3 = d[3] / tot
        ev = 1*p1 + 2*p2 + 3*p3
        post[rc] = {"total": tot, "p": {0:p0, 1:p1, 2:p2, 3:p3}, "ev": ev}
    return post, len(sols)


# ---------------------------
# 의사결정: P(0) 최소
# ---------------------------
def choose_next_safest(posteriors):
    if not posteriors:
        return None
    return min(posteriors.items(), key=lambda kv: (kv[1]["p"][0], -kv[1]["ev"]))

# ---------------------------
# 입력 검증 (총계·물리 가능성)
# ---------------------------
def sanity_check(row_sums, row_bombs, col_sums, col_bombs) -> Optional[str]:
    if sum(row_sums) != sum(col_sums):
        return f"행 합({sum(row_sums)}) ≠ 열 합({sum(col_sums)})"
    if sum(row_bombs) != sum(col_bombs):
        return f"행 폭탄({sum(row_bombs)}) ≠ 열 폭탄({sum(col_bombs)})"
    for i in range(N):
        if not (0 <= row_bombs[i] <= N):
            return f"{i}행 폭탄 수 범위 초과"
        nb = N - row_bombs[i]
        if not (nb*1 <= row_sums[i] <= nb*3):
            return f"{i}행 합이 비폭탄 {nb}개로 만들 수 없는 값"
    for j in range(N):
        if not (0 <= col_bombs[j] <= N):
            return f"{j}열 폭탄 수 범위 초과"
        nb = N - col_bombs[j]
        if not (nb*1 <= col_sums[j] <= nb*3):
            return f"{j}열 합이 비폭탄 {nb}개로 만들 수 없는 값"
    return None
# ---------------------------
# 의사결정: P(0) 최소 (동률 시 EV 최대)
# 인터랙티브 루프
# ---------------------------
def print_board(opened: Dict[Coord, Val]):
    print("\n현재 열린 보드:")
    for r in range(N):
        print(" ".join(str(opened[(r,c)]) if (r,c) in opened else "·" for c in range(N)))

def interactive_game():
    print("=== Voltorb Flip 보조 (P(0) 최소 추천) ===")
    print("행/열 합과 폭탄 수를 입력하세요.")
    row_sums = list(map(int, input("행 합 5개: ").split()))
    row_bombs = list(map(int, input("행 폭탄 5개: ").split()))
    col_sums = list(map(int, input("열 합 5개: ").split()))
    col_bombs = list(map(int, input("열 폭탄 5개: ").split()))

    err = sanity_check(row_sums, row_bombs, col_sums, col_bombs)
    if err:
        print("⚠️ 입력 모순:", err)
        return

    opened: Dict[Coord, Val] = {}
    step = 0
    while True:
        print_board(opened)
        post, nsol = compute_posteriors(row_sums, row_bombs, col_sums, col_bombs, opened)
        if not post:
            print("⚠️ 모순이거나 해가 없습니다.")
            break

        print(f"\n가능한 전체 보드 수: {nsol}")
        # 가장 안전한 상위 5개 참고 출력
        top_safe = sorted(post.items(), key=lambda kv: (kv[1]["p"][0], -kv[1]["ev"]))[:5]
        if DEBUG:
            print("\n[Top Safe (min P0)]")
            for (rc, st) in top_safe:
                p = st["p"]
                print(f" {rc}: P0={p[0]:.3f} | EV={st['ev']:.3f} | P1={p[1]:.3f}, P2={p[2]:.3f}, P3={p[3]:.3f}")

        best = choose_next_safest(post)
        if best is None:
            print("추천 불가.")
            break
        best_rc, st = best
        print(f"\n[{step+1}단계] 추천 칸: {best_rc} | 폭탄일 확률={st['p'][0]:.0%}, 기대값={st['ev']:.2f}")

        s = input("그 칸의 실제 값(0/1/2/3), q로 종료: ").strip().lower()
        if s.lower() == 'q':
            print("사용자 종료."); break
        try:
            v = int(s)
            if v not in (0,1,2,3): raise ValueError
        except:
            print("⚠️ 0~3 입력."); continue

        opened[best_rc] = v
        step += 1

        if v == 0:
            print("💣 폭탄! 게임 오버."); break
        # 성공 여부(모든 2/3 회수)는 사용자 판단

if __name__ == "__main__":
    interactive_game()