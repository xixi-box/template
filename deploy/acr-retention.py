#!/usr/bin/env python3
"""ACR retention: keep the newest N sha-tagged versions per image.

Never deleted: *latest tags, the currently deployed sha tag, and any tag
whose shape does not match <prefix><40-hex> (unknown-shape safety).

Env:
  ALIYUN_ACR_REGISTRY / ALIYUN_ACR_IMAGE_NAME / ALIYUN_ACR_USERNAME /
  ALIYUN_ACR_PASSWORD / IMAGE_TAG / DEPLOY_IMAGES (JSON) / ACR_KEEP_VERSIONS
"""
import base64
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

ACCEPT = ("application/vnd.docker.distribution.manifest.v2+json, "
          "application/vnd.oci.image.manifest.v1+json, "
          "application/vnd.oci.image.index.v1+json")


def classify(tags, prefixes):
    """Split tags into (groups_by_prefix, keep_fixed). Pure, testable."""
    sha = re.compile(r"^[0-9a-f]{40}$")
    ordered = sorted(set(prefixes), key=len, reverse=True)

    def owner(t):
        for p in ordered:
            if p == "":
                if sha.match(t):
                    return ""
            elif t.startswith(p) and sha.match(t[len(p):]):
                return p
        return None

    groups = {p: [] for p in prefixes}
    keep_fixed = []
    for t in tags:
        p = owner(t)
        if p is None:
            keep_fixed.append(t)
        else:
            groups[p].append(t)
    return groups, keep_fixed


def main():
    reg = os.environ["ALIYUN_ACR_REGISTRY"]
    repo = os.environ["ALIYUN_ACR_IMAGE_NAME"]
    user = os.environ["ALIYUN_ACR_USERNAME"]
    pw = os.environ["ALIYUN_ACR_PASSWORD"]
    keep = int(os.environ.get("ACR_KEEP_VERSIONS", "5"))
    cur = os.environ["IMAGE_TAG"]
    specs = json.loads(os.environ.get("DEPLOY_IMAGES")
                       or '[{"name":"app","dockerfile":"./Dockerfile","tag_prefix":""}]')
    # explicit tag_prefix wins ("" = no prefix, single-image); absent -> image name
    prefixes = [s["tag_prefix"] if "tag_prefix" in s else s["name"] for s in specs]

    try:
        urllib.request.urlopen(f"https://{reg}/v2/", timeout=20)
        print("retention: registry returned 200 without auth challenge; abort")
        return 0
    except urllib.error.HTTPError as e:
        www = e.headers.get("WWW-Authenticate", "")
    realm = re.search(r'realm="([^"]+)"', www).group(1)
    service = re.search(r'service="([^"]+)"', www).group(1)

    basic = base64.b64encode(f"{user}:{pw}".encode()).decode()

    def get_token(action):
        q = (f"service={urllib.parse.quote(service)}"
             f"&scope=repository:{repo}:{action}")
        r = urllib.request.Request(f"{realm}?{q}",
                                   headers={"Authorization": f"Basic {basic}"})
        return json.load(urllib.request.urlopen(r, timeout=20))["token"]

    tok = get_token("pull")
    dtok = get_token("delete,*")

    def call(path, method="GET"):
        headers = {"Authorization": f"Bearer {tok}", "Accept": ACCEPT}
        if method == "DELETE":
            headers["Authorization"] = f"Bearer {dtok}"
        req = urllib.request.Request(f"https://{reg}/v2/{repo}/{path}",
                                     headers=headers, method=method)
        return urllib.request.urlopen(req, timeout=30)

    tags = json.load(call("tags/list")).get("tags") or []
    groups, keep_fixed = classify(tags, prefixes)

    def created(t):
        try:
            man = json.load(call(f"manifests/{t}"))
            d = man.get("config", {}).get("digest")
            if d:
                return json.load(call(f"blobs/{d}")).get("created", "")
        except Exception:
            pass
        return ""

    deleted = 0
    for p, lst in groups.items():
        current = f"{p}{cur}"
        rest = [t for t in lst if t != current]
        ranked = sorted(((created(t), t) for t in rest), reverse=True)
        for _, t in ranked[keep:]:
            try:
                dig = call(f"manifests/{t}").headers.get("Docker-Content-Digest")
                if dig:
                    call(f"manifests/{dig}", method="DELETE")
                    print(f"retention: deleted {t}")
                    deleted += 1
            except Exception as e:
                print(f"retention: keep {t} ({type(e).__name__})")
    print(f"retention: deleted={deleted}; kept newest {keep} per image, "
          f"current sha, and fixed tags {keep_fixed}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
