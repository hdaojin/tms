# meeting/tables.py
import django_tables2 as tables
from core.utils.tables import BaseTable, ActionsColumn
from .models import Score


class ScoreTable(BaseTable):
    user = tables.Column(verbose_name="姓名", accessor="user.get_full_name")
    pass


