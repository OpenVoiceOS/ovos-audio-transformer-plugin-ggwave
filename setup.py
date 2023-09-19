#!/usr/bin/env python3
import logging
import os
import subprocess

from setuptools import setup
from setuptools.command.install import install

BASEDIR = os.path.abspath(os.path.dirname(__file__))


class CustomInstallCommand(install):
    """Custom install setup to help run shell commands before installation"""

    def run(self):
        # attempt to compile ggwave
        if not os.path.exists(os.path.expanduser("~/.local/bin/ggwave-rx")):
            logging.info(f"compiling ggwave from source")

            try:
                with open("/tmp/install_ggwave.sh", "w") as f:
                    f.write("""#!/bin/bash
git clone https://github.com/ggerganov/ggwave --recursive /tmp/ggwave
cd /tmp/ggwave && mkdir /tmp/ggwave/build && cd /tmp/ggwave/build
cmake .. && make
mv /tmp/ggwave/build/bin/* $HOME/.local/bin/
rm -rf /tmp/ggwave
""")
                subprocess.call("/bin/bash /tmp/install_ggwave.sh".split())
            except:
                logging.error("failed to compile ggwave, please install it manually")
        install.run(self)


def get_version():
    """ Find the version of the package"""
    version = None
    version_file = os.path.join(BASEDIR, 'ovos_audio_transformer_plugin_ggwave', 'version.py')
    major, minor, build, alpha = (None, None, None, None)
    with open(version_file) as f:
        for line in f:
            if 'VERSION_MAJOR' in line:
                major = line.split('=')[1].strip()
            elif 'VERSION_MINOR' in line:
                minor = line.split('=')[1].strip()
            elif 'VERSION_BUILD' in line:
                build = line.split('=')[1].strip()
            elif 'VERSION_ALPHA' in line:
                alpha = line.split('=')[1].strip()

            if ((major and minor and build and alpha) or
                    '# END_VERSION_BLOCK' in line):
                break
    version = f"{major}.{minor}.{build}"
    if alpha and int(alpha) > 0:
        version += f"a{alpha}"
    return version


def package_files(directory):
    paths = []
    for (path, directories, filenames) in os.walk(directory):
        for filename in filenames:
            paths.append(os.path.join('..', path, filename))
    return paths


def required(requirements_file):
    """ Read requirements file and remove comments and empty lines. """
    with open(os.path.join(BASEDIR, requirements_file), 'r') as f:
        requirements = f.read().splitlines()
        if 'MYCROFT_LOOSE_REQUIREMENTS' in os.environ:
            print('USING LOOSE REQUIREMENTS!')
            requirements = [r.replace('==', '>=').replace('~=', '>=') for r in requirements]
        return [pkg for pkg in requirements
                if pkg.strip() and not pkg.startswith("#")]


PLUGIN_ENTRY_POINT = 'ovos-audio-transformer-plugin-ggwave = ovos_audio_transformer_plugin_ggwave:GGWavePlugin'

setup(
    name='ovos-audio-transformer-plugin-ggwave',
    version=get_version(),
    description='A speech lang detection plugin for mycroft',
    url='https://github.com/OpenVoiceOS/ovos-audio-transformer-plugin-ggwave',
    author='JarbasAi',
    author_email='jarbasai@mailfence.com',
    license='Apache-2.0',
    packages=['ovos_audio_transformer_plugin_ggwave'],
    include_package_data=True,
    package_data={'': package_files('ovos_audio_transformer_plugin_ggwave')},
    install_requires=required("requirements.txt"),
    zip_safe=True,
    cmdclass={'install': CustomInstallCommand},  # compile ggwave-rx
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Intended Audience :: Developers',
        'Topic :: Text Processing :: Linguistic',
        'License :: OSI Approved :: Apache Software License',

        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.0',
        'Programming Language :: Python :: 3.1',
        'Programming Language :: Python :: 3.2',
        'Programming Language :: Python :: 3.3',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
    ],
    keywords='ovos plugin',
    entry_points={'neon.plugin.audio': PLUGIN_ENTRY_POINT}
)
