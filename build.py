#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TVBox 多仓构建器
  1. 拉取 registry 里每个上游配置（主地址失败自动回退备用地址）
  2. 容错解析 JSON（去 BOM / // 注释 / 控制字符）
  3. 校验 spider jar 可达性与 md5
  4. 生成 tvbox-multi.json（多仓索引）与 tvbox-single.json（单仓聚合）
  5. 写 status.json 健康报告
用法： python3 build.py [--test-apis]
"""
import urllib.request, json, socket, re, os, sys, time, hashlib
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urljoin

socket.setdefaulttimeout(25)
UA = {"User-Agent": "Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 Chrome/120 Mobile Safari/537.36"}
HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, "cache")
os.makedirs(CACHE, exist_ok=True)


# ---------- 网络 ----------
def idna_url(u):
    m = re.match(r"(https?://)([^/]+)(.*)", u)
    if not m:
        return u
    try:
        host = m.group(2).encode("idna").decode()
    except Exception:
        host = m.group(2)
    return m.group(1) + host + m.group(3)


def fetch(u, timeout=25):
    try:
        r = urllib.request.urlopen(urllib.request.Request(idna_url(u), headers=UA), timeout=timeout)
        return r.geturl(), r.read()
    except Exception as e:
        return None, f"{type(e).__name__}: {str(e)[:70]}"


# ---------- 解析 ----------
def parse_json_tolerant(b):
    if not isinstance(b, (bytes, bytearray)):
        return None
    t = b.decode("utf-8", "replace").replace("\ufeff", "").strip()
    no_comment = re.sub(r"^\s*//.*$", "", t, flags=re.M)
    strip_ctrl = lambda x: re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", x)
    for v in (t, no_comment, strip_ctrl(t), strip_ctrl(no_comment)):
        try:
            d = json.loads(v)
            if isinstance(d, dict):
                return d
        except Exception:
            continue
    return None


def absolutize(val, base):
    """把 './x' '../x' 这类相对引用按原始配置地址补全；类名(如 csp_XX)不动"""
    if not isinstance(val, str) or not val:
        return val
    if val.startswith("./") or val.startswith("../"):
        return urljoin(base, val)
    return val


def site_has_spider(site):
    if site.get("spider"):
        return True
    try:
        return int(site.get("type") or 0) == 3
    except Exception:
        return False


def classify_site(site):
    """返回 分类标签，用于统计"""
    blob = f"{site.get('name','')} {site.get('key','')}"
    for tag in ("短剧", "红果", "AI", "动漫", "番剧", "综艺", "电影", "电视剧", "少儿", "纪录"):
        if tag in blob:
            return tag
    return "其他"


# ---------- 拉取一个源 ----------
def load_source(src):
    rec = {"id": src["id"], "name": src["name"], "role": src.get("role", "supplement"),
           "tags": src.get("tags", []), "tried": []}
    for u in src["urls"]:
        real, b = fetch(u)
        d = parse_json_tolerant(b)
        if d is not None and isinstance(d.get("urls"), list) and not isinstance(d.get("sites"), list):
            rec["tried"].append({"url": u, "ok": True, "err": None})
            rec.update({"ok": True, "kind": "multi", "url": u, "real_url": real,
                        "sub_names": [x.get("name", "") for x in d["urls"]]})
            return rec
        ok = d is not None and isinstance(d.get("sites"), list)
        rec["tried"].append({"url": u, "ok": ok, "err": None if ok else (b if isinstance(b, str) else "非 TVBox JSON")})
        if not ok:
            continue
        base = real if real.rstrip("/").endswith((".json", ".txt")) else real
        rec.update({"ok": True, "url": u, "real_url": real, "spider": d.get("spider")})
        # 站内相对路径补全
        sites = []
        for s in d["sites"]:
            s = dict(s)
            s["api"] = absolutize(s.get("api"), base)
            if s.get("ext") and isinstance(s.get("ext"), str) and (s["ext"].startswith("./") or s["ext"].startswith("../")):
                s["ext"] = absolutize(s["ext"], base)
            sites.append(s)
        rec["sites_doc"] = sites
        rec["parses_doc"] = d.get("parses") or []
        rec["lives_doc"] = d.get("lives") or []
        rec["spider"] = absolutize(d.get("spider"), base)
        rec["wallpaper"] = d.get("wallpaper")
        rec["flags"] = d.get("flags")
        rec["counts"] = {}
        for s in sites:
            rec["counts"][classify_site(s)] = rec["counts"].get(classify_site(s), 0) + 1
        rec["spiderless"] = len([s for s in sites if not site_has_spider(s)])
        return rec
    rec["ok"] = False
    return rec


def check_jar(rec):
    """校验 spider jar：能否下载 + md5 是否与配置一致"""
    if rec.get("kind") == "multi":
        rec["jar"] = {"ok": True, "note": "多仓，无 jar"}
        return rec
    sp = rec.get("spider")
    if not sp or not isinstance(sp, str) or sp.startswith("csp_"):
        rec["jar"] = {"ok": True, "note": "无独立 jar"}
        return rec
    parts = sp.split(";md5;")
    url, want = parts[0], (parts[1] if len(parts) > 1 else "").lower()
    if url.lower().startswith(("http://", "https://")):
        real, b = fetch(url, timeout=60)
        if not isinstance(b, (bytes, bytearray)):
            rec["jar"] = {"ok": False, "url": url, "err": b}
            return rec
        got = hashlib.md5(b).hexdigest()
        rec["jar"] = {"ok": (not want or got == want), "url": real, "bytes": len(b),
                      "md5_got": got, "md5_want": want}
    else:
        rec["jar"] = {"ok": False, "url": sp, "err": "jar 是相对路径且配置地址无法解析"}
    return rec


# ---------- 构建 ----------
def build_single(loaded):
    base = next((r for r in loaded if r.get("ok") and r["role"] == "base"), None)
    if not base:
        raise SystemExit("没有可用的 base 源，无法生成单仓")
    sites, seen = [], set()
    for s in base["sites_doc"]:
        k = s.get("key") or s.get("name")
        if k in seen:
            continue
        seen.add(k)
        sites.append(s)
    base_n = len(sites)
    added = []
    for r in loaded:
        if not r.get("ok") or r is base or r["role"] == "meta" or r.get("kind") == "multi":
            continue
        n = 0
        for s in r["sites_doc"]:
            if site_has_spider(s):
                continue                       # 别的仓库的 csp 类在当前 jar 里不存在
            k = s.get("key") or s.get("name")
            if k in seen:
                continue
            seen.add(k)
            sites.append(s)
            n += 1
        added.append((r["name"], n))

    parses, pseen = [], set()
    for r in [base] + [x for x in loaded if x.get("ok") and x is not base and x.get("kind") != "multi"]:
        for p in r["parses_doc"]:
            nm = p.get("name")
            if nm in pseen:
                continue
            pseen.add(nm)
            parses.append(p)

    doc = {
        "spider": base["spider"],
        "wallpaper": base.get("wallpaper") or "",
        "sites": sites,
        "lives": base["lives_doc"],
        "parses": parses,
        "flags": base.get("flags") or [],
        "ads": [],
        "规则": "由 dsh 构建：主干=%s，补充站点无需 jar" % base["name"],
    }
    stats = {"base": base["name"], "base_sites": base_n, "added": added,
             "total": len(sites), "parses": len(parses), "lives": len(doc["lives"]),
             "with_spider": len([s for s in sites if site_has_spider(s)])}
    return doc, stats


def build_multi(loaded, registry):
    urls = []
    for r in loaded:
        if r.get("ok") and r.get("kind") != "multi":
            urls.append({"name": r["name"], "url": r["url"]})
    meta = [r for r in loaded if r.get("ok") and r["role"] == "meta"]
    return {"urls": urls}, meta


def main():
    reg = json.load(open(os.path.join(HERE, "config", "sources.json"), encoding="utf-8"))
    srcs = [s for s in reg["sources"] if s.get("enabled", True)]
    with ThreadPoolExecutor(8) as ex:
        loaded = list(ex.map(load_source, srcs))
    with ThreadPoolExecutor(8) as ex:
        loaded = list(ex.map(check_jar, loaded))

    single, stats = build_single(loaded)
    multi, meta = build_multi(loaded, reg)

    # 纯免 jar 精简版：只用 api 直连站点，不依赖任何 jar，换设备/换 App 都最稳
    lite_sites = [s for s in single["sites"] if not site_has_spider(s)]
    lite = {
        "sites": lite_sites,
        "parses": single["parses"],
        "lives": [],
        "flags": [],
        "ads": [],
        "规则": "精简版：仅 %d 个免 jar 的 api 直连站点，最稳但站点较少" % len(lite_sites),
    }
    json.dump(lite, open(os.path.join(HERE, "tvbox-lite.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)

    json.dump(multi, open(os.path.join(HERE, "tvbox-multi.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    json.dump(single, open(os.path.join(HERE, "tvbox-single.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)

    status = {"updated": time.strftime("%Y-%m-%d %H:%M:%S"), "single_stats": stats,
              "lite_sites": len(lite_sites),
              "sources": [{k: v for k, v in r.items() if k not in ("sites_doc", "parses_doc", "lives_doc")} for r in loaded]}
    json.dump(status, open(os.path.join(HERE, "status.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)

    print("== 各源状态 ==")
    for r in loaded:
        if r.get("ok") and r.get("kind") == "multi":
            print(f"  [OK]   {r['name']:<16} 多仓，子仓 {len(r.get('sub_names') or [])} 个")
        elif r.get("ok"):
            c = " ".join(f"{k}{v}" for k, v in sorted(r.get("counts", {}).items(), key=lambda kv: -kv[1])[:6])
            jar = r.get("jar", {})
            jt = "jar OK" if jar.get("ok") else f"jar 异常({jar.get('err') or 'md5 不符'})"
            print(f"  [OK]   {r['name']:<16} {len(r['sites_doc']):>3} 站  {jt:<10} {c}")
        else:
            print(f"  [FAIL] {r['name']:<16} " + "; ".join(f"{t['url']} -> {t['err']}" for t in r["tried"])[:110])
    print("\n== 单仓聚合 ==")
    print(f"  主干 {stats['base']}：{stats['base_sites']} 站")
    for nm, n in stats["added"]:
        print(f"  补充 {nm}：+{n} 个免 jar 站")
    print(f"  合计 {stats['total']} 站，{stats['parses']} 个解析，{stats['lives']} 条直播，其中 {stats['with_spider']} 站用主干 jar")
    print(f"  精简版 tvbox-lite.json：{len(lite_sites)} 个免 jar 站点")
    print("\n== 多仓索引 ==")
    for x in multi["urls"]:
        print("  -", x["name"], "|", x["url"])
    for m in meta:
        print(f"\n  (额外多仓，单独导入) {m['name']} | {m['url']}  子仓 {len(m.get('sub_names') or [])} 个")


if __name__ == "__main__":
    main()
