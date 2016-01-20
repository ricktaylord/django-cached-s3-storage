from settings import APP_DATABASE_NAME

class CachedS3Router(object):
    """
    A router to control all database operations on models in the
    cachedS3 application.
    """
    def db_for_read(self, model, **hints):
        """
        Attempts to read cachedS3 models go to APP_DATABASE_NAME.
        """
        if model._meta.app_label == 'cachedS3':
            return APP_DATABASE_NAME
        return None

    def db_for_write(self, model, **hints):
        """
        Attempts to write cachedS3 models go to APP_DATABASE_NAME.
        """
        if model._meta.app_label == 'cachedS3':
            return APP_DATABASE_NAME
        return None

    def allow_relation(self, obj1, obj2, **hints):
        """
        Allow relations if a model in the cachedS3 app is involved.
        """
        if obj1._meta.app_label == 'cachedS3' or \
           obj2._meta.app_label == 'cachedS3':
           return True
        return None

    def allow_migrate(self, db, app_label, model=None, **hints):
        """
        Make sure the cachedS3 app only appears in the APP_DATABASE_NAME
        database.
        """
        if app_label == 'cachedS3':
            return db == APP_DATABASE_NAME
        return None