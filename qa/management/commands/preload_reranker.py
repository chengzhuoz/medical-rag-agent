from django.core.management.base import BaseCommand, CommandError

from qa.services import get_reranker


class Command(BaseCommand):
    help = "下载并验证 Cross-Encoder 重排序模型。"

    def handle(self, *args, **options):
        reranker = get_reranker()
        if reranker is None:
            raise CommandError("重排序模型不可用：检查 RERANKER_ENABLED、模型名称和网络连接。")

        self.stdout.write(self.style.SUCCESS("Cross-Encoder 重排序模型已就绪。"))