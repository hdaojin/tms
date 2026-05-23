from __future__ import annotations

import argparse
import os
import random
import sys
from datetime import timedelta
from io import BytesIO
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

# 统一切回项目根目录，避免 .env 中的相对路径随当前工作目录变化。
os.chdir(BASE_DIR)

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "tmsproject.settings")

import django

django.setup()

from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.utils import timezone

from competition_standards.models import StandardModule, StandardModuleSet, TrainingCycle
from traininglogs.models import TrainingLog


TASK_TOPICS = [
    "Linux 服务巡检",
    "交换机 VLAN 配置",
    "路由策略调试",
    "虚拟化环境部署",
    "容器网络联通测试",
    "数据库主从同步检查",
    "Nginx 反向代理配置",
    "Windows 域服务维护",
    "日志采集链路排查",
    "备份恢复演练",
]


def positive_int(value: str) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("数量必须为正整数")
    return parsed


def non_negative_int(value: str) -> int:
    parsed = int(value)
    if parsed < 0:
        raise argparse.ArgumentTypeError("天数范围不能为负数")
    return parsed


def escape_pdf_text(value: str) -> str:
    return value.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def build_pdf_bytes(lines: list[str]) -> bytes:
    content_lines = ["BT", "/F1 12 Tf", "50 780 Td"]
    for index, line in enumerate(lines):
        if index > 0:
            content_lines.append("0 -18 Td")
        content_lines.append(f"({escape_pdf_text(line)}) Tj")
    content_lines.append("ET")

    stream = "\n".join(content_lines).encode("latin-1", errors="ignore")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        (
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
            b"/Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>"
        ),
        b"<< /Length " + str(len(stream)).encode("ascii") + b" >>\nstream\n" + stream + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]

    buffer = BytesIO()
    buffer.write(b"%PDF-1.4\n")

    offsets = [0]
    for index, obj in enumerate(objects, start=1):
        offsets.append(buffer.tell())
        buffer.write(f"{index} 0 obj\n".encode("ascii"))
        buffer.write(obj)
        buffer.write(b"\nendobj\n")

    xref_start = buffer.tell()
    buffer.write(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
    buffer.write(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        buffer.write(f"{offset:010d} 00000 n \n".encode("ascii"))

    buffer.write(
        (
            f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
            f"startxref\n{xref_start}\n%%EOF\n"
        ).encode("ascii")
    )
    return buffer.getvalue()


def choose_or_none(items: list[object], rng: random.Random):
    if not items:
        return None
    return rng.choice(items)


def build_uploaded_by_plan(users: list[object], count: int, rng: random.Random) -> list[object | None]:
    if not users:
        return [None] * count

    target_count = count
    if count < len(users):
        target_count = len(users)
        print(
            f"指定数量 {count} 小于用户数 {len(users)}，已自动调整为 {target_count}，"
            "以保证每个用户至少有一条日志。"
        )

    planned_users: list[object | None] = []
    while len(planned_users) < target_count:
        current_round = list(users)
        rng.shuffle(current_round)
        planned_users.extend(current_round)

    return planned_users[:target_count]


def build_task(module: StandardModule | None, rng: random.Random) -> str:
    topic = rng.choice(TASK_TOPICS)
    if module is None:
        return topic[:100]
    return f"{module.code} {topic}"[:100]


def build_file_content(index: int, training_date, task: str) -> ContentFile:
    lines = [
        "TrainingLog Test Data",
        f"Record: {index}",
        f"Date: {training_date.isoformat()}",
        f"Task: {task}",
    ]
    return ContentFile(build_pdf_bytes(lines), name=f"traininglog-test-{index:04d}.pdf")


def build_test_cycle_code(module_set: StandardModuleSet) -> str:
    project = module_set.project
    base_code = f"TEST-{project.code}-{module_set.code}"[:50]
    candidate = base_code
    suffix = 2
    while TrainingCycle.objects.filter(code=candidate).exists():
        suffix_text = f"-{suffix}"
        candidate = f"{base_code[:50 - len(suffix_text)]}{suffix_text}"
        suffix += 1
    return candidate


def get_or_create_training_cycles() -> list[TrainingCycle]:
    cycles = list(
        TrainingCycle.objects.select_related("project", "module_set")
        .order_by("-start_date", "id")
    )
    if cycles:
        return cycles

    module_set = (
        StandardModuleSet.objects.select_related("project")
        .order_by("-is_current", "sort_order", "id")
        .first()
    )
    if module_set is None:
        raise SystemExit("未找到训练周期或标准模块版本，无法创建训练日志测试数据。")

    today = timezone.localdate()
    cycle = TrainingCycle.objects.create(
        code=build_test_cycle_code(module_set),
        name=f"{module_set.project.name} 测试训练周期"[:100],
        project=module_set.project,
        module_set=module_set,
        start_date=today,
        status=TrainingCycle.Status.ACTIVE,
        description="由测试数据脚本自动创建。",
    )
    print(f"未找到训练周期，已自动创建：{cycle}")
    return [cycle]


def build_modules_by_cycle(cycles: list[TrainingCycle]) -> dict[int, list[StandardModule]]:
    modules_by_set: dict[int, list[StandardModule]] = {}
    for module in StandardModule.objects.filter(
        module_set_id__in=[cycle.module_set_id for cycle in cycles]
    ).select_related("module_set").order_by("module_set_id", "sort_order", "id"):
        modules_by_set.setdefault(module.module_set_id, []).append(module)
    return {
        cycle.pk: modules_by_set.get(cycle.module_set_id, [])
        for cycle in cycles
    }


def choose_unique_slot(
    cycles: list[TrainingCycle],
    uploaded_by,
    today,
    days_back: int,
    rng: random.Random,
    used_keys: set[tuple[int, int | None, object]],
) -> tuple[TrainingCycle, object]:
    uploaded_by_id = uploaded_by.pk if uploaded_by else None
    for _attempt in range(100):
        cycle = rng.choice(cycles)
        training_date = today - timedelta(days=rng.randint(0, days_back))
        key = (cycle.pk, uploaded_by_id, training_date)
        if key not in used_keys:
            used_keys.add(key)
            return cycle, training_date

    offset = days_back + 1
    while True:
        for cycle in cycles:
            training_date = today - timedelta(days=offset)
            key = (cycle.pk, uploaded_by_id, training_date)
            if key not in used_keys:
                used_keys.add(key)
                return cycle, training_date
        offset += 1


def create_traininglogs(count: int, days_back: int, seed: int | None) -> int:
    rng = random.Random(seed)
    today = timezone.localdate()

    user_model = get_user_model()
    users = [user for user in user_model.objects.order_by("id") if hasattr(user, "display_name")]
    training_cycles = get_or_create_training_cycles()
    modules_by_cycle = build_modules_by_cycle(training_cycles)
    uploaded_by_plan = build_uploaded_by_plan(users, count, rng)
    used_keys = {
        (training_cycle_id, uploaded_by_id, training_date)
        for training_cycle_id, uploaded_by_id, training_date in TrainingLog.objects.values_list(
            "training_cycle_id",
            "uploaded_by_id",
            "training_date",
        )
    }

    if not users:
        print("未找到可用用户，将创建 uploaded_by 为空的训练日志。")
    if not any(modules_by_cycle.values()):
        print("所选训练周期没有可用标准模块，将创建 module 为空的训练日志。")

    created = 0
    for index, uploaded_by in enumerate(uploaded_by_plan, start=1):
        training_cycle, training_date = choose_unique_slot(
            training_cycles,
            uploaded_by,
            today,
            days_back,
            rng,
            used_keys,
        )
        module = choose_or_none(modules_by_cycle.get(training_cycle.pk, []), rng)
        task = build_task(module, rng)

        training_log = TrainingLog(
            training_cycle=training_cycle,
            module=module,
            task=task,
            training_date=training_date,
            uploaded_by=uploaded_by,
            file=build_file_content(index, training_date, task),
        )
        training_log.full_clean()
        training_log.save()
        created += 1

    return created


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="创建 traininglogs app 的测试数据")
    parser.add_argument(
        "count",
        nargs="?",
        type=positive_int,
        default=10,
        help="计划创建的训练日志总数，默认 10；若小于用户数，会自动提升到用户数",
    )
    parser.add_argument(
        "--days-back",
        type=non_negative_int,
        default=60,
        help="训练日期向前随机回溯的天数范围，默认 60",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="随机种子，传入后可复现同一批测试数据",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    created = create_traininglogs(args.count, args.days_back, args.seed)
    print(f"成功创建 {created} 条训练日志测试数据。")


if __name__ == "__main__":
    main()
