from django.http import HttpResponse
from django.views.generic import View
from models import S3FileMeta
from io import BytesIO
class ThumbnailImage(View):
	def get(self, request, im_id):
		try:
			immeta = S3FileMeta.get(id=im_id)
		except S3FileMeta.DoesNotExist as e:
			raise Http404("Image does not exist")
		if immeta.thumbnail:
			imfile = BytesIO.BytesIO()
			imfile.write(immeta.thumbnail)
		else:
			return False
		return HttpResponse(f.read(), content_type=mimetype)
