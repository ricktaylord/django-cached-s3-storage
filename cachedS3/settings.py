# coding: utf-8

# django imports
from django.conf import settings

# Use cacheS3 tag directories
USE_TAG_DIRECTORIES = getattr(settings, "CACHEDS3_USE_TAG_DIRECTORIES", False)
APP_DATABASE_NAME = getattr(settings, "CACHEDS3_DATABASE_NAME","default")

# Recent upload directory
RECENT_UPLOAD_DIRECTORY = getattr(settings, "CACHEDS3_RECENT_UPLOADS", "recent_uploads")