from django.db import models
from django.conf import settings
from django.core.files.storage import DefaultStorage

class FileTag(models.Model):
	objects = models.Manager()
	name = models.CharField(max_length=255)

class S3FileMeta(models.Model):
	objects = models.Manager()
	path = models.CharField(max_length=255, unique=True)
	last_modified = models.DateTimeField(null=True,blank=True)
	size = models.IntegerField(null=True, blank=True)
	image_x = models.IntegerField(null=True, blank=True)
	image_y = models.IntegerField(null=True, blank=True)
	tags = models.ManyToManyField(FileTag)
	thumbnail = models.BinaryField(null=True,blank=True)
	def get_absolute_url(self):
		return DefaultStorage().url(self.path)
		

