# coding=utf-8
import os
# 单个判题端最多同时运行的程序个数，因为判题端会同时运行多组测试数据，比如一共有5组测试数据
# 如果MAX_RUNNING_NUMBER大于等于5，那么这5组数据就会同时进行评测，然后返回结果。
# 如果MAX_RUNNING_NUMBER小于5，为3，那么就会同时运行前三组测试数据，然后再运行后两组数据
# 这样可以避免同时运行的程序过多导致的cpu占用太高
max_running_number = 10

# lrun运行用户的uid
lrun_uid = 1001

# lrun用户组gid
lrun_gid = 1002

# judger工作目录
judger_workspace = "/var/judger/"

submission_db = {
    "host": os.environ.get("MYSQL_PORT_3306_TCP_ADDR", "127.0.0.1"),
    "port": 3306,
    "db": "oj_submission",
    "user": "root",
    "password": os.environ.get("MYSQL_ENV_MYSQL_ROOT_PASSWORD", "root")
}
