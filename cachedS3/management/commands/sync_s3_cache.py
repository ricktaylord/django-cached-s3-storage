from django.core.management.base import BaseCommand, CommandError
from django.core.files.storage import DefaultStorage

class Command(BaseCommand):
        args = ''
        help = 'Synchronises the local DB cache to Amazon S3'
        def handle(self, *args, **options):
                DefaultStorage().sync_caches_to_S3()

