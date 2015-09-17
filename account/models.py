# coding=utf-8
from django.db import models
from django.contrib.auth.models import AbstractBaseUser


class AdminGroup(models.Model):
    pass


class UserManager(models.Manager):
    use_in_migrations = True

    def get_by_natural_key(self, username):
        return self.get(**{self.model.USERNAME_FIELD: username})


REGULAR_USER = 0
ADMIN = 1
SUPER_ADMIN = 2


class User(AbstractBaseUser):
    # 用户名
    username = models.CharField(max_length=30, unique=True)
    # 真实姓名
    real_name = models.CharField(max_length=30, blank=True, null=True)
    # 用户邮箱
    email = models.EmailField(max_length=254, blank=True, null=True)
    # 用户注册时间
    create_time = models.DateTimeField(auto_now_add=True)
    # 0代表不是管理员 1是普通管理员 2是超级管理员
    admin_type = models.IntegerField(default=0)
    # JSON字典用来表示该用户的问题的解决状态 1为ac，2为正在进行
    problems_status = models.TextField(default="{}")

    USERNAME_FIELD = 'username'
    REQUIRED_FIELDS = []

    objects = UserManager()

    class Meta:
        db_table = "user"
