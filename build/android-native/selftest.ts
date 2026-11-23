// Self-test del binario compilado (OPENCODE_SELFTEST=1).
// Los imports son DINAMICOS con rutas literales inyectadas en build:
// así los módulos nativos NO se cargan al arrancar (evita dlopen de liblog.so).
import { mkdtemp, writeFile, rm } from "node:fs/promises"
import os from "node:os"
import path from "node:path"

type Row = { name: string; ok: boolean; info: string }
const rows: Row[] = []
function report(name: string, ok: boolean, info = "") {
  rows.push({ name, ok, info })
  console.log(`${ok ? "PASS" : "FAIL"} ${name}${info ? " :: " + info : ""}`)
}

async function testPty(tmp: string) {
  try {
    const m: any = await import("__BP__")
    const p: any = m.spawn("/system/bin/sh", [], { cols: 80, rows: 24, name: "xterm", cwd: tmp })
    let out = ""
    const dispose = p.onData((d: string) => { out += d })
    p.write("echo SELFTEST_PTY_OK\n")
    await new Promise((r) => setTimeout(r, 900))
    p.kill(); try { dispose.dispose() } catch {}
    report("bun-pty", out.includes("SELFTEST_PTY_OK"), JSON.stringify(out.slice(0, 120)))
  } catch (e) { report("bun-pty", false, String(e)) }
}

async function testWatcher(tmp: string) {
  const dir = await mkdtemp(path.join(tmp, "oc-watch-"))
  try {
    const api: any = await import("__PW__")
    let events: string[] = []
    const sub = await (api.subscribe ?? api.default.subscribe)(dir, (err: Error | null, evs: { path: string; type: string }[]) => {
      if (!err) events = evs.map((e) => e.type + ":" + path.basename(e.path))
    })
    await writeFile(path.join(dir, "watched.txt"), "x")
    await new Promise((r) => setTimeout(r, 1200))
    await sub.unsubscribe()
    report("parcel-watcher", events.some((e) => e.includes("watched.txt")), JSON.stringify(events))
  } catch (e) { report("parcel-watcher", false, String(e)) }
  finally { await rm(dir, { recursive: true, force: true }).catch(() => {}) }
}

async function testFff(tmp: string) {
  const dir = await mkdtemp(path.join(tmp, "oc-fff-"))
  try {
    await writeFile(path.join(dir, "selftest_marker.txt"), "ok")
    const m: any = await import("__FFF__")
    const created: any = m.FileFinder.create({ basePath: dir, disableWatch: true })
    if (!created.ok) { report("fff", false, String(created.error)); return }
    const finder = created.value
    try {
      await finder.waitForScan(4000)
      const res: any = finder.search("selftest_marker")
      const n = res?.ok ? (res.value?.items?.length ?? 0) : 0
      report("fff", n > 0, `matches=${n}`)
    } finally { finder.destroy() }
  } catch (e) { report("fff", false, String(e)) }
  finally { await rm(dir, { recursive: true, force: true }).catch(() => {}) }
}

export async function runSelfTest() {
  const tmp = process.env.TMPDIR || os.tmpdir()
  console.log("SELFTEST_START platform=" + process.platform + " arch=" + process.arch)
  await testPty(tmp)
  await testWatcher(tmp)
  await testFff(tmp)
  const failed = rows.filter((r) => !r.ok)
  console.log(`SELFTEST_END pass=${rows.length - failed.length}/${rows.length}`)
  if (failed.length) process.exitCode = 1
}
