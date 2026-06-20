from core.tables import ActionsColumn, BaseDateColumn, BaseDateTimeColumn, BaseTable

from .models import ArchiveAsset


class ArchiveAssetTable(BaseTable):
    business_date = BaseDateColumn()
    uploaded_at = BaseDateTimeColumn()
    actions = ActionsColumn(view_url="archives:asset_detail", edit_url="archives:asset_edit")

    class Meta(BaseTable.Meta):
        model = ArchiveAsset
        fields = ("business_date", "asset_type", "title", "skill_project", "filename", "uploaded_by", "uploaded_at", "is_locked", "actions")
