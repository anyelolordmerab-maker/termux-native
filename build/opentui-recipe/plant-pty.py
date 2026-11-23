#!/usr/bin/env python3
"""Planta @opencode/pty-linux-arm64-android (y -musl) con el binario estatico de npm."""
import os, json, shutil, glob, subprocess, tarfile

OC = '/content/oc'
PTY_SRC = '/content/pty/package/bin/opencode-pty'

if not os.path.isfile(PTY_SRC):
    os.makedirs('/content/pty', exist_ok=True)
    subprocess.check_call(['curl','-fsSL','-o','/content/pty/pty.tgz',
        'https://registry.npmjs.org/@opencode/pty-linux-arm64-musl/-/pty-linux-arm64-musl-0.6.0.tgz'])
    subprocess.check_call(['tar','xzf','/content/pty/pty.tgz','-C','/content/pty'])
assert os.path.isfile(PTY_SRC), 'no pty bin'

roots = [OC+'/node_modules', OC+'/node_modules/.bun/node_modules', OC+'/packages/cli/node_modules']
for pat in ['@opencode+pty@*','@opentui+core@*']:
    roots += glob.glob(OC+'/node_modules/.bun/'+pat+'/node_modules')
roots = list(dict.fromkeys([r for r in roots if os.path.isdir(r)]))

n=0
for r in roots:
    for name in ['pty-linux-arm64-android','pty-linux-arm64-musl']:
        d = os.path.join(r,'@opencode',name)
        os.makedirs(d+'/bin', exist_ok=True)
        shutil.copy2(PTY_SRC, d+'/bin/opencode-pty')
        os.chmod(d+'/bin/opencode-pty', 0o755)
        json.dump({"name":"@opencode/"+name,"version":"0.6.0","os":["linux"],"cpu":["arm64"],
                   "bin":{"opencode-pty":"./bin/opencode-pty"}}, open(d+'/package.json','w'))
        n+=1
print('PTY PLANTED', n, 'roots', len(roots))
