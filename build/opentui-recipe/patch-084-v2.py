p = '/content/oc-recipe/build/opentui-src/packages/native/build.zig'
import shutil
shutil.copy('/content/otsrc/packages/native/build.zig.bak', p)
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
    s = s.replace(build_marker, globals_decl + 'pub fn build(b: *std.Build) void {\n    android_ndk_include = b.option([]const u8, "ndk-include", "NDK sysroot usr/include");\n    android_ndk_arch_include = b.option([]const u8, "ndk-arch-include", "NDK arch include");\n    android_ndk_lib = b.option([]const u8, "ndk-lib", "NDK lib dir");\n    android_bionic_compat = b.option([]const u8, "bionic-compat-c", "bionic compat C");', 1)

s = s.replace('    miniaudio_translate.addIncludePath(b.path("src"));',
              '    miniaudio_translate.addIncludePath(b.path("src"));\n    addAndroidNdkIncludes(b, miniaudio_translate);', 1)
s = s.replace('    yoga_translate.addIncludePath(yoga_dep.path(""));',
              '    yoga_translate.addIncludePath(yoga_dep.path(""));\n    addAndroidNdkIncludes(b, yoga_translate);', 1)
s = s.replace('    module.addImport("context_abi_c", header.createModule());',
              '    addAndroidNdkIncludes(b, header);\n    module.addImport("context_abi_c", header.createModule());', 1)

old_link = '''        .linux => {
            module.linkSystemLibrary("dl", .{});
            module.linkSystemLibrary("pthread", .{});
            module.linkSystemLibrary("m", .{});
        },'''
new_link = '''        .linux => {
            if (android_ndk_lib) |dir| {
                module.addLibraryPath(.{ .cwd_relative = dir });
                module.linkSystemLibrary("m", .{});
                if (android_bionic_compat) |compat| {
                    module.addCSourceFile(.{ .file = .{ .cwd_relative = compat }, .flags = &.{} });
                }
            } else {
                module.linkSystemLibrary("dl", .{});
                module.linkSystemLibrary("pthread", .{});
                module.linkSystemLibrary("m", .{});
            }
        },'''
assert old_link in s, 'link anchor not found'
s = s.replace(old_link, new_link, 1)
open(p, 'w').write(s)
f = open(p).read()
print('PATCH_V2 OK', f.count('addAndroidNdkIncludes(b,'), 'defineMacro' in f, f.count('b.option([]const u8, "ndk-include"'))
