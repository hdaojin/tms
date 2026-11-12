from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from core.documents import DocumentError, DocumentRenderError, generate_document_pdf, list_document_templates
from core.documents.sample import sample_document


class Command(BaseCommand):
    help = "使用两套中文样张验证 PDF 渲染环境。"

    def add_arguments(self, parser):
        parser.add_argument("--output-dir", type=Path, help="将样张写入已有的目录。")

    def handle(self, *args, **options):
        output_dir = options["output_dir"]
        if output_dir is not None and not output_dir.is_dir():
            raise CommandError("样张输出目录必须已存在。")
        for template in list_document_templates():
            try:
                pdf = generate_document_pdf(sample_document(template.id))
                if output_dir is not None:
                    with (output_dir / f"{template.id}.pdf").open("xb") as file:
                        file.write(pdf)
            except (DocumentError, DocumentRenderError, OSError) as exc:
                raise CommandError(f"{template.name}自检失败。{exc}") from exc
            self.stdout.write(self.style.SUCCESS(f"{template.name}生成成功（{len(pdf):,} 字节）。"))
