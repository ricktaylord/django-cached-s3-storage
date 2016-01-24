# coding: utf-8
# Python imports
import time
import inspect
import logging
import os
import types
from tempfile import NamedTemporaryFile
from datetime import datetime
from io import BytesIO

# django imports
from django.core.urlresolvers import reverse
from django.core.files import File
from django.core.files.base import ContentFile

# library imports
from storages.backends.s3boto import S3BotoStorage, parse_ts_extended, S3ResponseError
from PIL import Image

# local imports
from models import FileTag, S3FileMeta
from settings import USE_TAG_DIRECTORIES, RECENT_UPLOAD_DIRECTORY


class CachedS3BotoStorage(S3BotoStorage):
    def __init__(self, *args, **kwargs):
        super(CachedS3BotoStorage, self).__init__(*args, **kwargs)
        #self.entries = S3FileMetaHandler
        self._entries = {}
        self._folders = {}
        self._update_calls = 0

    @property
    def entries(self):
        """
        Get the locally cached files for the bucket.
        Overrides django-storages behaviour by loading from database backend if available (2 tier cache)
        """
        return dict([(k, v)
                     for k, v in self.raw_entries().iteritems()
                     if v.size > 0])

    def raw_entries(self):
        if not self._entries:
            self._entries = dict([(self._clean_name(entry.path), entry)
                                  for entry in S3FileMeta.objects.all()])
        return self._entries

    def exists(self, path):
        return path in self.entries.keys() or path in self.folders.keys()

    def thumbnail_cache_url(self, path, gen_thumb_cb):
        try:
            immeta = S3FileMeta.get(path=path)
        except S3FileMeta.DoesNotExist:
            return False  # throw error?
        imid = immeta.id
        path = reverse('cachedS3.thumbnail', args=(imid,))
        if not path:
            gen_thumb_cb()
            path = reverse('cachedS3.thumbnail', args=(imid,))
        return path

    def tag_file(self, path, tags):
        try:
            filemeta = S3FileMeta.objects.get(path=path)
        except S3FileMeta.DoesNotExist:
            return False
        if isinstance(tags, types.StringTypes):
            tags = (tags,)
        self._tag_file(filemeta, tags)

    def _tag_file(self, filemeta, tags):
        for tagname in tags:
            tag, created = FileTag.objects.get_or_create(name=tagname)
            if created:
                tag.save()
            filemeta.tags.add(tag)

    def _update_folder_cache(self, entry):
        name = entry.path
        for ancdirname in self._get_file_ancestor_dirs(name):
            try:
                if entry.last_modified > self._folders[ancdirname, -1]:
                    self._folders[ancdirname] = entry.last_modified
            except:
                self._folders[ancdirname] = entry.last_modified

    def _generate_folders(self):
        self._folders = {}
        for path, entry in self.raw_entries().iteritems():
            self._update_folder_cache(entry)

    def _clean_cache(self):
        self._folders = None
        self._entries = None

    @property
    def folders(self):
        """
        folder paths and last-modified time are cached in memory only
        re-calculated from the entries() cache each time,
        as last-modified not available directly from S3
        """

        if not self._folders:
            self._generate_folders()
        return self._folders

    def set_original(self, name, original=True):
        fm = S3FileMeta.objects.get(path=name)
        fm.original = original
        fm.save()
        self._entries[fm.path] = fm

    def batch_set_original(self, names, original=True):
        qs = S3FileMeta.objects.filter(path__in=names)
        return qs.update(original=original)

    def _get_file_ancestor_dirs(self, fle):
        parts = fle.split("/")
        ret = ["/".join(parts[:x]) for x in range(len(parts))]
        return ret

    def _ensure_s3key(self, name, fle=None, s3key=None):
        if s3key is None:
            try:
                s3key = fle.key
            except:
                s3key = self.bucket.get_key(
                    self._normalize_name(self._clean_name(name)))
        return s3key


    def _update_db_cache_entry(self, name, fle=None,
                               thumbnail=False, s3key=None,
                               update=True, original=False):
        s3key = _ensure_s3key(self, name, fle, s3key)
        filemeta_defaults = {'size': s3key.size,
                             'last_modified': parse_ts_extended(
                                 s3key.last_modified),
                             'original':original}

        if name not in self.entries or self.entries[name].image_x is None:
            self._update_calls += 1
            if self._update_calls > 30:
                time.sleep(10)
                self._update_calls = 0
            try:
                fle = self.open(name, 'r')
                im = Image.open(fle)
                filemeta_defaults.update(
                    {'image_x': im.size[0],
                     'image_y': im.size[1]})

                if thumbnail:
                    logging.debug("Saving thumbnail cache")
                    bytesfle = BytesIO.BytesIO()
                    im.save(bytesfle, 'JPEG')
                    filemeta_defaults['thumbnail'] = bytesfle.getvalue()
                fle.close()
            except IOError:
                filemeta_defaults.update({'image_x': 0, 'image_y': 0})

        if name not in self.entries or update or self.entries[name].image_x is None:
            filemeta, created = S3FileMeta.objects.get_or_create(
                path=name, defaults=filemeta_defaults)
            if not created:
                filemeta.__dict__.update(filemeta_defaults)
                filemeta.save()
            self._entries[filemeta.path] = filemeta

            self._update_folder_cache(filemeta)

    def listmostrecent(self, filter_original=True):
        qs = S3FileMeta.objects
        if filter_original:
            qs = qs.filter(original=True)
        else:
            qs = qs.all()
        return ([], [el.path for el in qs.order_by(
            "-last_modified")[0:75]])

    @property
    def use_tag_directories(self):
        return USE_TAG_DIRECTORIES

    @property
    def recent_upload_directory(self):
        return RECENT_UPLOAD_DIRECTORY

    def listdir(self, name):
        if self.use_tag_directories:
            return self.listdir_bytag(name)
        name = self._clean_name(name)
        level = name.count("/")
        lpath = len(name) + 1
        files = [path[lpath:] for path in self.entries.keys()
                 if path.startswith(name) and
                 path not in self.folders.keys() and
                 path.count("/") == level + 1]
        folders = [path[lpath:] for path in self.folders.keys()
                   if path.startswith(name) and
                   path.count("/") == level + 1]
        return (folders, files)

    def listdir_bytag(self, name):
        name = self._clean_name(name)
        last_seg = name.split("/")[-1]
        logging.debug("Tag browsing " + last_seg)
        paths = [el.path for el in
                 S3FileMeta.objects.filter(tags__name=last_seg)]
        if not paths:
            if last_seg == RECENT_UPLOAD_DIRECTORY:
                logging.debug(self.listmostrecent())
                return self.listmostrecent()
            return ([el.name for el in FileTag.objects.all()] +
                    [self.recent_upload_directory, ], [])
            return (["/", ], paths)

    def listdir_recursive(self, name, raw=False, full=False):
        name = self._normalize_name(self._clean_name(name))
        lpath = len(name) + 1
        if raw:
            entr = self.raw_entries().keys()
        else:
            entr = self.entries.keys()
        if full:
            outfn = lambda x: x
        else:
            outfn = lambda x: x[lpath:]
        files = [outfn(path) for path in entr
                 if path.startswith(name) and
                 path not in self.folders.keys()]
        folders = [outfn(path)
                   for path in self.folders.keys() if path.startswith(name)]
        return (folders, files)

    def sync_caches_to_S3(self):
        blist = self.bucket.list(self.location)
        for key in blist:
            print key
            self._update_db_cache_entry(key.name[len(self.location):],
                                        fle=None, s3key=key, update=True)

    def convert_all_images_to_RGB(self):
        for path, fl in self.entries.iteritems():
            try:
                tmpfile = File(NamedTemporaryFile())
                fle = self.open(path, 'r')
                im = Image.open(fle)
                dr, basename = os.path.split(path)
                root, ext = os.path.splitext(basename)
                im.convert('RGB').save(tmpfile,
                                       format=Image.EXTENSION[ext.lower()],
                                       quality=95)
                self.save(path, tmpfile)
                fle.close()
                print "Saved %s as RGB" % path
            except IOError as e:
                print "Error opening %s: %s" % (path, e.message)

    def isdir(self, path):
        path = self._clean_name(path)
        if USE_TAG_DIRECTORIES:
            last_seg = path.split("/")[-1]
            logging.debug("Checking if " + path + " is a folder or " +
                          last_seg + " is a tag")
            if path in self.entries.keys() and path not in self.folders.keys():
                return False
            return self._clean_name(path) in self.folders.keys() or \
                FileTag.objects.filter(
                    name=self._clean_name(last_seg)).exists() or \
                last_seg == "recent_uploads"
        return self._clean_name(path) in self.folders.keys()

    def isfile(self, path):
        path = self._clean_name(path)
        return path in self.entries.keys() and path not in self.folders.keys()

    def _save(self, path, fle, *args, **kwargs):
        logging.debug("Saving file %s", path)
        fle.seek(0)
        saveret = super(
            CachedS3BotoStorage, self)._save(path, fle, *args, **kwargs)
        try:
            thumbnail = kwargs['thumbnail']
        except KeyError:
            thumbnail = False
        logging.debug("Save args %s", str(kwargs))
        try:
            original = kwargs['original']
        except KeyError:
            original = True
        self._update_db_cache_entry(saveret, original=original, fle=fle, thumbnail=thumbnail)
        return saveret

    def modified_time(self, name):
        name = self._clean_name(name)
        entry = self.entries.get(name)
        # Parse the last_modified string to a local datetime object.
        try:
            return self.folders[name]
        except KeyError:
            try:
                return entry.last_modified
            except AttributeError:
                return datetime.now()

    def dimensions(self, name):
        name = self._clean_name(name)
        try:
            entry = self.entries[name]
        except IndexError:
            return None
        if entry.image_x > 0:
            return (entry.image_x, entry.image_y)
        else:
            return None

    def delete(self, name, clean_cache=True):
        isdir = self.isdir(name)
        try:
            obj = S3FileMeta.objects.get(path=name)
            obj.delete()
        except:
            if isdir:
                try:
                    obj = S3FileMeta.objects.get(path=name + "/")
                    obj.delete()
                except:
                    pass
            pass

        if not isdir:
            ret = super(CachedS3BotoStorage, self).delete(name)
        else:
            ret = True
        if clean_cache:
            self._clean_cache()
        return ret

    def rmtree(self, name):
        (_, files) = self.listdir_recursive(name, raw=True, full=True)
        for item in files:
            self.delete(item, clean_cache=False)
        self.delete(name)

    def makedirs(self, name):
        name = self._clean_name(name)
        #saveret = super(CachedS3BotoStorage,self).save(name+"/_",fl)
        #s3key = self.bucket.get_key(saveret)
        entry = S3FileMeta(path=name + "/_", last_modified=datetime.now())
        entry.save()
        self._update_folder_cache(entry)
        self._clean_cache()

    def mvtree(self, old_dir, new_dir):
        if self.exists(new_dir):
            raise OSError(
                "The folder '%s' already exists: please choose a different name" % new_dir)
        old_key_name = self._clean_name(old_dir)
        new_key_name = self._clean_name(new_dir)
        (_, files) = self.listdir_recursive(old_key_name, full=True)
        for fl in files:
            new_fl = fl.replace(old_key_name, new_key_name)
            self.mvfile(fl, new_fl)
        self.makedirs(new_dir)
        self.rmtree(old_key_name)

    def move(self, old_file_name, new_file_name, allow_overwrite=False):
        if self.isdir(old_file_name):
            self.mvtree(old_file_name, new_file_name)
        else:
            self.mvfile(old_file_name, new_file_name, allow_overwrite)
        self._clean_cache()

    def mvfile(self, old_file_name, new_file_name, allow_overwrite=False):
        if self.exists(new_file_name):
            if allow_overwrite:
                self.delete(new_file_name)
            else:
                raise OSError(
                    "The dest file '%s' exists, allow_overwrite is False"
                    % new_file_name)

        old_key_name = self._normalize_name(self._clean_name(old_file_name))
        new_key_name = self._normalize_name(self._clean_name(new_file_name))
        k = None
        try:
            k = self.bucket.copy_key(new_key_name,
                                     self.bucket.name, old_key_name)
        except S3ResponseError:
            pass

        if not k:
            raise OSError("Couldn't copy '%s' to '%s'" %
                          (old_key_name, new_key_name))
        self._update_db_cache_entry(new_file_name)
        self.delete(old_file_name, clean_cache=False)
