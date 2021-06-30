# pylint: disable=import-outside-toplevel
from xcute import cute, LiveReload

def build():
    """Build pyte"""
    import re
    import shutil
    import requests
    shutil.rmtree("ptt_mail_backup/pyte", ignore_errors=True)
    r = requests.get("https://github.com/eight04/pyte/archive/dev-blink.zip")
    def includes(name):
        match = re.match(r".+?/(pyte/.+\.py)$", name)
        if match:
            return "ptt_mail_backup/{}".format(match.group(1))
        return None
    extract_zip(r.content, includes)
                        
def extract_zip(b, includes):
    import pathlib
    from io import BytesIO
    from zipfile import ZipFile
    with BytesIO(b) as f:
        with ZipFile(f) as z:
            for name in z.namelist():
                output = includes(name)
                if output:
                    path = pathlib.Path(output)
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(z.read(name))

cute(
    pkg_name = 'ptt_mail_backup',
    build = build,
    lint = 'pylint {pkg_name} cute setup',
    test = ['lint', 'pytest', 'readme_build'],
    bump_pre = ['build', 'test'],
    bump_post = ['dist', 'release', 'publish', 'install'],
    dist = ['x-clean build dist && python setup.py sdist bdist_wheel'],
    release = [
        'git add .',
        'git commit -m "Release v{version}"',
        'git tag -a v{version} -m "Release v{version}"'
    ],
    publish = [
        'twine upload dist/*',
        'git push --follow-tags'
    ],
    install = 'pip install -e .',
    readme_build = [
        'python setup.py --long-description | x-pipe build/readme/index.rst',
        ('rst2html5.py --no-raw --exit-status=1 --verbose '
         'build/readme/index.rst build/readme/index.html')
    ],
    readme_pre = "readme_build",
    readme = LiveReload("README.rst", "readme_build", "build/readme")
)
