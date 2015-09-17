# coding=utf-8
import json
from datetime import datetime
import redis
import pytz
from django.shortcuts import render
from django.core.paginator import Paginator
from django.utils import timezone
from rest_framework.views import APIView

from judge.judger_controller.tasks import judge
from judge.judger_controller.settings import redis_config

from account.decorators import login_required
from account.models import SUPER_ADMIN

from contest.decorators import check_user_contest_permission
from problem.models import Problem
from contest.models import Contest, ContestProblem

from utils.shortcuts import serializer_invalid_response, error_response, success_response, error_page, paginate
from submission.models import Submission
from .serializers import CreateContestSubmissionSerializer
from submission.serializers import SubmissionSerializer


class ContestSubmissionAPIView(APIView):
    @check_user_contest_permission
    def post(self, request):
        """
        创建比赛的提交
        ---
        request_serializer: CreateContestSubmissionSerializer
        """
        serializer = CreateContestSubmissionSerializer(data=request.data)
        if serializer.is_valid():
            data = serializer.data
            contest = Contest.objects.get(id=data["contest_id"])
            try:
                problem = ContestProblem.objects.get(contest=contest, id=data["problem_id"])
                # 更新题目提交计数器
                problem.total_submit_number += 1
                problem.save()
            except ContestProblem.DoesNotExist:
                return error_response(u"题目不存在")
            submission = Submission.objects.create(user_id=request.user.id, language=int(data["language"]),
                                                   contest_id=contest.id, code=data["code"], problem_id=problem.id)
            try:
                judge.delay(submission.id, problem.time_limit, problem.memory_limit, problem.test_case_id)
            except Exception:
                return error_response(u"提交判题任务失败")
            # 增加redis 中判题队列长度的计数器
            r = redis.Redis(host=redis_config["host"], port=redis_config["port"], db=redis_config["db"])
            r.incr("judge_queue_length")
            return success_response({"submission_id": submission.id})
        else:
            return serializer_invalid_response(serializer)


@login_required
def contest_problem_my_submissions_list_page(request, contest_id, contest_problem_id):
    """
    我比赛单个题目的所有提交列表
    """
    try:
        Contest.objects.get(id=contest_id)
    except Contest.DoesNotExist:
        return error_page(request, u"比赛不存在")
    try:
        contest_problem = ContestProblem.objects.get(id=contest_problem_id, visible=True)
    except ContestProblem.DoesNotExist:
        return error_page(request, u"比赛问题不存在")
    submissions = Submission.objects.filter(user_id=request.user.id, problem_id=contest_problem.id).order_by(
        "-create_time"). \
        values("id", "result", "create_time", "accepted_answer_time", "language")
    return render(request, "oj/contest/my_submissions_list.html",
                  {"submissions": submissions, "problem": contest_problem})


@check_user_contest_permission
def contest_problem_submissions_list_page(request, contest_id, page=1):
    """
    单个比赛中的所有提交（包含自己和别人，自己可查提交结果，其他人不可查）
    """
    try:
        contest = Contest.objects.get(id=contest_id)
    except Contest.DoesNotExist:
        return error_page(request, u"比赛不存在")

    submissions = Submission.objects.filter(contest_id=contest_id).\
        values("id", "contest_id", "problem_id", "result", "create_time",
               "accepted_answer_time", "language", "user_id").order_by("-create_time")


    # 封榜的时候只能看到自己的提交
    if not contest.real_time_rank:
        if not (request.user.admin_type == SUPER_ADMIN or request.user == contest.created_by):
            submissions = submissions.filter(user_id=request.user.id)

    language = request.GET.get("language", None)
    filter = None
    if language:
        submissions = submissions.filter(language=int(language))
        filter = {"name": "language", "content": language}
    result = request.GET.get("result", None)
    if result:
        submissions = submissions.filter(result=int(result))
        filter = {"name": "result", "content": result}
    paginator = Paginator(submissions, 20)

    # 为查询题目标题创建新字典
    title = {}
    contest_problems = ContestProblem.objects.filter(contest=contest)
    for item in contest_problems:
        title[item.id] = item.title
    for item in submissions:
        item['title'] = title[item['problem_id']]

    try:
        current_page = paginator.page(int(page))
    except Exception:
        return error_page(request, u"不存在的页码")
    previous_page = next_page = None
    try:
        previous_page = current_page.previous_page_number()
    except Exception:
        pass
    try:
        next_page = current_page.next_page_number()
    except Exception:
        pass

    for item in current_page:
        # 自己提交的 管理员和创建比赛的可以看到所有的提交链接
        if item["user_id"] == request.user.id or request.user.admin_type == SUPER_ADMIN or \
                        request.user == contest.created_by:
            item["show_link"] = True
        else:
            item["show_link"] = False

    return render(request, "oj/contest/submissions_list.html",
                  {"submissions": current_page, "page": int(page),
                   "previous_page": previous_page, "next_page": next_page, "start_id": int(page) * 20 - 20,
                   "contest": contest, "filter": filter})


class ContestSubmissionAdminAPIView(APIView):
    def get(self, request):
        """
        查询比赛提交,单个比赛题目提交的adminAPI
        ---
        response_serializer: SubmissionSerializer
        """
        problem_id = request.GET.get("problem_id", None)
        contest_id = request.GET.get("contest_id", None)
        if contest_id:
            try:
                contest = Contest.objects.get(pk=contest_id)
            except Contest.DoesNotExist:
                return error_response(u"比赛不存在!")
            if request.user.admin_type != SUPER_ADMIN and contest.created_by != request.user:
                return error_response(u"您无权查看该信息!")
            submissions = Submission.objects.filter(contest_id=contest_id).order_by("-create_time")
        else:
            if problem_id:
                try:
                    contest_problem = ContestProblem.objects.get(pk=problem_id)
                except ContestProblem.DoesNotExist:
                    return error_response(u"问题不存在!")
                if request.user.admin_type != SUPER_ADMIN and contest_problem.contest.created_by != request.user:
                    return error_response(u"您无权查看该信息!")
                submissions = Submission.objects.filter(contest_id=contest_problem.contest_id).order_by("-create_time")
            else:
                return error_response(u"参数错误!")
        if problem_id:
            submissions = submissions.filter(problem_id=problem_id)
        return paginate(request, submissions, SubmissionSerializer)
