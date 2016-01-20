from setuptools import setup, find_packages

setup(
    name='django-cachedS3-storage',
    version='0.0.1',
    description='Database-cached version of django-storages S3Boto backend',
    author='Rick Taylor',
    author_email='rick@ricktaylordesign.co.uk',
    packages=find_packages(),
    include_package_data=True,
    zip_safe=False,
    classifiers=[
        'Development Status :: 4 - Beta',
        'Environment :: Web Environment',
        'Intended Audience :: Developers',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Framework :: Django',
    ]
)
