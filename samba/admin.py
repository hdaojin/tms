from django.contrib import admin

from .models import SambaOperation


@admin.register(SambaOperation)
class SambaOperationAdmin(admin.ModelAdmin):
	list_display = (
		'target_user',
		'action',
		'status',
		'created_by',
		'created_at',
		'started_at',
		'finished_at',
	)
	list_filter = ('action', 'status', 'created_at')
	search_fields = ('target_user__username', 'created_by__username', 'result_summary', 'last_error')
	readonly_fields = (
		'target_user',
		'action',
		'status',
		'created_by',
		'created_at',
		'started_at',
		'finished_at',
		'result_summary',
		'detail',
		'last_error',
	)

	def has_add_permission(self, request):
		return False