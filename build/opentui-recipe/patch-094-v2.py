import sys
p = sys.argv[1]
import shutil
shutil.copy(p, p + '.bak')
s = open(p).read()

helper = '''fn addAndroidNdkIncludes(b: *std.Build, step: *std.Build.Step.TranslateC) void {
    const inc = android_ndk_include orelse return;
    const arch_inc = android_ndk_arch_include orelse return;
    step.addIncludePath(.{ .cwd_relative = inc });
    step.addIncludePath(.{ .cwd_relative = arch_inc });
}

'''
marker = 'fn addTranslatedCImports('
if 'fn addAndroidNdkIncludes' not in s:
    s = s.replace(marker, helper + marker, 1)

build_marker = 'pub fn build(b: *std.Build) void {'
globals_decl = '''var android_ndk_include: ?[]const u8 = null;
var android_ndk_arch_include: ?[]const u8 = null;
var android_ndk_lib: ?[]const u8 = null;
var android_bionic_compat: ?[]const u8 = null;

'''
if 'var android_ndk_include' not in s:
    s = s.replace(build_marker, globals_decl + 'pub fn build(b: *std.Build) void {\n    android_ndk_include = b.option([]const u8, "ndk-include", "NDK sysroot usr/include");\n    android_ndk_arch_include = b.option([]const u8, "ndk-arch-include", "NDK sysroot usr/include/aarch64-linux-android");\n    android_ndk_lib = b.option([]const u8, "ndk-lib", "NDK sysroot usr/lib/aarch64-linux-android");\n    android_bionic_compat = b.option([]const u8, "bionic-compat", "bionic-compat.c");', 1)

s = s.replace('    miniaudio_translate.addIncludePath(b.path("src"));\n', '    miniaudio_translate.addIncludePath(b.path("src"));\n    addAndroidNdkIncludes(b, miniaudio_translate);\n', 1)
s = s.replace('    yoga_translate.addIncludePath(yoga_dep.path(""));\n', '    yoga_translate.addIncludePath(yoga_dep.path(""));\n    addAndroidNdkIncludes(b, yoga_translate);\n', 1)
s = s.replace('    });\n    module.addImport("yoga", yoga_translate.createModule());\n    addContextABIHeader(b, module, optimize, target);\n}', '    });\n    module.addImport("yoga", yoga_translate.createModule());\n    addAndroidNdkIncludes(b, yoga_translate);\n    addContextABIHeader(b, module, optimize, target);\n}', 1)

s = s.replace('''        .linux => {
            module.linkSystemLibrary("dl", .{});
            module.linkSystemLibrary("pthread", .{});
            module.linkSystemLibrary("m", .{});
        },''', '''        .linux => {
            module.linkSystemLibrary("dl", .{});
            module.linkSystemLibrary("pthread", .{});
            module.linkSystemLibrary("m", .{});
        },
        .android => {
            module.linkSystemLibrary("dl", .{});
            module.linkSystemLibrary("pthread", .{});
            module.linkSystemLibrary("m", .{});
        },''', 1)

open(p, 'w').write(s)
print('patched', p)
