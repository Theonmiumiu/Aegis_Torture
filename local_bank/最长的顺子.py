"""
题目名称：最长的顺子 (Longest Straight)
题目来源：根据用户上传的图片整理（斗地主残局模拟）

【题目描述】
斗地主起源于湖北十堰房县，据传是一位叫吴修全的年轻人根据当地流行的扑克玩法“跑得快”改编的。
现在我们需要模拟一个场景：已知你手上的牌和已经出过的牌，请推测对手可能构成的“最长顺子”。

【牌型规则】
1. 单顺（又称顺子）：最少 5 张牌，最多 12 张牌（3-A）。
2. 顺子中不能包含数字 '2'，也不能包含大小王（B 和 C）。
3. 不计花色。
4. 可用的牌及其大小顺序：3 < 4 < 5 < 6 < 7 < 8 < 9 < 10 < J < Q < K < A。
5. 每种牌（除大小王外）有 4 种花色（即最多 4 张）；大小王各 1 张（共 2 张）。

【任务】
输入 1：手上已有的牌
输入 2：已经出过的牌
输出：对手可能构成的最长的顺子。
      - 如果有相同长度的顺子，输出牌面最大的那一个。
      - 如果无法构成顺子，则输出 "NO-CHAIN"。

【输入描述】
第一行：当前手中的牌，牌与牌之间用 '-' 隔开（如 3-3-3-4-5）。
第二行：已经出过的牌，牌与牌之间用 '-' 隔开。

【输出描述】
最长的顺子，牌与牌之间用 '-' 隔开。

【示例 1】
输入：
3-3-3-3-4-4-5-5-6-7-8-9-10-J-Q-K-A
4-5-6-7-8-8-8
输出：
9-10-J-Q-K-A

【示例 2】
输入：
3-3-3-3-8-8-8-8
K-K-K-K
输出：
NO-CHAIN
说明：剩余的牌无法构成长度至少为 5 的顺子。
"""

import sys


def solve():
    # 定义合法的顺子牌面顺序（不含2和大小王）
    # 注意：'10' 在输入中可能是字符串 '10'
    pai_order = ['3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A']

    # 初始化一副完整的牌
    # 3-A 各 4 张，2 各 4 张，小王(B) 1 张，大王(C) 1 张
    card_counts = {p: 4 for p in pai_order}
    card_counts['2'] = 4
    card_counts['B'] = 1
    card_counts['C'] = 1

    # 读取输入
    try:
        my_hand_str = sys.stdin.readline().strip()
        played_cards_str = sys.stdin.readline().strip()

        if not my_hand_str or not played_cards_str:
            # 如果输入不完整，视具体情况处理，此处默认返回
            return

        my_hand = my_hand_str.split('-')
        played_cards = played_cards_str.split('-')

        # 从完整牌堆中减去已知的牌
        for card in my_hand:
            if card in card_counts:
                card_counts[card] -= 1
        for card in played_cards:
            if card in card_counts:
                card_counts[card] -= 1

    except EOFError:
        return

    # 寻找最长顺子
    # 策略：遍历所有可能的长度 L (12 down to 5)
    # 对于每个长度，从最大的起始位置开始找，找到的第一个即为满足“最长且面值最大”的顺子

    max_len = 0
    best_start_idx = -1

    # 参考图片中的双重循环逻辑：
    # 外层循环：顺子的长度（从 5 到 12）
    # 内层循环：顺子的起始位置
    for length in range(5, 13):  # 长度从 5 到 12
        for i in range(len(pai_order) - length + 1):  # 起始索引
            # 检查从 i 开始，长度为 length 的区间内，是否每一张牌都至少还有一张
            is_valid = True
            for j in range(i, i + length):
                if card_counts[pai_order[j]] <= 0:
                    is_valid = False
                    break

            if is_valid:
                # 按照题目要求：如果有相同长度的顺子，输出牌面最大的。
                # 这里的循环顺序是长度从小到大，起始位置从低到高。
                # 所以我们只要不断更新 max_len 和 result 即可。
                # 只有当长度大于等于当前最大长度时才更新。
                if length >= max_len:
                    max_len = length
                    best_start_idx = i

    # 输出结果
    if max_len == 0:
        print("NO-CHAIN")
    else:
        res_chain = []
        for i in range(best_start_idx, best_start_idx + max_len):
            res_chain.append(pai_order[i])
        print("-".join(res_chain))


if __name__ == "__main__":
    solve()

"""
【逻辑分析】
1. **牌库初始化**：题目隐含了对手手中的牌是从“一副牌”扣除“我方手牌”和“已出牌”后剩下的。
   标准的斗地主牌库是 54 张，但顺子只涉及 3-A。
2. **贪心与穷举**：
   - 顺子的长度范围是 [5, 12]。
   - 由于需要“最长”且“面值最大”，我们遍历所有可能的子序列。
   - 图片中的代码采用了从短到长的遍历方式 `range(5, 13)`，并在找到合法序列时记录。
   - 这种方式通过不断“覆盖”旧的结果来保留最新（即最长、最靠后/最大）的序列。
3. **细节处理**：
   - '10' 是两个字符，但在分割时被视为一个元素，处理时需注意。
   - 输入为空或格式不正确时的异常处理（虽然在线评测通常输入是规范的）。
"""