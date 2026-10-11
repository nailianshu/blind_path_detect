#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""练习二：User 类、Admin 子类及其调用演示。

    1. 定义 User 类：first_name / last_name / describe_user() / greet_user()
    2. 定义 Admin 类继承 User：privileges 属性 / show_privileges()
    3. 创建 Admin 实例，调用它的所有方法
"""

class User:
    """一个普通用户。"""

    def __init__(self, first_name, last_name):
        """初始化用户名。

        参数:
            first_name: 名
            last_name:  姓
        """
        self.first_name = first_name
        self.last_name = last_name

    def describe_user(self):
        """打印该用户的信息。"""
        print("用户信息：{0} {1}".format(self.first_name, self.last_name))

    def greet_user(self):
        """打印问候语。"""
        print("你好，{0} {1}，欢迎回来！".format(self.first_name, self.last_name))


class Admin(User):
    """管理员：一种拥有额外权限的特殊用户。"""

    def __init__(self, first_name, last_name, privileges=None):
        """初始化管理员。

        参数:
            first_name: 名
            last_name:  姓
            privileges: 权限列表；不传则使用默认权限
        """
        # 复用父类的初始化逻辑，避免重复代码
        super().__init__(first_name, last_name)

        if privileges is None:
            self.privileges = [
                "can add post",
                "can delete post",
                "can ban user",
            ]
        else:
            self.privileges = list(privileges)

    def show_privileges(self):
        """显示管理员拥有的权限。"""
        print("{0} {1} 的权限如下：".format(self.first_name, self.last_name))
        for index, privilege in enumerate(self.privileges, start=1):
            print("  {0}. {1}".format(index, privilege))


def main():
    """创建 Admin 实例，并调用它的所有方法。"""
    admin = Admin("Li", "Hua")

    print("=" * 36)
    print("调用 admin.describe_user()")
    admin.describe_user()

    print("-" * 36)
    print("调用 admin.greet_user()")
    admin.greet_user()

    print("-" * 36)
    print("调用 admin.show_privileges()")
    admin.show_privileges()
    print("=" * 36)


if __name__ == "__main__":
    main()
