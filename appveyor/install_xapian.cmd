REM ========================================================
REM Install xapian
curl -fsSL -O http://download.kiwix.org/dev/xapian-core-1.4.16.zip || exit /b 1
7z x xapian-core-1.4.16.zip || exit /b 1
%MINGW64_RUN% "cd /c/Projects/kiwix-build/xapian-core-1.4.16 && ../appveyor/apply_patch.sh xapian_remote.patch" || exit /b 1
cd xapian-core-1.4.16
mkdir build
cd build
%MINGW64_RUN% "cd /c/Projects/kiwix-build/xapian-core-1.4.16/build && /c/Projects/kiwix-build/appveyor/build_xapian.sh" > build_xapian.log || exit /b 1
cd ..\..
