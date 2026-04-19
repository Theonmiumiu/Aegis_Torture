"""
题目名称：士兵的任务2
题目来源：根据用户上传的图片整理

【题目描述】
士兵在迷宫中执行任务，迷宫中危机重重，他需要在最短的时间内到达指定的位置。
请计算士兵从起点到达终点最少需要花费多少单位时间。

【迷宫元素说明】
- 0：路（行走花费 1 个单位时间）
- 1：墙（不可通过，除非被炸弹炸毁）
- 2：起点（士兵的初始位置）
- 3：终点（目标位置）
- 4：陷阱（行走花费 3 个单位时间）
- 6：炸弹（激活后会将上下左右相邻的“墙”炸毁变为“路”）

【特殊规则】
1. 移动方向：上、下、左、右四个方向移动。
2. 炸弹规则：炸弹只能销毁墙（1），不会炸掉陷阱（4）。
3. 消耗规则：炸弹、陷阱触发后即失效（在最短路搜索中，通常视为经过该点即产生代价）。
4. 炸弹激活：当士兵站在炸弹（6）所在格点时，其周围相邻的墙变为可通行的路。
5. 迷宫大小：最大为 25 * 25。
6. 保证有解：用例保证士兵一定能到达终点。

【输入描述】
第一行：n 和 m，表示迷宫的行数和列数。
第二行开始：n * m 的矩阵，表示迷宫布局。

【输出描述】
输出一个整数，表示最少需要的单位时间。

【样例 1】
输入：
4 4
1 1 1 1
1 6 2 1
1 1 0 1
1 3 1 1
输出：
3
解释：起点在 (1, 2)，左移到 (1, 1) 的炸弹上（耗时 1），炸掉周围的墙。
随后向下走两步 (2, 1) -> (3, 1) 到达终点（耗时 2），总共 3。

【样例 2】
输入：
8 4
1 6 2 1
1 1 0 1
1 1 0 1
1 1 0 1
1 1 0 1
1 1 0 1
1 1 0 1
1 1 3 1
输出：
7
解释：直接向下移动 7 步即可到达终点。
"""

import heapq
import sys


def solve():
    # 读取 n 和 m
    input_data = sys.stdin.read().split()
    if not input_data:
        return

    n = int(input_data[0])
    m = int(input_data[1])

    grid = []
    idx = 2
    start_pos = None
    end_pos = None

    for r in range(n):
        row = []
        for c in range(m):
            val = int(input_data[idx])
            row.append(val)
            if val == 2:
                start_pos = (r, c)
            elif val == 3:
                end_pos = (r, c)
            idx += 1
        grid.append(row)

    # Dijkstra 算法准备
    # pq 存储 (时间, x, y)
    pq = [(0, start_pos[0], start_pos[1])]
    # dist 存储到达每个点的最小时间
    dist = {}  # (x, y) -> min_time

    directions = [(0, 1), (0, -1), (1, 0), (-1, 0)]

    while pq:
        time, x, y = heapq.heappop(pq)

        # 如果当前时间已经大于记录的最小时间，跳过
        if (x, y) in dist and time >= dist[(x, y)]:
            continue
        dist[(x, y)] = time

        # 到达终点
        if (x, y) == end_pos:
            print(time)
            return

        for dx, dy in directions:
            nx, ny = x + dx, y + dy

            if 0 <= nx < n and 0 <= ny < m:
                cell_type = grid[nx][ny]

                # 核心逻辑判断：能否进入目标格 nx, ny
                move_cost = -1

                # 情况 A：目标是普通路、起点、终点或炸弹
                if cell_type in (0, 2, 3, 6):
                    move_cost = 1

                # 情况 B：目标是陷阱
                elif cell_type == 4:
                    move_cost = 3

                # 情况 C：目标是墙
                elif cell_type == 1:
                    # 只有当前位置是炸弹 (6) 时，墙才可通行
                    if grid[x][y] == 6:
                        move_cost = 1
                    else:
                        continue  # 墙不可通过

                if move_cost != -1:
                    new_time = time + move_cost
                    if (nx, ny) not in dist or new_time < dist[(nx, ny)]:
                        heapq.heappush(pq, (new_time, nx, ny))


if __name__ == "__main__":
    solve()

"""
【逻辑分析】
1. **Dijkstra 算法**：
   因为移动代价不唯一（普通格为 1，陷阱为 3），这属于带权图的最短路径问题。
   普通的 BFS 只能处理权值相等的图，因此必须使用优先队列（Priority Queue）实现的 Dijkstra。

2. **炸弹毁墙的判定**：
   根据题目描述和图片中的 C++ 代码，炸弹是在“激活”后起作用的。
   逻辑实现上：当我们尝试从 (x, y) 移动到 (nx, ny) 时，如果 (nx, ny) 是墙，
   我们需要检查士兵“当前所在的位置” (x, y) 是不是炸弹 (6)。
   如果是，说明墙被炸毁了，可以通过，耗时 1。

3. **空间与时间复杂度**：
   - 地图最大为 25x25 = 625 个节点。
   - Dijkstra 复杂度为 O(E log V)，在此规模下瞬时即可完成。
"""