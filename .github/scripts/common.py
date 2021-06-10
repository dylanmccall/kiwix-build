import os
from os import environ as _environ
from pathlib import Path
from datetime import date
import tarfile
import zipfile
import subprocess
import re
import shutil

from kiwixbuild.versions import (
    main_project_versions,
    release_versions,
    base_deps_versions,
)

PLATFORM_TARGET = _environ["PLATFORM_TARGET"]
if PLATFORM_TARGET == "native_desktop":
    PLATFORM_TARGET = "native_dyn"
    DESKTOP = True
else:
    DESKTOP = False
OS_NAME = _environ["OS_NAME"]
HOME = Path(os.path.expanduser("~"))

BASE_DIR = HOME / "BUILD_{}".format(PLATFORM_TARGET)
SOURCE_DIR = HOME / "SOURCE"
ARCHIVE_DIR = HOME / "ARCHIVE"
INSTALL_DIR = BASE_DIR / "INSTALL"
TMP_DIR = Path("/tmp")
KBUILD_SOURCE_DIR = HOME / "kiwix-build"

# [TODO]
KIWIX_DESKTOP_ONLY = False

_ref = _environ.get("GITHUB_REF", "").split("/")[-1]
MAKE_RELEASE = re.fullmatch(r"r_[0-9]+", _ref) is not None

RELEASE_OS_NAME = "macos" if OS_NAME == "osx" else "linux"

PLATFORM_TO_RELEASE = {
    "native_mixed": "{os}-x86_64".format(os=RELEASE_OS_NAME),
    "native_static": "{os}-x86_64".format(os=RELEASE_OS_NAME),
    "win32_static": "win-i686",
    "armhf_static": "{os}-armhf".format(os=RELEASE_OS_NAME),
    "i586_static": "{os}-i586".format(os=RELEASE_OS_NAME),
}

FLATPAK_HTTP_GIT_REMOTE = "https://github.com/flathub/org.kiwix.desktop.git"
FLATPAK_GIT_REMOTE = "git@github.com:flathub/org.kiwix.desktop.git"

BIN_EXT = ".exe" if PLATFORM_TARGET.startswith("win32_") else ""

# We have build everything. Now create archives for public deployement.
EXPORT_FILES = {
    "kiwix-tools": (
        INSTALL_DIR / "bin",
        [
            f + BIN_EXT
            for f in ("kiwix-manage", "kiwix-read", "kiwix-search", "kiwix-serve")
        ],
    ),
    "zim-tools": (
        INSTALL_DIR / "bin",
        [
            f + BIN_EXT
            for f in (
                "zimbench",
                "zimcheck",
                "zimdump",
                "zimsearch",
                "zimdiff",
                "zimpatch",
                "zimsplit",
                "zimwriterfs",
                "zimrecreate"
            )
        ],
    ),
    "libzim": (
        INSTALL_DIR,
        (
            "lib/x86_64-linux-gnu/libzim.so.{}".format(main_project_versions["libzim"]),
            "lib/x86_64-linux-gnu/libzim.so.{}".format(
                main_project_versions["libzim"][0]
            ),
            "lib/libzim.{}.dylib".format(
                main_project_versions["libzim"][0]
            ),
            "lib/libzim.dylib",
            "include/zim/**/*.h",
        ),
    ),
}

DATE = date.today().isoformat()


def print_message(message, *args, **kwargs):
    message = message.format(*args, **kwargs)
    message = "{0} {1} {0}".format("-" * 3, message)
    print(message, flush=True)


MANIFEST_TEMPLATE = """{archive_name}
***************************

Dependencies archive for {target} on platform {platform}
Generated at {date}
"""


def write_manifest(manifest_file, archive_name, target, platform):
    with manifest_file.open(mode="w") as f:
        f.write(
            MANIFEST_TEMPLATE.format(
                archive_name=archive_name, target=target, platform=platform, date=DATE,
            )
        )


def run_kiwix_build(
    target,
    platform,
    build_deps_only=False,
    target_only=False,
    make_release=False,
    make_dist=False,
):
    command = ["kiwix-build"]
    command.append(target)
    command.append("--hide-progress")
    command.append("--fast-clone")
    if platform == "flatpak" or platform.startswith("win32_"):
        command.append("--assume-packages-installed")
    if target == "kiwix-lib-app" and platform.startswith("android_"):
        command.extend(["--target-platform", "android", "--android-arch", platform[8:]])
    elif platform == "android":
        command.extend(["--target-platform", "android"])
        for arch in ("arm", "arm64", "x86", "x86_64"):
            command.extend(["--android-arch", arch])
    else:
        command.extend(["--target-platform", platform])
    if build_deps_only:
        command.append("--build-deps-only")
    if target_only:
        command.append("--build-nodeps")
    if make_release:
        command.append("--make-release")
    if make_dist:
        command.append("--make-dist")
    print_message(
        "Build {} (deps={}, release={}, dist={})",
        target,
        build_deps_only,
        make_release,
        make_dist,
    )
    env = dict(_environ)
    env["SKIP_BIG_MEMORY_TEST"] = "1"
    subprocess.check_call(command, cwd=str(HOME), env=env)
    print_message("Build ended")


def upload(file_to_upload, host, dest_path):
    if not file_to_upload.exists():
        print_message("No {} to upload!", file_to_upload)
        return

    command = [
        "ssh",
        "-i",
        _environ.get("SSH_KEY"),
        "-o",
        "StrictHostKeyChecking=no",
        host,
        "mkdir -p {}".format(dest_path),
    ]
    print_message("Creating dest path {}", dest_path)
    subprocess.check_call(command)

    command = [
        "scp",
        "-i",
        _environ.get("SSH_KEY"),
        "-o",
        "StrictHostKeyChecking=no",
        str(file_to_upload),
        "{}:{}".format(host, dest_path),
    ]
    print_message("Sending archive with command {}", command)
    subprocess.check_call(command)


def upload_archive(archive, project, make_release):
    if project.startswith("kiwix-"):
        host = "ci@download.kiwix.org"
        dest_path = "/data/download/"
    else:
        host = "ci@download.openzim.org"
        dest_path = "/data/openzim/"

    if make_release:
        dest_path = dest_path + "release/" + project
    else:
        dest_path = dest_path + "nightly/" + DATE

    upload(archive, host, dest_path)


def make_deps_archive(target=None, name=None, full=False):
    archive_name = name or "deps2_{}_{}_{}.tar.xz".format(
        OS_NAME, PLATFORM_TARGET, target
    )
    print_message("Create archive {}.", archive_name)
    files_to_archive = [INSTALL_DIR]
    files_to_archive += HOME.glob("BUILD_*/LOGS")
    if PLATFORM_TARGET == "native_mixed":
        files_to_archive += [HOME / "BUILD_native_static" / "INSTALL"]
    if PLATFORM_TARGET.startswith("android"):
        files_to_archive.append(HOME / "BUILD_neutral" / "INSTALL")
    if PLATFORM_TARGET == "android":
        for arch in ("arm", "arm64", "x86", "x86_64"):
            base_dir = HOME / "BUILD_android_{}".format(arch)
            files_to_archive.append(base_dir / "INSTALL")
            if (base_dir / "meson_cross_file.txt").exists():
                files_to_archive.append(base_dir / "meson_cross_file.txt")
    files_to_archive += HOME.glob("BUILD_*/android-ndk*")
    files_to_archive += HOME.glob("BUILD_*/android-sdk*")
    if (BASE_DIR / "meson_cross_file.txt").exists():
        files_to_archive.append(BASE_DIR / "meson_cross_file.txt")

    manifest_file = BASE_DIR / "manifest.txt"
    write_manifest(manifest_file, archive_name, target, PLATFORM_TARGET)
    files_to_archive.append(manifest_file)

    relative_path = HOME
    if full:
        files_to_archive += ARCHIVE_DIR.glob(".*_ok")
        files_to_archive += BASE_DIR.glob("*/.*_ok")
        files_to_archive += (HOME / "BUILD_native_dyn").glob("*/.*_ok")
        files_to_archive += (HOME / "BUILD_native_static").glob("*/.*_ok")
        files_to_archive += HOME.glob("BUILD_android*/**/.*_ok")
        files_to_archive += SOURCE_DIR.glob("*/.*_ok")
        if PLATFORM_TARGET.startswith("armhf"):
            files_to_archive += (SOURCE_DIR / "armhf").glob("*")
        toolchains_subdirs = HOME.glob("BUILD_*/TOOLCHAINS/*/*")
        for subdir in toolchains_subdirs:
            if not subdir.match("tools"):
                files_to_archive.append(subdir)

    archive_file = TMP_DIR / archive_name
    with tarfile.open(str(archive_file), "w:xz") as tar:
        for name in set(files_to_archive):
            print(".{}".format(name), flush=True)
            tar.add(str(name), arcname=str(name.relative_to(relative_path)))

    return archive_file


def get_postfix(project):
    postfix = main_project_versions[project]
    extra = release_versions.get(project)
    if extra:
        postfix = "{}-{}".format(postfix, extra)
    return postfix


def make_archive(project, make_release):
    try:
        platform = PLATFORM_TO_RELEASE[PLATFORM_TARGET]
    except KeyError:
        # We don't know how to name the release.
        return None

    try:
        base_dir, export_files = EXPORT_FILES[project]
    except KeyError:
        # No binary files to export
        return None

    if make_release:
        postfix = get_postfix(project)
    else:
        postfix = DATE

    archive_name = "{}_{}-{}".format(project, platform, postfix)

    files_to_archive = []
    for export_file in export_files:
        files_to_archive.extend(base_dir.glob(export_file))
    if platform == "win-i686":
        open_archive = lambda a: zipfile.ZipFile(
            str(a), "w", compression=zipfile.ZIP_DEFLATED
        )
        archive_add = lambda a, f: a.write(str(f), arcname=str(f.relative_to(base_dir)))
        archive_ext = ".zip"
    else:
        open_archive = lambda a: tarfile.open(str(a), "w:gz")
        archive_add = lambda a, f: a.add(
            str(f), arcname="{}/{}".format(archive_name, str(f.relative_to(base_dir)))
        )
        archive_ext = ".tar.gz"

    archive = TMP_DIR / "{}{}".format(archive_name, archive_ext)
    print_message("create archive {} with {}", archive, files_to_archive)
    with open_archive(archive) as arch:
        for f in files_to_archive:
            archive_add(arch, f)
    return archive


def create_desktop_image(make_release):
    print_message("creating desktop image")
    if make_release:
        postfix = get_postfix("kiwix-desktop")
        src_dir = SOURCE_DIR / "kiwix-desktop_release"
    else:
        postfix = DATE
        src_dir = SOURCE_DIR / "kiwix-desktop"

    if PLATFORM_TARGET == "flatpak":
        build_path = BASE_DIR / "org.kiwix.desktop.flatpak"
        app_name = "org.kiwix.desktop.{}.flatpak".format(postfix)
        print_message("archive is {}", build_path)
    else:
        build_path = HOME / "Kiwix-{}-x86_64.AppImage".format(postfix)
        app_name = "kiwix-desktop_x86_64_{}.appimage".format(postfix)
        command = [
            "kiwix-build/scripts/create_kiwix-desktop_appImage.sh",
            str(INSTALL_DIR),
            str(src_dir),
            str(HOME / "AppDir"),
        ]
        env = dict(os.environ)
        env["VERSION"] = postfix
        print_message("Build AppImage of kiwix-desktop")
        subprocess.check_call(command, cwd=str(HOME), env=env)

    print_message("Copy Build to {}".format(TMP_DIR / app_name))
    shutil.copy(str(build_path), str(TMP_DIR / app_name))
    return TMP_DIR / app_name


def update_flathub_git():
    git_repo_dir = TMP_DIR / "org.kiwix.desktop"
    env = dict(os.environ)
    env["GIT_AUTHOR_NAME"] = env["GIT_COMMITTER_NAME"] = "KiwixBot"
    env["GIT_AUTHOR_EMAIL"] = env["GIT_COMMITTER_EMAIL"] = "release@kiwix.org"

    def call(command, cwd=None):
        cwd = cwd or git_repo_dir
        print_message("call {}", command)
        subprocess.check_call(command, env=env, cwd=str(cwd))

    command = ["git", "clone", FLATPAK_HTTP_GIT_REMOTE]
    call(command, cwd=TMP_DIR)
    shutil.copy(str(BASE_DIR / "org.kiwix.desktop.json"), str(git_repo_dir))
    patch_dir = KBUILD_SOURCE_DIR / "kiwixbuild" / "patches"
    for dep in ("libaria2", "mustache", "pugixml", "xapian", "zstd"):
        for f in patch_dir.glob("{}_*.patch".format(dep)):
            shutil.copy(str(f), str(git_repo_dir / "patches"))
    command = ["git", "add", "-A", "."]
    call(command)
    command = [
        "git",
        "commit",
        "-m",
        "Update to version {}".format(main_project_versions["kiwix-desktop"]),
    ]
    try:
        call(command)
    except subprocess.CalledProcessError:
        # This may fail if there is nothing to commit (a rebuild of the CI for exemple)
        return
    command = ["git", "config", "remote.origin.pushurl", FLATPAK_GIT_REMOTE]
    call(command)
    command = ["git", "push"]
    env["GIT_SSH_COMMAND"] = "ssh -o StrictHostKeyChecking=no -i " + _environ.get(
        "SSH_KEY"
    )
    call(command)


def fix_macos_rpath(project):

    base_dir, export_files = EXPORT_FILES[project]
    for file in filter(lambda f: f.endswith(".dylib"), export_files):
        lib = base_dir / file
        if lib.is_symlink():
            continue
        command = ["install_name_tool", "-id", lib.name, str(lib)]
        print_message("call {}", " ".join(command))
        subprocess.check_call(command, env=os.environ)
