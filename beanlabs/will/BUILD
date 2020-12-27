package(default_visibility = ["//visibility:public"])

py_library(
    name = "will",
    srcs = ["will.py"],
    deps = [
        "//beancount/core:account",
        "//beancount/core:account_types",
        "//beancount/core:convert",
        "//beancount/core:data",
        "//beancount/core:getters",
        "//beancount/core:realization",
        "//beancount:loader",
        "//beancount/parser:options",
        "//beancount/parser:version",
    ],
)

py_test(
    name = "will_test",
    srcs = ["will_test.py"],
    deps = [
        "//beancount/core:getters",
        "//beancount:loader",
        "//beancount/projects:will",
        "//beancount/utils:test_utils",
        "//beancount:plugins_for_tests",
    ],
)
