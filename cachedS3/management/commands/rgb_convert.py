from django.core.management.base import BaseCommand, CommandError
from django.core.files.storage import DefaultStorage

class Command(BaseCommand):
        args = ''
        help = 'Converts all S3 images to RGB'
        def handle(self, *args, **options):
                DefaultStorage().convert_all_images_to_RGB()

