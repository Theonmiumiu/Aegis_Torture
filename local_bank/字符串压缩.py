"""
题目名称：字符串压缩 (String Compression / Word Index Replacement)
题目来源：根据用户上传的图片整理

【题目描述】
给定一段英文句子和一个英文单词列表。
英文句子包含英文单词和标点符号，其中：
1. 英文单词只包含 [a-zA-Z] 范围内的字符。
2. 标点符号包括逗号 (,)、句号 (.)、双引号 (")。
   注意：双引号两边至少有一个空格。

替换规则：
1. 如果列表中的单词在句子中存在（大小写不敏感），且该单词未被双引号包含，
   则使用该单词在列表中的索引值（索引值从 0 开始）代替句子中的该单词。
2. 如果英文单词列表中存在重复的英文单词，则以该单词最后一次出现的索引值进行替换。
3. 如果单词在双引号内，则保持原样，不进行替换。

【输入描述】
第一行：一段英文句子。
第二行：英文单词列表，单词之间以空格分隔。

【提示】
- 每个英文单词长度在 [1, 50] 范围内。
- 输入的英文句子长度在 [0, 10000] 范围内。
- 输入的英文单词列表长度在 [0, 100000] 范围内。
- 英文句子中不会出现双引号不匹配的情况。

【输出描述】
替换后的英文句子。

【示例 1】
输入：
Hello world.
Good Hello LOOP
输出：
1 world.
解释：hello 在列表中存在（索引 1），且不在双引号内，替换为 1。

【示例 2】
输入：
An introduction is " the first paragraph " of your paper.
what say first Second IS introduction IS end
输出：
An 5 6 " the first paragraph " of your paper.
解释：
- introduction 是索引 5，IS 是索引 6（IS 出现了两次，取最后一次索引 6）。
- first 虽然在句子中，但由于被双引号包围了，所以不替换。
"""

import sys


def solve():
    # 读取输入
    # 由于句子和单词列表可能包含空格，使用 sys.stdin 确保读取完整行
    sentence = sys.stdin.readline().rstrip('\n')
    word_list_line = sys.stdin.readline().rstrip('\n')

    if not sentence:
        print("")
        return

    # 1. 处理单词列表，建立映射
    # 规则：大小写不敏感，重复单词取最后一次出现的索引
    word_to_index = {}
    words_in_list = word_list_line.split()
    for idx, w in enumerate(words_in_list):
        word_to_index[w.lower()] = str(idx)

    # 2. 遍历句子并进行处理
    res = []
    i = 0
    n = len(sentence)
    in_quotes = False  # 追踪是否在双引号内

    while i < n:
        char = sentence[i]

        # 处理双引号标记
        if char == '"':
            in_quotes = not in_quotes
            res.append(char)
            i += 1
            continue

        # 如果当前是字母，说明是一个单词的开始
        if char.isalpha():
            start = i
            while i < n and sentence[i].isalpha():
                i += 1
            word = sentence[start:i]

            # 检查替换条件：不在引号内 且 在字典中
            if not in_quotes and word.lower() in word_to_index:
                res.append(word_to_index[word.lower()])
            else:
                res.append(word)
        else:
            # 标点符号或空格，直接原样添加
            res.append(char)
            i += 1

    # 输出结果
    print("".join(res))


if __name__ == "__main__":
    solve()

"""
【逻辑分析】
1. **索引映射**：
   使用 Python 字典存储 `word.lower() -> index`。因为是顺序遍历列表，
   后出现的相同单词会自动覆盖掉之前的索引，完美符合“取最后一次出现”的规则。

2. **状态机思想**：
   引入 `in_quotes` 布尔值。每当遇到 `"` 字符，就翻转这个布尔值。
   单词只有在 `in_quotes` 为 `False` 时才考虑替换。

3. **分词处理**：
   不建议直接使用 `sentence.split()`，因为这样会破坏标点符号（如句号和逗号）的相对位置。
   采用“指针扫描”法（while 循环），遇到字母则识别为单词，遇到非字母则视为分隔符或标点。
   这种方法能保证输出的格式（空格、标点）与原句子完全一致。

4. **复杂度**：
   - 建立索引：O(L)，L 为单词列表总字符数。
   - 扫描句子：O(S)，S 为句子总字符数。
   - 总时间复杂度：O(L + S)，非常高效，能够满足题目中的大数据量要求。
"""