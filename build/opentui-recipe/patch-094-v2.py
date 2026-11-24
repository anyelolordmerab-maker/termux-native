import sys
import shutil

if len(sys.argv) != 2:
    sys.exit("usage: patch-094-v2.py <packages/native/build.zig>")

p = sys.argv[1]
shutil.copy(p, p + ".bak")
s = open(p).read()
orig = s


def sub(old, new, label):
    global s
    if old not in s:
        sys.exit(f"anchor missing: {label}")
    s = s.replace(old, new, 1)


helper = '''fn addAndroidNdkIncludes(b: *std.Build, step: *std.Build.Step.TranslateC) void {
    const inc = android_ndk_include orelse return;
    const arch_inc = android_ndk_arch_include orelse return;
    step.addIncludePath(.{ .cwd_relative = inc });
    step.addIncludePath(.{ .cwd_relative = arch_inc });
}

'''

if 'fn addAndroidNdkIncludes' not in s:
    sub('fn addTranslatedCImports(', helper + 'fn addTranslatedCImports(', 'addTranslatedCImports')

build_marker = 'pub fn build(b: *std.Build) void {'
globals_decl = '''var android_ndk_include: ?[]const u8 = null;
var android_ndk_arch_include: ?[]const u8 = null;
var android_ndk_lib: ?[]const u8 = null;
var android_bionic_compat: ?[]const u8 = null;

'''
build_opts = '''pub fn build(b: *std.Build) void {
    android_ndk_include = b.option([]const u8, "ndk-include", "NDK sysroot usr/include");
    android_ndk_arch_include = b.option([]const u8, "ndk-arch-include", "NDK sysroot usr/include/aarch64-linux-android");
    android_ndk_lib = b.option([]const u8, "ndk-lib", "NDK sysroot usr/lib/aarch64-linux-android");
    android_bionic_compat = b.option([]const u8, "bionic-compat-c", "bionic-compat.c");'''

if 'var android_ndk_include' not in s:
    sub(build_marker, globals_decl + build_opts, 'build options')

sub('    miniaudio_translate.addIncludePath(b.path("src"));\n',
    '    miniaudio_translate.addIncludePath(b.path("src"));\n    addAndroidNdkIncludes(b, miniaudio_translate);\n',
    'miniaudio NDK includes')

sub('    yoga_translate.addIncludePath(yoga_dep.path(""));\n',
    '    yoga_translate.addIncludePath(yoga_dep.path(""));\n    addAndroidNdkIncludes(b, yoga_translate);\n',
    'yoga NDK includes')

sub('    });\n    module.addImport("context_abi_c", header.createModule());',
    '    });\n    addAndroidNdkIncludes(b, header);\n    module.addImport("context_abi_c", header.createModule());',
    'context ABI NDK includes')

sub('''        .linux => {
            module.linkSystemLibrary("dl", .{});
            module.linkSystemLibrary("pthread", .{});
            module.linkSystemLibrary("m", .{});
        },''',
    '''        .linux => {
            module.linkSystemLibrary("dl", .{});
            module.linkSystemLibrary("pthread", .{});
            module.linkSystemLibrary("m", .{});
        },
        .android => {
            if (android_ndk_lib) |lib| module.addLibraryPath(.{ .cwd_relative = lib });
            // bionic: pthread/dl viven en libc; solo libm es una .so aparte.
            module.linkSystemLibrary("m", .{});
        },''',
    'android link branch')

sub('''    addNativeAudioDependencies(b, module, target, macos_sdk_path);
    addYogaDependencies(b, module, false);
''',
    '''    addNativeAudioDependencies(b, module, target, macos_sdk_path);
    addYogaDependencies(b, module, false);
    if (android_bionic_compat) |compat| {
        module.addCSourceFile(.{
            .file = .{ .cwd_relative = compat },
            .flags = &.{ "-std=c99", "-D_GNU_SOURCE" },
        });
    }
''',
    'bionic-compat C source')

if s == orig:
    sys.exit("nothing changed")
open(p, 'w').write(s)
print('patched', p)
