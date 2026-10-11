#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""练习一：计算列表的最大嵌套深度。

任务边界（本程序只做这一件事）：
    1. 实现 max_nesting_depth() 函数
    2. 用 unittest 编写并执行单元测试

约定：
    - 非列表元素（如 1、"a"）本身不构成嵌套，深度记 0
    - 空列表 [] 视为“位于第 1 层”，深度记 1
    - 扁平列表 [1, 2, 3] 深度为 1
"""

import unittest


def max_nesting_depth(value):
    """返回 value 中列表的最大嵌套深度。

    递归思路：
        - 若 value 不是列表 -> 深度 0（递归的“停止条件”）
        - 若 value 是空列表 -> 深度 1（它本身就是第 1 层）
        - 否则 -> 1 + 子元素中的最大深度

    参数:
        value: 任意对象，通常是一个列表

    返回:
        int: 最大嵌套深度
    """
    # 停止条件一：不是列表，不贡献任何深度
    if not isinstance(value, list):
        return 0

    # 停止条件二：空列表，它自己算第 1 层
    if not value:
        return 1

    # 递归：当前这一层 + 子元素里最深的那个
    child_max = max(max_nesting_depth(item) for item in value)
    return 1 + child_max


class TestMaxNestingDepth(unittest.TestCase):
    """max_nesting_depth() 的单元测试（共 8 个用例）。"""

    def test_flat_list(self):
        """扁平列表：深度为 1。"""
        self.assertEqual(max_nesting_depth([1, 2, 3]), 1)

    def test_two_level(self):
        """两层嵌套：深度为 2。"""
        self.assertEqual(max_nesting_depth([1, [2, 3]]), 2)

    def test_example_from_question(self):
        """题目示例：[[1], [2, [3]]] 深度为 3。"""
        self.assertEqual(max_nesting_depth([[1], [2, [3]]]), 3)

    def test_empty_list(self):
        """空列表：按约定深度为 1。"""
        self.assertEqual(max_nesting_depth([]), 1)

    def test_non_list_input(self):
        """非列表输入：深度为 0。"""
        self.assertEqual(max_nesting_depth(42), 0)
        self.assertEqual(max_nesting_depth("abc"), 0)

    def test_deeply_nested(self):
        """深层嵌套：[[[[1]]]] 深度为 5。"""
        self.assertEqual(max_nesting_depth([[[[[1]]]]]), 5)

    def test_depth_is_max_not_sum(self):
        """取最大值而非累加：[1, [2], [[3]]] 深度为 3。"""
        self.assertEqual(max_nesting_depth([1, [2], [[3]]]), 3)

    def test_mixed_types(self):
        """混合类型：[1, "a", [2, [3, [4]]]] 深度为 4。"""
        self.assertEqual(max_nesting_depth([1, "a", [2, [3, [4]]]]), 4)


if __name__ == "__main__":
    # 直接运行本文件即可执行全部单元测试
    unittest.main(verbosity=2)
