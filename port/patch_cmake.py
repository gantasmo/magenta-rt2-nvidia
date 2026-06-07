#!/usr/bin/env python3
# Patches the magenta-realtime CMake build so the portable `core` library and
# the headless `hello_mrt2` CLI build on Linux + NVIDIA (CUDA) instead of being
# hard-blocked to macOS/Metal.
#
# It edits exactly two files:
#   - CMakeLists.txt            (root: Apple guard, MLX tag + CUDA flag, TFLite, targets)
#   - core/CMakeLists.txt       (Apple framework link flags)
#
# Every transform is anchored on a unique string. If an anchor is missing the
# script aborts loudly (upstream drifted) rather than silently mis-patching.
# Re-running is safe: each transform is skipped if its result is already present.
#
# Usage:  python3 patch_cmake.py /path/to/magenta-realtime
import re
import sys
import pathlib

MARKER = "# [PORT-PATCHED for Linux/CUDA]"


def fail(msg):
    print(f"  !! FAIL: {msg}")
    sys.exit(1)


def sub_once(text, old, new, label):
    """Literal single substring replacement with presence assertions."""
    if new in text and old not in text:
        print(f"  .. {label}: already patched, skipping")
        return text
    if old not in text:
        fail(f"{label}: anchor not found (upstream changed?)")
    print(f"  ok {label}")
    return text.replace(old, new, 1)


def regex_wrap(text, pattern, label, flags=re.DOTALL):
    """Wrap the matched span in `if(APPLE) ... endif()`."""
    if f"# WRAP:{label}" in text:
        print(f"  .. {label}: already wrapped, skipping")
        return text
    m = re.search(pattern, text, flags)
    if not m:
        fail(f"{label}: anchor not found (upstream changed?)")
    span = m.group(0)
    wrapped = f"# WRAP:{label}\nif(APPLE)\n{span}\nendif()  # /WRAP:{label}"
    print(f"  ok {label}")
    return text[: m.start()] + wrapped + text[m.end():]


def patch_root(repo):
    p = repo / "CMakeLists.txt"
    t = p.read_text(encoding="utf-8")
    if MARKER in t:
        print("CMakeLists.txt (root): already patched (marker present), skipping")
        return
    print("Patching CMakeLists.txt (root)")

    # 1) project() declares OBJCXX, which needs an Objective-C++ compiler that
    #    does not exist on Linux. Make the language list platform-conditional.
    t = sub_once(
        t,
        "project(MagentaRT LANGUAGES C CXX OBJCXX)",
        "if(APPLE)\n"
        "  project(MagentaRT LANGUAGES C CXX OBJCXX)\n"
        "else()\n"
        "  project(MagentaRT LANGUAGES C CXX)\n"
        "endif()",
        "project() OBJCXX guard",
    )

    # 2) Remove the hard macOS-only FATAL_ERROR guard.
    guard = re.compile(
        r"if\(NOT APPLE\)\s*\n\s*message\(FATAL_ERROR.*?endif\(\)",
        re.DOTALL,
    )
    if "magenta-rt-v2's C++ build is macOS-only" in t:
        t = guard.sub(
            "# [PORT] macOS-only guard removed: core + hello_mrt2 build on Linux/CUDA.",
            t,
            count=1,
        )
        print("  ok macOS FATAL_ERROR guard removed")
    else:
        print("  .. macOS guard: already removed, skipping")

    # 3) Bump MLX to v0.31.2 (CUDA quantized-matmul + FFT; ~zero API drift).
    t = sub_once(t, "GIT_TAG        v0.31.1", "GIT_TAG        v0.31.2", "MLX tag -> v0.31.2")

    # 4) Enable the CUDA backend off-Apple.
    t = sub_once(
        t,
        'set(MLX_BUILD_CUDA OFF CACHE BOOL "" FORCE)',
        "if(APPLE)\n"
        '  set(MLX_BUILD_CUDA OFF CACHE BOOL "" FORCE)\n'
        "else()\n"
        '  set(MLX_BUILD_CUDA ON CACHE BOOL "" FORCE)\n'
        "endif()",
        "MLX_BUILD_CUDA",
    )

    # 5) The MLX Metal-preamble shell patch only applies to the Metal backend.
    t = regex_wrap(
        t,
        r'file\(READ "\$\{mlx_SOURCE_DIR\}/mlx/backend/metal/make_compiled_preamble\.sh".*?'
        r'file\(WRITE "\$\{mlx_SOURCE_DIR\}/mlx/backend/metal/make_compiled_preamble\.sh" "\$\{MLX_CONTENT\}"\)',
        "metal-preamble-patch",
    )

    # 6) Re-enable XNNPACK so the MusicCoCa TFLite models run fast on Linux CPU.
    t = sub_once(
        t,
        'set(TFLITE_ENABLE_XNNPACK OFF CACHE BOOL "Disable XNNPACK delegate" FORCE)',
        "if(APPLE)\n"
        '  set(TFLITE_ENABLE_XNNPACK OFF CACHE BOOL "Disable XNNPACK delegate" FORCE)\n'
        "else()\n"
        '  set(TFLITE_ENABLE_XNNPACK ON CACHE BOOL "Enable XNNPACK delegate (Linux CPU)" FORCE)\n'
        "endif()",
        "TFLITE_ENABLE_XNNPACK",
    )

    # 7) Skip the npm React-UI custom targets on Linux (GUI-app only).
    t = regex_wrap(
        t,
        r"add_custom_target\(npm_install_root.*?add_dependencies\(build_mrt2_ui npm_install_root\)",
        "npm-ui-targets",
    )

    # 8) Only build the portable targets; gate the Apple GUI/host subdirs.
    t = sub_once(
        t,
        "add_subdirectory(core)\n"
        "add_subdirectory(examples/mrt2/auv3)\n"
        "add_subdirectory(examples/mrt2/standalone)\n"
        "add_subdirectory(examples/jam)\n"
        "add_subdirectory(examples/collider)\n"
        "add_subdirectory(examples/hello_mrt2)\n"
        "add_subdirectory(examples/max)\n"
        "add_subdirectory(examples/pd)\n"
        "add_subdirectory(examples/sc)",
        "add_subdirectory(core)\n"
        "add_subdirectory(examples/hello_mrt2)\n"
        "if(APPLE)\n"
        "  add_subdirectory(examples/mrt2/auv3)\n"
        "  add_subdirectory(examples/mrt2/standalone)\n"
        "  add_subdirectory(examples/jam)\n"
        "  add_subdirectory(examples/collider)\n"
        "  add_subdirectory(examples/max)\n"
        "  add_subdirectory(examples/pd)\n"
        "  add_subdirectory(examples/sc)\n"
        "endif()",
        "project targets (gate Apple subdirs)",
    )

    if MARKER not in t:
        t = MARKER + "\n" + t
    p.write_text(t, encoding="utf-8")


def patch_core(repo):
    p = repo / "core" / "CMakeLists.txt"
    t = p.read_text(encoding="utf-8")
    if MARKER in t:
        print("core/CMakeLists.txt: already patched (marker present), skipping")
        return
    print("Patching core/CMakeLists.txt")

    # Apple frameworks: keep on macOS, drop on Linux (MLX-CUDA links its own).
    t = sub_once(
        t,
        '    "-framework Metal"\n'
        '    "-framework Accelerate"\n'
        '    "-framework Foundation"\n'
        ")",
        ")\n"
        "if(APPLE)\n"
        "    target_link_libraries(magentart_core PUBLIC\n"
        '        "-framework Metal"\n'
        '        "-framework Accelerate"\n'
        '        "-framework Foundation")\n'
        "else()\n"
        "    find_package(Threads REQUIRED)\n"
        "    target_link_libraries(magentart_core PUBLIC Threads::Threads ${CMAKE_DL_LIBS})\n"
        "endif()",
        "core Apple frameworks",
    )

    if MARKER not in t:
        t = MARKER + "\n" + t
    p.write_text(t, encoding="utf-8")


def main():
    if len(sys.argv) != 2:
        print("Usage: python3 patch_cmake.py /path/to/magenta-realtime")
        sys.exit(2)
    repo = pathlib.Path(sys.argv[1]).resolve()
    if not (repo / "CMakeLists.txt").exists():
        fail(f"{repo} does not look like the magenta-realtime repo root")
    patch_root(repo)
    patch_core(repo)
    print("\nDone. Configure with:  cmake . -B build -DCMAKE_BUILD_TYPE=Release")


if __name__ == "__main__":
    main()
