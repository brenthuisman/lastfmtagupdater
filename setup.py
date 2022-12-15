#! /usr/bin/env python
from setuptools import setup

VERSION = '3.0.3'

with open("README.md", "rb") as f:
    long_descr = f.read()

def main():
    setup(name='lastfmtagupdater',
          version=VERSION,
          description="Update your music files with tags from Last.FM",
          long_description=open('README.md').read(),
          classifiers=[
              'Development Status :: 4 - Beta',
              'Environment :: Console',
              'Programming Language :: Python :: 3',
              'License :: OSI Approved :: GPL License',
              'Topic :: Utilities',
              'Topic :: Multimedia :: Sound/Audio',
              'Operating System :: OS Independent'
          ],
          keywords='lastfm music tag update',
          author='Brent Huisman',
          author_email='mail@brenthuisman.net',
          url='https://github.com/brenthuisman/lastfmtagupdater',
          license='GPL',
          include_package_data=True,
          zip_safe=False,
          install_requires=['pylast<2.0.0','mutagen'],
          packages=['lastfmtagupdater'],
          entry_points={
              "console_scripts": ['lastfmtagupdater = lastfmtagupdater:main'],
          },
          )

if __name__ == '__main__':
    main()
