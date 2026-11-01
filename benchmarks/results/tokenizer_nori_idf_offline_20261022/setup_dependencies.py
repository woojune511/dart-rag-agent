"""Public dependency download only; no corpus or environment credentials read."""
import hashlib
import json
import subprocess
import urllib.request
import zipfile
from pathlib import Path

OUT = Path(__file__).resolve().parent
DEPS = OUT / '_deps'
DEPS.mkdir(exist_ok=True)

def fetch(url):
    with urllib.request.urlopen(url, timeout=120) as r:
        return r.read()

def digest(p, algorithm='sha256'):
    h = hashlib.new(algorithm)
    with p.open('rb') as f:
        for b in iter(lambda: f.read(1024*1024), b''):
            h.update(b)
    return h.hexdigest()

assert not (OUT/'dependency_manifest.json').exists(), 'Dependencies already frozen'
manifest = {'purpose': 'Isolated local Nori analyzer; no document upload', 'files': []}
asset_url = 'https://learn.microsoft.com/en-us/java/openjdk/download'
name = 'microsoft-jdk-17.0.20.1-windows-x64.zip'
url = 'https://aka.ms/download-jdk/'+name
pkg = {'name':name,'link':url,'checksum':fetch(url+'.sha256sum.txt').decode().strip().split()[0]}
archive = DEPS/pkg['name']
print('Downloading isolated JDK: '+pkg['name'], flush=True)
archive.write_bytes(fetch(pkg['link']))
assert digest(archive) == pkg['checksum']
with zipfile.ZipFile(archive) as z:
    for name in z.namelist():
        assert (DEPS/name).resolve().is_relative_to(DEPS.resolve())
    z.extractall(DEPS)
java = next(DEPS.glob('*/bin/java.exe'))
javac = java.with_name('javac.exe')
manifest['jdk'] = {'asset_query':asset_url, 'release':'Microsoft OpenJDK 17.0.20.1', 'url':pkg['link'], 'sha256':pkg['checksum'], 'java':str(java), 'javac':str(javac)}
for artifact in ('lucene-core','lucene-analysis-common','lucene-analysis-nori'):
    name = artifact+'-9.12.3.jar'
    url = 'https://repo.maven.apache.org/maven2/org/apache/lucene/'+artifact+'/9.12.3/'+name
    path = DEPS/name
    print('Downloading '+name, flush=True)
    path.write_bytes(fetch(url))
    expected = fetch(url+'.sha512').decode().strip().split()[0]
    assert digest(path,'sha512') == expected
    manifest['files'].append({'path':str(path),'url':url,'sha512':expected,'sha256':digest(path)})
manifest['java_version'] = subprocess.run([str(java),'-version'],capture_output=True,text=True,check=True).stderr
(OUT/'dependency_manifest.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
cp = ';'.join(str(p) for p in DEPS.glob('*.jar'))
subprocess.run([str(javac),'-encoding','UTF-8','-cp',cp,str(OUT/'NoriBatch.java')],check=True)
print('Isolated dependencies verified and helper compiled.',flush=True)
