from django.db import models

class ImageTagField(models.CharField):
	def __init__(self,*args,**kwargs):
		self.max_length=100
		return super(ImageTagField,self).__init__(*args,**kwargs)