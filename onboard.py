import os
import shutil
import yaml

tpl = open('deploy-template.yml', encoding='utf-8').read()
MARKER = """      # -------------------------------------------------------------------
      # PROJECT PRE-BUILD (optional)
      # Multi-module projects insert Maven / pnpm build and artifact copy
      # steps here. Build outputs must be copied to the repository root so
      # the Dockerfiles can COPY them from there; node_modules and target/
      # are stripped before archiving (nothing in a Dockerfile reads them).
      # -------------------------------------------------------------------
"""
DEPLOY_ANCHOR = '      - name: Deploy from Aliyun ACR'

JOY_PREPARE = '''      - name: Retire legacy manual container
        shell: bash
        run: docker rm -f joy-shock-mapper-site 2>/dev/null || true

'''

CAD_PREPARE = '''      - name: Retire legacy manual container
        shell: bash
        run: docker rm -f cad2shp 2>/dev/null || true

'''

CAD_PREBUILD = '''      # -------------------------------------------------------------------
      # PROJECT PRE-BUILD: assemble ODA File Converter into build context
      # (Linux rpm lives in the private GitHub release; copyright forbids
      # redistribution -> image must stay in PRIVATE registries only)
      # -------------------------------------------------------------------
      - name: Download ODA rpm from private release
        env:
          GH_TOKEN: ${{ github.token }}
        run: gh release download oda-27.1 --repo ${{ github.repository }} --pattern "*.rpm" --output /tmp/oda.rpm

      - name: Unpack ODA into build context
        run: |
          sudo apt-get update -qq && sudo apt-get install -y -qq rpm2cpio cpio
          mkdir -p cad2shp_standalone/deploy/oda
          cd cad2shp_standalone/deploy/oda
          rpm2cpio /tmp/oda.rpm | cpio -idm --quiet
          ODA_SUB=$(find . -type d -name "ODAFileConverter_*" | head -1)
          test -n "$ODA_SUB" || { echo "ODA dir missing in rpm"; exit 1; }
          cp -a "$ODA_SUB"/. .
          rm -rf usr etc
          test -x ODAFileConverter && echo "ODA ready: $(du -sh . | cut -f1)"

'''


def base(default_ref, acr_name, images_json):
    src = tpl
    src = src.replace("        default: mysql\n        type: choice", "        default: none\n        type: choice")
    src = src.replace("        default: main\n        type: string", f"        default: {default_ref}\n        type: string")
    src = src.replace("  ALIYUN_ACR_REGISTRY: ${{ vars.ALIYUN_ACR_REGISTRY }}",
                      "  ALIYUN_ACR_REGISTRY: crpi-r1wme86kfaw7rr3f.cn-shanghai.personal.cr.aliyuncs.com")
    src = src.replace("  ALIYUN_ACR_USERNAME: ${{ vars.ALIYUN_ACR_USERNAME }}",
                      "  ALIYUN_ACR_USERNAME: aliyun4384550071")
    src = src.replace("  ALIYUN_ACR_IMAGE_NAME: ${{ vars.ALIYUN_ACR_IMAGE_NAME || format('wangshun_build/{0}', github.event.repository.name) }}",
                      f"  ALIYUN_ACR_IMAGE_NAME: {acr_name}")
    src = src.replace("  DEPLOY_IMAGES: ${{ vars.DEPLOY_IMAGES }}\n", f"  DEPLOY_IMAGES: '{images_json}'\n")
    return src


# ---------- JoyShockMapper ----------
joy = base('master', 'wangshun_build/joy-shock-mapper',
           '[{"name":"app","dockerfile":"Dockerfile","context":"site","tag_prefix":""}]')
joy = joy.replace("APP_PORT: ${{ vars.APP_PORT || '8080' }}", "APP_PORT: ${{ vars.APP_PORT || '8081' }}")
joy = joy.replace(DEPLOY_ANCHOR, JOY_PREPARE + DEPLOY_ANCHOR, 1)
joy = ('# Generated from template/deploy-template.yml (ACR-only, matrix build).\n'
       '# JoyShockMapper site: single static nginx image, context=site/,\n'
       '# replaces the manual docker-run container (port 8081->80).\n'
       '# deploy site updates: run with deploy_ref=gui-rework when needed.\n' + joy)

JOY_SERVICES = '''# JoyShockMapper 官网生产服务定义(由 deploy-template.yml 部署模板读取)
services:
  app:
    image: ${IMAGE_APP}
    container_name: joy-shock-mapper-site
    restart: unless-stopped
    ports:
      - "8081:80"
    # 镜像内建 HEALTHCHECK 用 localhost 在本容器恒失败,覆盖为 127.0.0.1
    healthcheck:
      test: ["CMD-SHELL", "wget -q -T 5 --spider http://127.0.0.1:80/ || exit 1"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 10s
'''

# ---------- CAD2SHP ----------
cad = base('master', 'wangshun_build/cad2shp',
           '[{"name":"api","dockerfile":"deploy/Dockerfile","context":"cad2shp_standalone"}]')
cad = cad.replace("""  pre-build:
    name: Project Pre-Build
    needs: setup
    runs-on: ubuntu-latest
""", """  pre-build:
    name: Project Pre-Build
    needs: setup
    runs-on: ubuntu-latest
    permissions:
      contents: read
""")
assert MARKER in cad
cad = cad.replace(MARKER, CAD_PREBUILD)
cad = cad.replace(DEPLOY_ANCHOR, CAD_PREPARE + DEPLOY_ANCHOR, 1)
cad = cad.replace("""      # Project-specific secrets used by deploy/prod-services.yaml interpolation
      # are declared here, e.g. JWT_SECRET: ${{ secrets.JWT_SECRET }}.
""", """      # Project values for deploy/prod-services.yaml interpolation.
      CAD2SHP_API_TOKEN: ${{ secrets.CAD2SHP_API_TOKEN }}
      CAD2SHP_LLM_BASE_URL: ${{ secrets.CAD2SHP_LLM_BASE_URL }}
      CAD2SHP_LLM_API_KEY: ${{ secrets.CAD2SHP_LLM_API_KEY }}
      CAD2SHP_LLM_MODEL: ${{ secrets.CAD2SHP_LLM_MODEL }}
""")
cad = ('# Generated from template/deploy-template.yml (ACR-only, matrix build).\n'
       '# CAD2SHP API: single image (context=cad2shp_standalone/), ODA rpm\n'
       '# assembled in pre-build from the PRIVATE release; ACR repo MUST stay\n'
       '# private (ODA license forbids redistribution). Replaces the dead\n'
       '# manual container (exited 137 three weeks ago); work volume reused.\n' + cad)

CAD_SERVICES = '''# CAD2SHP API 生产服务定义(由 deploy-template.yml 部署模板读取)
services:
  api:
    image: ${IMAGE_API}
    container_name: cad2shp
    restart: unless-stopped
    environment:
      QT_QPA_PLATFORM: offscreen
      CAD2SHP_API_TOKEN: ${CAD2SHP_API_TOKEN:-}
      CAD2SHP_LLM_BASE_URL: ${CAD2SHP_LLM_BASE_URL:-}
      CAD2SHP_LLM_API_KEY: ${CAD2SHP_LLM_API_KEY:-}
      CAD2SHP_LLM_MODEL: ${CAD2SHP_LLM_MODEL:-}
    ports:
      - "8686:8686"
    volumes:
      - work:/app/work
    # python:slim 无 wget,用 socket 探活(端口通 = API 活)
    healthcheck:
      test: ["CMD-SHELL", "python3 -c 'import socket;s=socket.create_connection((\"127.0.0.1\",8686),timeout=5);s.close()'"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 30s

volumes:
  work:
    name: cad2shp-work
'''

out_root = '_onboard'
for sub, wf, services in [('joyshock', joy, JOY_SERVICES), ('cad2shp', cad, CAD_SERVICES)]:
    d = f'{out_root}/{sub}'
    os.makedirs(f'{d}/.github/workflows', exist_ok=True)
    os.makedirs(f'{d}/deploy', exist_ok=True)
    open(f'{d}/.github/workflows/deploy.yml', 'w', encoding='utf-8', newline='\n').write(wf)
    open(f'{d}/deploy/prod-services.yaml', 'w', encoding='utf-8', newline='\n').write(services)
    shutil.copy('deploy/acr-retention.py', f'{d}/deploy/acr-retention.py')
    yaml.safe_load(open(f'{d}/.github/workflows/deploy.yml', encoding='utf-8'))
    yaml.safe_load(open(f'{d}/deploy/prod-services.yaml', encoding='utf-8'))
    print(f'{sub}: generated + valid')
