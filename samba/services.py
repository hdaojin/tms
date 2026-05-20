import json
import logging
from base64 import urlsafe_b64encode
from concurrent.futures import ThreadPoolExecutor
from hashlib import sha256

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.db import transaction
from django.utils import timezone

from .models import SambaOperation
from .samba_sync import (
    change_samba_password,
    disable_samba_for_user,
    enable_samba_for_user,
)

logger = logging.getLogger(__name__)

_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix='samba-ops')


class SambaIntegrationDisabled(RuntimeError):
    pass


class SambaOperationConflict(RuntimeError):
    pass


def _get_fernet() -> Fernet:
    configured_key = getattr(settings, 'SAMBA_TASK_ENCRYPTION_KEY', '').strip()
    if configured_key:
        key = configured_key.encode('utf-8')
    else:
        key = urlsafe_b64encode(sha256(settings.SECRET_KEY.encode('utf-8')).digest())

    try:
        return Fernet(key)
    except ValueError as exc:
        raise ImproperlyConfigured('SAMBA_TASK_ENCRYPTION_KEY 不是合法的 Fernet 密钥。') from exc


def _encrypt_payload(payload: dict[str, str]) -> str:
    data = json.dumps(payload, ensure_ascii=False).encode('utf-8')
    return _get_fernet().encrypt(data).decode('utf-8')


def _decrypt_payload(payload_encrypted: str) -> dict[str, str]:
    if not payload_encrypted:
        raise RuntimeError('任务缺少执行载荷，请重新提交。')

    try:
        raw = _get_fernet().decrypt(payload_encrypted.encode('utf-8'))
    except InvalidToken as exc:
        raise RuntimeError('任务载荷无法解密，请重新提交。') from exc

    payload = json.loads(raw.decode('utf-8'))
    if not isinstance(payload, dict):
        raise RuntimeError('任务载荷格式无效，请重新提交。')
    return payload


def ensure_samba_enabled() -> None:
    if not getattr(settings, 'SAMBA_INTEGRATION_ENABLED', True):
        raise SambaIntegrationDisabled('Samba 集成功能当前已关闭，请联系管理员。')


def get_latest_operation_for_user(user):
    return SambaOperation.objects.filter(target_user=user).select_related('created_by').first()


def get_last_known_enabled_state(user) -> bool | None:
    latest_success = SambaOperation.objects.filter(
        target_user=user,
        status=SambaOperation.Status.SUCCEEDED,
    ).first()
    if latest_success is None:
        return None
    return latest_success.action != SambaOperation.Action.DISABLE


def has_pending_operation(user) -> bool:
    return SambaOperation.objects.filter(
        target_user=user,
        status__in=[SambaOperation.Status.QUEUED, SambaOperation.Status.RUNNING],
    ).exists()


def submit_operation(*, actor, target_user, action: str, password: str) -> SambaOperation:
    ensure_samba_enabled()

    if has_pending_operation(target_user):
        raise SambaOperationConflict('已有正在处理的 Samba 操作，请稍后刷新页面查看结果。')

    operation = SambaOperation.objects.create(
        target_user=target_user,
        action=action,
        status=SambaOperation.Status.QUEUED,
        payload_encrypted=_encrypt_payload({'password': password}),
        created_by=actor,
        updated_by=actor,
        result_summary='已提交，等待处理。',
    )

    if getattr(settings, 'SAMBA_ASYNC_OPERATIONS_ENABLED', True):
        transaction.on_commit(lambda: _executor.submit(process_operation, operation.pk))
    else:
        process_operation(operation.pk)

    return operation


def process_pending_operations(limit: int = 20) -> int:
    processed = 0
    operation_ids = list(
        SambaOperation.objects.filter(status=SambaOperation.Status.QUEUED)
        .order_by('created_at', 'id')
        .values_list('id', flat=True)[:limit]
    )

    for operation_id in operation_ids:
        process_operation(operation_id)
        processed += 1

    return processed


def process_operation(operation_id: int) -> SambaOperation:
    with transaction.atomic():
        operation = SambaOperation.objects.select_for_update().get(pk=operation_id)
        if operation.status != SambaOperation.Status.QUEUED:
            return operation

        operation.status = SambaOperation.Status.RUNNING
        operation.started_at = timezone.now()
        operation.result_summary = '后台处理中。'
        operation.last_error = ''
        operation.save(update_fields=['status', 'started_at', 'result_summary', 'last_error', 'updated_at'])

    try:
        payload = _decrypt_payload(operation.payload_encrypted)
        password = payload['password']
        result = _execute_operation(operation, password)
    except Exception as exc:
        logger.exception('Samba 操作执行失败', extra={'operation_id': operation_id, 'action': operation.action})
        operation.refresh_from_db(fields=['status', 'started_at'])
        operation.status = SambaOperation.Status.FAILED
        operation.finished_at = timezone.now()
        operation.last_error = str(exc)
        operation.result_summary = '执行失败。'
        operation.detail = str(exc)
        operation.payload_encrypted = ''
        operation.save(
            update_fields=[
                'status',
                'finished_at',
                'last_error',
                'result_summary',
                'detail',
                'payload_encrypted',
                'updated_at',
            ]
        )
        return operation

    operation.refresh_from_db(fields=['status', 'started_at'])
    operation.status = SambaOperation.Status.SUCCEEDED
    operation.finished_at = timezone.now()
    operation.last_error = ''
    operation.result_summary = result['summary']
    operation.detail = json.dumps(result['detail'], ensure_ascii=False)
    operation.payload_encrypted = ''
    operation.save(
        update_fields=[
            'status',
            'finished_at',
            'last_error',
            'result_summary',
            'detail',
            'payload_encrypted',
            'updated_at',
        ]
    )
    return operation


def _execute_operation(operation: SambaOperation, password: str) -> dict[str, object]:
    user = operation.target_user

    if operation.action == SambaOperation.Action.ENABLE:
        result = enable_samba_for_user(user, password)
        summary = 'Samba 账户已开通。' if result['created'] else 'Samba 账户已更新密码与组。'
        return {
            'summary': summary,
            'detail': result,
        }

    if operation.action == SambaOperation.Action.CHANGE_PASSWORD:
        change_samba_password(user, password)
        return {
            'summary': 'Samba 密码已修改。',
            'detail': {'username': user.username},
        }

    if operation.action == SambaOperation.Action.DISABLE:
        disable_samba_for_user(user)
        return {
            'summary': 'Samba 账户已停用。',
            'detail': {'username': user.username},
        }

    raise RuntimeError(f'不支持的 Samba 操作: {operation.action}')