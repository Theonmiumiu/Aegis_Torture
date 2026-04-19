"""
题目名称：服务故障传播
题目来源：根据用户上传的图片整理

【题目描述】
某系统中有很多服务，每个服务用字符串（只包含字母和数字，长度 <= 10）表示，作为唯一标识。
服务之间可能存在依赖关系，例如：如果 A 依赖 B，则当 B 故障时会导致 A 也故障。
依赖关系具有传递性，例如：A 依赖 B，B 依赖 C，当 C 故障时会导致 B 故障，进而也导致 A 故障。

给定所有的依赖关系以及当前已知故障的服务列表，请输出所有正常工作的服务。

【输入描述】
1. 第一行：半角逗号分隔的依赖关系列表。
   格式为 "服务1-服务2"，表示“服务1”依赖“服务2”。
2. 第二行：半角逗号分隔的已知故障服务列表。

【输出描述】
1. 输出所有可以正常工作的服务列表，以半角逗号分隔。
2. 排序规则：按照服务在依赖关系列表中出现的先后顺序进行排序。
3. 特别说明：如果没有正常节点，输出一个单独的半角逗号 ","。

【约束条件】
- 依赖关系列表和故障列表非空。
- 依赖关系数不超过 3000。
- 服务总数不超过 1000。

【示例 1】
输入：
a1-a2,a5-a6,a2-a3
a5,a2

输出：
a6,a3

解析：
- 依赖链：a1 -> a2 -> a3，a5 -> a6。
- 初始故障：a5, a2。
- 故障传播：
  - a2 故障导致依赖它的 a1 故障。
  - a5 故障（a5 依赖 a6，但 a6 本身不依赖 a5，所以 a6 正常）。
- 最终故障：a1, a2, a5。
- 正常服务：a6, a3。按出现顺序输出：a6, a3。
"""

import sys


def solve():
    # 读取输入
    try:
        line1 = sys.stdin.readline().strip()
        line2 = sys.stdin.readline().strip()
        if not line1:
            return

        relations = line1.split(',')
        initial_failed = line2.split(',')
    except EOFError:
        return

    # mapp: 存储反向依赖，即 {被依赖服务: [依赖它的服务列表]}
    # status: 存储服务状态，1 表示正常，0 表示故障
    # order_keys: 记录服务出现的顺序
    mapp = {}
    status = {}
    order_keys = []

    # 解析依赖关系
    for rel in relations:
        # b[0] 依赖 b[1]
        b = rel.split('-')
        if len(b) != 2:
            continue

        u, v = b[0], b[1]

        # 构建反向邻接表：v 故障会影响 u
        if v not in mapp:
            mapp[v] = set()
        mapp[v].add(u)

        # 初始化 mapp 中可能不存在的节点
        if u not in mapp:
            mapp[u] = set()

        # 记录服务出现的顺序并初始化状态
        for node in [u, v]:
            if node not in status:
                status[node] = 1
                order_keys.append(node)

    # 故障传播 (使用 BFS)
    queue = []
    # 首先处理初始故障列表
    for item in initial_failed:
        if item in status:
            queue.append(item)

    while queue:
        current = queue.pop(0)
        # 如果当前节点还被标记为正常，则将其设为故障并传播
        if status.get(current) == 1:
            status[current] = 0
            # 找到所有依赖当前故障服务的上游服务
            if current in mapp:
                for dependent in mapp[current]:
                    if status.get(dependent) == 1:
                        queue.append(dependent)
        elif current not in status:
            # 如果初始故障节点不在依赖列表中，直接忽略或处理
            pass

    # 收集正常服务
    result = []
    for key in order_keys:
        if status[key] == 1:
            result.append(key)

    # 输出结果
    if not result:
        print(",")
    else:
        print(",".join(result))


if __name__ == "__main__":
    solve()

"""
【代码逻辑解析】
1. 解析输入：将 "a1-a2" 拆解。
2. 构建关系：本题的关键是方向。A 依赖 B，表示 B 坏了 A 就会坏。
   所以我们建立 B -> A 的映射。
3. 状态管理：用字典记录每个节点的生命值（1 或 0）。
4. 顺序保持：题目要求按“出现顺序”输出。
   我们在解析第一行输入时，第一次见到某个服务名就把它存入 `order_keys` 列表。
5. 边界处理：如果没有正常节点，按照题目要求输出单个逗号。
"""